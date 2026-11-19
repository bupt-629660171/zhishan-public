# -*- coding: utf-8 -*-
"""知源智膳 · 规则引擎（确定性判定层）。

职责边界（对应立项书创新点 1「规则与模型分离」）：
    输入：菜品 + 体质 + 用户限制
    输出：判定（禁/慎/宜）+ 命中的规则（含编号与出处）+ 一句话理由
    本模块不调用任何大模型，纯 SQLite 查询 + 集合运算。

判定的唯一入口是 `evaluate()` / `plan()`；
`app.py` 与 `eval_metrics.py` 都走这里，保证"评测的就是线上跑的"。
"""

from __future__ import annotations

from contextlib import closing

import os
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from version import RULE_VERSION


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("ZY_DB_PATH", BASE_DIR / "food.db"))
SUPPORTED_CONSTITUTIONS = ("气虚", "湿热")
ACTION_RANK = {"禁": 2, "慎": 1, "宜": 0}


@dataclass(frozen=True)
class Evidence:
    """一条规则对一道菜的判定证据——可追溯性的最小单位。"""

    rule_code: str
    action: str
    tag: str
    rationale: str
    source_ref: str
    rule_version: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_code,
            "action": self.action,
            "tag": self.tag,
            "rationale": self.rationale,
            "source_ref": self.source_ref,
            "rule_version": self.rule_version,
        }


def _connect() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"数据库不存在：{DATABASE_PATH}，请先运行 python schema.py")
    con = sqlite3.connect(DATABASE_PATH)
    con.row_factory = sqlite3.Row
    return con


def load_rules(constitution: str) -> dict[str, dict]:
    """返回该体质下 tag -> 规则（同 tag 多规则时取动作最严的一条）。"""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT code, action, tag, rationale, source_ref, version FROM Rules WHERE constitution=?",
            (constitution,),
        ).fetchall()
    best: dict[str, dict] = {}
    for r in rows:
        tag = r["tag"]
        if tag not in best or ACTION_RANK[r["action"]] > ACTION_RANK[best[tag]["action"]]:
            best[tag] = {
                "code": r["code"],
                "action": r["action"],
                "tag": tag,
                "rationale": r["rationale"],
                "source_ref": r["source_ref"],
                "version": r["version"],
            }
    return best


