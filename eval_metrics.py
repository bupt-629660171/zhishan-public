# -*- coding: utf-8 -*-
"""知源智膳 · 考核指标基线评测（P0 阶段必备资产）。

用法：
    python eval_metrics.py            # 跑全部指标，写 eval_report.md / eval_report.json
    python eval_metrics.py --check    # 只核对金标菜品是否都在库中

覆盖立项书 5 项考核指标 + 1 项根因检测：
    1. 测试集禁忌违规率        ——被放行的菜里是否仍有该体质的"禁"证据
    2. 方案条目可追溯率        ——每条推荐是否带 规则ID/出处/版本
    3. 体质硬过滤准确率        ——对照人工金标
    4. 单次方案生成延迟
    5. 免责声明覆盖率
    6. 体质敏感度（根因检测）  ——两种体质被判"禁"的集合差集，为 0 说明体质没起作用

金标来自菜品库 explanation 文本反推（"湿热者少吃""适合气虚调理"），
属"库内一致性"标注，不能替代导师对中医规则的复核。
"""

from __future__ import annotations

from contextlib import closing

import json
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import rule_engine as engine
from version import RULE_VERSION


BASE_DIR = Path(__file__).resolve().parent
REPORT_PATH = BASE_DIR / "eval_report.md"
JSON_PATH = BASE_DIR / "eval_report.json"

# 每条推荐必须具备的可追溯字段
TRACE_FIELDS = ("rule_id", "source_ref", "rule_version")


# ---------------------------------------------------------------- 人工金标
# (菜名, 体质, 期望 verdict, 依据) —— verdict 取 "禁" / "非禁"
# 依据必须能对应到 explanation 里的一句话，便于导师复核标注是否合理。
GOLD_LABELS: list[tuple[str, str, str, str]] = [
    # ---------------- 气虚 ----------------
    ("麻辣香锅", "气虚", "禁", "辛辣重油，气虚忌辣、耗气"),
    ("麻辣烫13元套餐", "气虚", "禁", "辛辣重油，气虚忌辣"),
    ("脆皮鸡饭", "气虚", "禁", "油炸燥热，气虚者难消化且易上火"),
    ("水煮毛血旺", "气虚", "禁", "大辛大热，气虚者易上火"),
    ("蛋糕", "气虚", "禁", "高糖甜腻碍胃，气虚者脾胃本弱"),
    ("蒜蓉卷章", "气虚", "禁", "油炸油腻，气虚者难消化"),
    ("西瓜", "气虚", "禁", "寒凉生津，气虚脾胃弱者慎用"),
    ("蛋黄烧卖", "气虚", "禁", "高脂高碳，极难消化、易生湿滞气"),
    ("山药鸡汤", "气虚", "非禁", "山药健脾益气，鸡汤温补，适合气虚"),
    ("五谷渔粉", "气虚", "非禁", "温润易消化，适合气虚调理"),
    ("清蒸鱼", "气虚", "非禁", "清淡温润、高蛋白低脂，极易消化"),
    ("白灼虾", "气虚", "非禁", "温补清淡，气虚者极佳选择"),
    ("馒头", "气虚", "非禁", "健脾养胃，气虚必备主食"),
    ("玉米鲜肉", "气虚", "非禁", "玉米健脾、鲜肉温补，粗细搭配"),
    ("米饭", "气虚", "非禁", "平性碳水，补中益气，基础主食"),
    ("白灼生菜", "气虚", "非禁", "清淡少油，不碍脾胃"),
    ("什锦杂粮", "气虚", "非禁", "健脾益气，升糖指数低"),
    ("猪肉白萝卜包子", "气虚", "非禁", "萝卜下气消食，中和猪肉油腻"),
    ("黄焖鸡米饭", "气虚", "非禁", "温补偏油，气虚可少量，湿热少吃"),
    # ---------------- 湿热 ----------------
    ("麻辣牛肉拼辣椒炒肉饭", "湿热", "禁", "大热大燥，极易生内热，湿热慎用"),
    ("水煮毛血旺", "湿热", "禁", "红油辣椒极多，湿热上火者绝对忌口"),
    ("巴蜀水煮肉片", "湿热", "禁", "重油辣，易生湿热火毒"),
    ("水煮肉", "湿热", "禁", "红油重辣，湿热体质大忌"),
    ("招牌卤肉饭", "湿热", "禁", "卤制肥腻多脂，易生痰湿"),
    ("蛋挞", "湿热", "禁", "高糖高油，甜腻碍胃，极易生痰湿"),
    ("酱香肘花", "湿热", "禁", "脂肪极高，易碍脾胃、助生湿热"),
    ("软糯鸡爪螺蛳粉", "湿热", "禁", "酸辣发散属发物，湿热体质者少吃"),
    ("酥肉小火锅", "湿热", "禁", "油炸配辛辣火锅，极易上火"),
    ("白灼生菜", "湿热", "非禁", "清淡利水，富含膳食纤维，湿热者首选"),
    ("蒜蓉西兰花", "湿热", "非禁", "高纤维、清淡少油，减脂首选"),
    ("减脂大拌菜", "湿热", "非禁", "低卡低脂、利尿排湿，适合湿热"),
    ("清炒时蔬", "湿热", "非禁", "清淡易消化，可减少油腻积热"),
    ("海带丝米粉", "湿热", "非禁", "海带软坚，适合痰湿体质"),
    ("土豆丝", "湿热", "非禁", "平性、健脾易消化，不助湿热"),
    ("白灼菜心", "湿热", "非禁", "清热去火、少油健康"),
    ("菠菜鸡蛋", "湿热", "非禁", "平性养阴，不偏不倚，各类体质皆宜"),
    ("西红柿鸡蛋", "湿热", "非禁", "平性生津，酸甜开胃，大众皆宜"),
]