def dish_tags(con: sqlite3.Connection, dish_id: int) -> dict[str, str]:
    rows = con.execute(
        "SELECT tag, COALESCE(evidence, '') FROM Dish_Tag WHERE dish_id=?", (dish_id,)
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def evaluate(
    dish: dict,
    constitution: str,
    *,
    rules: dict[str, dict] | None = None,
    tags: set[str] | None = None,
) -> dict:
    """对单道菜做规则判定。

    dish: {"id", "name", "property", "explanation", ...}
    tags: 显式传入标签（测试/评测用）；不传则从 Dish_Tag 读。
    """
    if constitution not in SUPPORTED_CONSTITUTIONS:
        return {
            "verdict": "未知",
            "evidence": [],
            "rationale": f"暂不支持体质「{constitution}」，当前仅覆盖 {'、'.join(SUPPORTED_CONSTITUTIONS)}。",
            "rule_version": RULE_VERSION,
        }

    rules = rules if rules is not None else load_rules(constitution)
    if tags is None:
        with closing(_connect()) as con:
            tags = set(dish_tags(con, dish["id"])) if dish.get("id") else set()

    matched: list[Evidence] = [
        Evidence(
            rule_code=rules[tag]["code"],
            action=rules[tag]["action"],
            tag=tag,
            rationale=rules[tag]["rationale"],
            source_ref=rules[tag]["source_ref"],
            rule_version=rules[tag]["version"],
        )
        for tag in sorted(tags)
        if tag in rules
    ]
    matched.sort(key=lambda e: (-ACTION_RANK[e.action], e.rule_code))
    if not matched:
        matched.append(
            Evidence(
                rule_code="NEUTRAL",
                action="宜",
                tag="neutral",
                rationale="未命中本体质的禁忌条规，按平性处理，可正常食用。",
                source_ref="规则表默认：无禁忌证据即放行（保守原则仅对命中项生效）",
                rule_version=RULE_VERSION,
            )
        )

    if not matched:
        neutral = Evidence(
            rule_code="NEUTRAL",
            action="宜",
            tag="neutral",
            rationale="未命中本体质的禁忌条规，按平性处理，可正常食用。",
            source_ref="规则表默认：无禁忌证据即放行（保守原则仅对命中项生效）",
            rule_version=RULE_VERSION,
        )
        return {
            "verdict": "宜",
            "evidence": [neutral.to_dict()],
            "rationale": neutral.rationale,
            "rule_version": RULE_VERSION,
        }

    actions = [e.action for e in matched]
    verdict = max(actions, key=lambda a: ACTION_RANK[a])
    top = [e for e in matched if e.action == verdict]
    return {
        "verdict": verdict,
        "evidence": [e.to_dict() for e in matched],
        "rationale": "；".join(f"{e.rule_code}：{e.rationale}" for e in top),
        "rule_version": RULE_VERSION,
    }


def search_dish(query: str) -> dict:
    """菜名检索：精确名 → 别名 → 子串/反向子串。

    返回 {"status": "hit"|"ambiguous"|"miss", "candidates": [...], "matched_by": str}
    单字查询（如"肉""饭"）不再直接取一条，避免"查肉返回麻辣牛肉饭"这类事故。
    """
    q = "".join((query or "").split())
    if not q:
        return {"status": "miss", "candidates": [], "matched_by": ""}

    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT id, name, property, explanation, calories FROM Dish"
        ).fetchall()
        alias_row = con.execute(
            "SELECT dish_name FROM Dish_Alias WHERE alias=?", (q,)
        ).fetchone()

    base = {r["name"]: r for r in rows}

    # 1) 精确菜名
    if q in base:
        return {"status": "hit", "candidates": [base[q]["name"]], "matched_by": "exact"}
    # 2) 别名（只接受库内真实存在的菜品）
    if alias_row and alias_row[0] in base:
        return {"status": "hit", "candidates": [alias_row[0]], "matched_by": "alias"}
    # 3) 子串匹配；单字查询一律视为歧义，必须让用户说清楚
    if len(q) == 1:
        hits = [n for n in base if q in n]
        return {
            "status": "ambiguous" if hits else "miss",
            "candidates": sorted(hits, key=len)[:8],
            "matched_by": "single_char",
        }

    # 反向包含：只有菜名足够长（>=3 字）才算，避免「燕麦」命中「燕麦拿铁」
    hits = [n for n in base if q in n or (len(n) >= 3 and n in q)]
    if len(hits) == 1:
        return {"status": "hit", "candidates": hits, "matched_by": "substring"}
    if len(hits) > 1:
        return {
            "status": "ambiguous",
            "candidates": sorted(hits, key=lambda n: (len(n), n))[:8],
            "matched_by": "substring",
        }
    return {"status": "miss", "candidates": [], "matched_by": ""}


def query_by_dish(dish_name: str, constitution: str) -> dict:
    """开发调试接口：检索单道菜并返回完整、可追溯的规则判定。"""
    search = search_dish(dish_name)
    base = {
        "status": search["status"],
        "dish_name": None,
        "matched_by": search["matched_by"],
        "candidates": search["candidates"],
        "verdict": "未命中" if search["status"] == "miss" else "歧义",
        "rule_id": "",
        "source_ref": "",
        "rule_version": RULE_VERSION,
    }
    if search["status"] != "hit":
        return base

    canonical_name = search["candidates"][0]
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT id, name, property, explanation, calories FROM Dish WHERE name=?",
            (canonical_name,),
        ).fetchone()
        tags = set(dish_tags(con, row["id"])) if row else set()
    if row is None:
        return base

    result = evaluate(dict(row), constitution, tags=tags)
    evidence = result["evidence"]
    return {
        "status": "hit",
        "dish_name": canonical_name,
        "matched_by": search["matched_by"],
        "candidates": search["candidates"],
        "verdict": result["verdict"],
        "rule_id": ",".join(dict.fromkeys(item["rule_id"] for item in evidence)),
        "source_ref": "；".join(dict.fromkeys(item["source_ref"] for item in evidence)),
        "rule_version": result["rule_version"],
        "rationale": result["rationale"],
        "evidence": evidence,
    }


def _tag_similarity(a: set[str], b: set[str]) -> float:
    """标签 Jaccard；两边都空时给 0.5，避免中性菜互相排斥。"""
    if not a and not b:
        return 0.5
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _attach_alternatives(recommendations: list[dict], pool: list[dict],
                         tags: dict[int, set[str]], keep: int = 2) -> None:
    """为每道推荐挂上 keep 个替代项（就地修改）。"""
    chosen = {d["id"] for d in recommendations}
    for rec in recommendations:
        base = tags.get(rec["id"], set())
        rec_window = (rec.get("canteen_info") or "").split("｜")[0]
        scored = []
        for cand in pool:
            if cand["id"] in chosen:
                continue
            score = _tag_similarity(base, tags.get(cand["id"], set()))
            cand_window = (cand.get("canteen_info") or "").split("｜")[0]
            if rec_window and cand_window and rec_window == cand_window:
                score += 0.15
            if cand["verdict"] == rec["verdict"]:
                score += 0.05
            scored.append((score, cand))
        scored.sort(key=lambda x: (-x[0], x[1]["name"]))
        rec["alternatives"] = [
            {
                "name": c["name"],
                "verdict": c["verdict"],
                "property": c.get("property", ""),
                "canteen_info": c.get("canteen_info", ""),
            }
            for _, c in scored[:keep]
        ]


def plan(
    constitution: str,
    *,
    constraints: set[str] | None = None,
    emotion_rules: dict[int, bool] | None = None,
    limit: int = 3,
    seed: int | None = None,
    campus: str | None = None,
    statuses: tuple[str, ...] = ("草案", "已审核"),
) -> dict:
    """为该体质产出方案：先按规则判定，再按 宜 > 中性 > 慎 排序。

    返回结构保持与旧版 generate_diet_plan 字段兼容，另增 evidence。
    """
    if constitution not in SUPPORTED_CONSTITUTIONS:
        return {
            "status": "error",
            "message": f"暂不支持体质「{constitution}」。",
            "recommendations": [],
            "total_count": 0,
            "blocked_count": 0,
            "remaining_count": 0,
            "blocked_details": [],
        }

    rules = load_rules(constitution)
    constraint_set = constraints or set()
    emotion_rules = emotion_rules or {}

    with closing(_connect()) as con:
        rows = con.execute(
            """
            SELECT d.id, d.name, d.property, d.explanation, d.calories,
                (SELECT GROUP_CONCAT(
                    c.location || '｜' || c.window_name ||
                    CASE WHEN c.price IS NULL OR c.price <= 0 THEN '' ELSE '（￥' || c.price || '）' END,
                    '；')
                 FROM Canteen c WHERE c.dish_id = d.id) AS canteen_info
            FROM Dish d
            WHERE COALESCE(d.kind, 'dish') = 'dish'
              AND (? IS NULL OR EXISTS (
                    SELECT 1 FROM Dish_Source s WHERE s.dish_id = d.id AND s.campus = ?))
            ORDER BY d.id
            """,
            (campus, campus),
        ).fetchall()
        tag_map: dict[int, set[str]] = {}
        for r in con.execute("SELECT dish_id, tag FROM Dish_Tag"):
            tag_map.setdefault(r["dish_id"], set()).add(r["tag"])
        constraint_map: dict[int, set[str]] = {}
        if constraint_set:
            ph = ",".join("?" for _ in constraint_set)
            for r in con.execute(
                f"SELECT dish_id, constraint_type FROM Constraint_Rule WHERE constraint_type IN ({ph})",
                tuple(constraint_set),
            ):
                constraint_map.setdefault(r["dish_id"], set()).add(r["constraint_type"])

    kept: list[dict] = []
    blocked: list[dict] = []
    for r in rows:
        dish = {
            "id": r["id"],
            "name": r["name"],
            "property": r["property"] or "",
            "explanation": r["explanation"] or "",
            "calories": r["calories"],
            "canteen_info": r["canteen_info"] or "",
        }
        verdict = evaluate(dish, constitution, rules=rules, tags=tag_map.get(r["id"], set()))

        # 用户显式限制优先于体质规则（如"素食"直接排除）
        blocked_by_constraint = sorted(constraint_map.get(r["id"], set()))
        if blocked_by_constraint:
            blocked.append(
                {"name": dish["name"], "reason": "用户限制：" + "、".join(blocked_by_constraint)}
            )
            continue
        if verdict["verdict"] == "禁":
            blocked.append(
                {
                    "name": dish["name"],
                    "reason": "体质禁忌：" + verdict["rationale"],
                    "rule_codes": [e["rule_id"] for e in verdict["evidence"] if e["action"] == "禁"],
                }
            )
            continue

        kept.append(
            {
                **dish,
                "verdict": verdict["verdict"],
                "rationale": verdict["rationale"],
                "evidence": verdict["evidence"],
                "source_ref": "；".join(
                    dict.fromkeys(e["source_ref"] for e in verdict["evidence"])
                ) or "规则表默认（无具体条规命中）",
                "rule_id": ",".join(
                    dict.fromkeys(e["rule_id"] for e in verdict["evidence"])
                ) or "DEFAULT_CAUTION",
                "rule_version": verdict["rule_version"],
                "_emotion": emotion_rules.get(r["id"], False),
            }
        )

    if not kept:
        return {
            "status": "empty",
            "message": "严格过滤后暂无符合条件的菜品，请减少限制条件后重试。",
            "recommendations": [],
            "total_count": len(rows),
            "blocked_count": len(blocked),
            "remaining_count": 0,
            "blocked_details": blocked,
            "constitution": constitution,
        }

    rng = random.Random(seed)
    rng.shuffle(kept)

    VERDICT_PRIORITY = {"宜": 0, "慎": 1, "禁": 2}

    def _rank(d: dict) -> tuple:
        return (
            VERDICT_PRIORITY.get(d["verdict"], 1),   # 第一优先：宜 → 慎
            not any(e["action"] == "宜" for e in d["evidence"]),
            not d["_emotion"],
            -len(d["evidence"]),
        )

    kept.sort(key=_rank)
    recommendations = kept[:limit]
    _attach_alternatives(recommendations, kept, tag_map)
    for d in recommendations:
        d.pop("_emotion", None)

    return {
        "status": "ok",
        "message": "调养方案生成完成。",
        "constitution": constitution,
        "campus": campus,
        "constraints": sorted(constraint_set),
        "recommendations": recommendations,
        "total_count": len(rows),
        "blocked_count": len(blocked),
        "remaining_count": len(kept),
        "blocked_details": blocked,
        "rule_version": RULE_VERSION,
    }