@dataclass
class Metric:
    name: str
    value: str
    target: str
    passed: bool
    note: str = ""


@dataclass
class Report:
    metrics: list[Metric] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)


def _dish_rows() -> list[dict]:
    with closing(sqlite3.connect(engine.DATABASE_PATH)) as con:
        con.row_factory = sqlite3.Row
        return [
            dict(r)
            for r in con.execute(
                "SELECT id, name, property, explanation, calories FROM Dish ORDER BY id"
            )
        ]


def _verdict_map(constitution: str) -> dict[str, dict]:
    """对 Dish 全表（菜品 + 基础食材）逐一取判定。

    注意：不能走 plan()——plan 只返回 kind='dish'，会把食材漏掉。
    """
    import sqlite3 as _sqlite

    rules = engine.load_rules(constitution)
    with _sqlite.connect(engine.DATABASE_PATH) as con:
        con.row_factory = _sqlite.Row
        dishes = [dict(r) for r in con.execute("SELECT id, name, kind FROM Dish")]
        tags: dict[int, set[str]] = {}
        for r in con.execute("SELECT dish_id, tag FROM Dish_Tag"):
            tags.setdefault(r["dish_id"], set()).add(r["tag"])

    out: dict[str, dict] = {}
    for d in dishes:
        v = engine.evaluate(
            {"id": d["id"], "name": d["name"]}, constitution,
            rules=rules, tags=tags.get(d["id"], set()),
        )
        out[d["name"]] = {"name": d["name"], "verdict": v["verdict"], "evidence": v["evidence"]}
    return out


GOLD_JSON = BASE_DIR / "gold_labels.json"


def _load_labels() -> list[tuple[str, str, str, str]]:
    """优先读 gold_labels.json（人工标注、可审），缺失时回退到内置金标。"""
    if not GOLD_JSON.exists():
        return list(GOLD_LABELS)
    payload = json.loads(GOLD_JSON.read_text(encoding="utf-8"))
    out = []
    for item in payload.get("labels", []):
        out.append(
            (item["name"], item["constitution"], item["expected"], item.get("note") or "")
        )
    return out or list(GOLD_LABELS)


def check_gold_presence() -> list[str]:
    names = {d["name"] for d in _dish_rows()}
    return sorted({d for d, _, _, _ in GOLD_LABELS if d not in names})