def sensitivity() -> dict:
    """两种体质下判定不同的菜品——用于证明"体质真的改变了判定"，而非文案差异。"""
    verdicts: dict[str, dict[str, str]] = {}
    for c in SUPPORTED_CONSTITUTIONS:
        with closing(_connect()) as con:
            dishes = con.execute(
                "SELECT id, name FROM Dish WHERE COALESCE(kind, 'dish') = 'dish'"
            ).fetchall()
            tag_map: dict[int, set[str]] = {}
            for r in con.execute("SELECT dish_id, tag FROM Dish_Tag"):
                tag_map.setdefault(r["dish_id"], set()).add(r["tag"])
        rules = load_rules(c)
        verdicts[c] = {
            r["name"]: evaluate({"id": r["id"], "name": r["name"]}, c, rules=rules, tags=tag_map.get(r["id"], set()))["verdict"]
            for r in dishes
        }

    qi, damp = verdicts["气虚"], verdicts["湿热"]
    differing = [n for n in qi if qi[n] != damp.get(n)]
    banned_qi = {n for n, v in qi.items() if v == "禁"}
    banned_damp = {n for n, v in damp.items() if v == "禁"}
    return {
        "气虚禁": len(banned_qi),
        "湿热禁": len(banned_damp),
        "判定不同": len(differing),
        "仅气虚禁": sorted(banned_qi - banned_damp),
        "仅湿热禁": sorted(banned_damp - banned_qi),
        "判定不同示例": sorted(differing)[:8],
    }


if __name__ == "__main__":
    import json

    print(json.dumps(sensitivity(), ensure_ascii=False, indent=2))