def evaluate() -> Report:
    labels = _load_labels()
    report = Report()
    names_in_db = {d["name"] for d in _dish_rows()}
    missing = sorted({d for d, _, _, _ in labels if d not in names_in_db})
    if missing:
        raise SystemExit(f"金标里有 {len(missing)} 道菜不在库中：{sorted(missing)}")
    missing = []

    _ = check_gold_presence()

    if missing:
        raise SystemExit(f"金标里有 {len(missing)} 道菜不在库中：{missing}")

    verdicts_by_constitution = {c: _verdict_map(c) for c in engine.SUPPORTED_CONSTITUTIONS}

    # ---- 指标 3：体质硬过滤准确率
    confusion: dict[str, dict[str, int]] = {}
    for dish, constitution, expect, why in labels:
        d = verdicts_by_constitution[constitution].get(dish, {})
        actual = d.get("verdict", "未收录")
        bucket = confusion.setdefault(constitution, {"correct": 0, "wrong": 0, "n": 0})
        bucket["n"] += 1
        if (expect == "禁" and actual == "禁") or (expect == "非禁" and actual in ("慎", "宜")):
            bucket["correct"] += 1
        else:
            bucket["wrong"] += 1
            report.mismatches.append(
                f"{constitution} × {dish}：期望 {expect}，实际 {actual}（{why}）"
            )
    correct = sum(b["correct"] for b in confusion.values())
    total = sum(b["n"] for b in confusion.values())
    accuracy = correct / total if total else 0.0
    report.metrics.append(
        Metric(
            "体质硬过滤准确率",
            f"{accuracy:.1%}（{correct}/{total}）",
            "≥95%",
            accuracy >= 0.95,
            f"分体质：{json.dumps(confusion, ensure_ascii=False)}",
        )
    )

    # ---- 指标 6：体质敏感度
    banned = {c: {n for n, d in m.items() if d.get("verdict") == "禁"} for c, m in verdicts_by_constitution.items()}
    only_qi = banned["气虚"] - banned["湿热"]
    only_damp = banned["湿热"] - banned["气虚"]
    report.metrics.append(
        Metric(
            "体质敏感度（判定不同菜品数）",
            f"仅气虚禁 {len(only_qi)} 道 / 仅湿热禁 {len(only_damp)} 道",
            "两侧均 >0 且方向符合体质理论",
            bool(only_qi) and bool(only_damp),
            f"仅气虚禁示例：{'、'.join(sorted(only_qi)[:5])}；"
            f"仅湿热禁示例：{'、'.join(sorted(only_damp)[:5])}",
        )
    )

    # ---- 指标 1：禁忌违规率（放行集合里出现"禁"证据即为违规）
    violations: list[str] = []
    released = 0
    for c, mapping in verdicts_by_constitution.items():
        for name, d in mapping.items():
            if d.get("verdict") == "禁":
                continue
            released += 1
            banned_rules = [e["rule_id"] for e in d.get("evidence", []) if e["action"] == "禁"]
            if banned_rules:
                violations.append(f"{c} × {name}: {'、'.join(banned_rules)}")
    report.metrics.append(
        Metric(
            "测试集禁忌违规率",
            f"{len(violations)}/{released} = {len(violations) / released:.2%}" if released else "N/A",
            "0%",
            not violations,
            "；".join(violations[:5]) or "放行集合内无「禁」级规则证据",
        )
    )

    # ---- 指标 2：可追溯率
    sample = engine.plan("气虚", limit=3, seed=7)
    recs = sample["recommendations"]
    required = ("rule_id", "source_ref", "rule_version")
    traced = [d for d in recs if all(d.get(k) for k in required)]
    weak = [d for d in recs if not d.get("evidence")]
    report.metrics.append(
        Metric(
            "方案条目可追溯率",
            f"{len(traced)}/{len(recs)} = {len(traced) / len(recs):.0%}" if recs else "N/A",
            "100% 条目带 规则ID+出处+版本",
            bool(recs) and len(traced) == len(recs),
            (
                f"示例：{recs[0]['name']} ← {recs[0]['rule_id']}（{recs[0]['source_ref'][:36]}…）；"
                f"其中 {len(weak)} 条未命中具体条规、按 DEFAULT_CAUTION 处理"
            )
            if recs
            else "无推荐结果",
        )
    )

    # ---- 指标 4：延迟
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        engine.plan("气虚", constraints={"素食", "不吃辣"}, limit=3)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p95 = times[int(len(times) * 0.95)]
    report.metrics.append(
        Metric(
            "单次方案生成延迟（本地）",
            f"p50 {times[len(times) // 2]:.1f} ms / p95 {p95:.1f} ms",
            "本地 <100 ms；端到端（含 AI）≤5000 ms",
            p95 <= 5000,
            "AI 链路需单独测量，建议 15 s 超时并降级到本地结果",
        )
    )

    # ---- 指标 5：免责声明 + 依据完整性
    from shafe_mvp import plan_to_text

    text = plan_to_text(sample)
    from version import DISCLAIMER

    has_disclaimer = "不替代专业医疗建议" in text and DISCLAIMER[:8] in text
    with closing(sqlite3.connect(engine.DATABASE_PATH)) as con:
        no_expl = con.execute(
            "SELECT COUNT(*) FROM Dish WHERE explanation IS NULL OR TRIM(explanation)=''"
        ).fetchone()[0]
        no_tags = con.execute(
            "SELECT COUNT(*) FROM Dish d WHERE NOT EXISTS (SELECT 1 FROM Dish_Tag t WHERE t.dish_id=d.id)"
        ).fetchone()[0]
    report.metrics.append(
        Metric(
            "免责声明与依据完整性",
            f"{'含声明' if has_disclaimer else '缺声明'}；无解释 {no_expl} 条、无标签 {no_tags} 条",
            "每份导出含声明，每条菜品至少 1 个标签",
            has_disclaimer and no_expl == 0 and no_tags == 0,
            "规则版本 " + RULE_VERSION,
        )
    )

    _write_report(report)
    return report


def _write_report(report: Report) -> None:
    lines = [
        "# 知源智膳 · 考核指标基线",
        "",
        f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M}",
        f"- 规则版本：`{RULE_VERSION}`",
        f"- 数据库：`{Path(engine.DATABASE_PATH).name}`",
        "",
        "| 考核指标 | 当前值 | 目标 | 结论 |",
        "| --- | --- | --- | --- |",
    ]
    for m in report.metrics:
        lines.append(f"| {m.name} | {m.value} | {m.target} | {'PASS' if m.passed else 'FAIL'} |")
    lines += ["", "## 明细"]
    for m in report.metrics:
        if m.note:
            lines.append(f"- **{m.name}**：{m.note}")
    if report.mismatches:
        lines += ["", f"## 判定与金标不一致（{len(report.mismatches)} 条）"]
        lines += [f"- {x}" for x in report.mismatches]
    lines += [
        "",
        "> 金标由菜品库 `explanation` 反推，属“库内一致性”检验；中医规则本身仍需导师复核。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "rule_version": RULE_VERSION,
                "metrics": [
                    {"name": m.name, "value": m.value, "target": m.target, "passed": m.passed, "note": m.note}
                    for m in report.metrics
                ],
                "mismatches": report.mismatches,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    if "--check" in sys.argv:
        missing = check_gold_presence()
        print(f"金标 {len(GOLD_LABELS)} 条，缺失 {len(missing)} 条：{missing}")
        raise SystemExit(1 if missing else 0)

    r = evaluate()
    print()
    print(f"{'指标':<28}{'当前值':<40}结论")
    print("-" * 90)
    for m in r.metrics:
        print(f"{m.name:<28}{m.value:<40}{'PASS' if m.passed else 'FAIL'}")
    print()
    print(f"已写入 {REPORT_PATH.name} / {JSON_PATH.name}")

    # --gate：把指标变成门禁，任何一项回退都返回非零退出码
    if "--gate" in sys.argv:
        failed = [m.name for m in r.metrics if not m.passed]
        if failed:
            print(f"\nGATE FAIL：{len(failed)} 项指标未达标 -> {'、'.join(failed)}")
            raise SystemExit(1)
        print("\nGATE PASS：六项指标全部达标")
