# -*- coding: utf-8 -*-
"""文案—判定一致性检查。

问题：文案写"湿热者适量"，判定却是「禁」，用户看到红标会认为系统自相矛盾
（见 docs/标签复核_20261118.md 问题 2）。

做法：只检查**明确指向某体质**的短句（"气虚者…" / "湿热者…"），避免把
"气虚可少量、湿热少吃"这类同时描述两种体质的文案误判。

规则：
  - 该体质判「禁」，短句里出现 可食/可吃/放心吃/适量/为宜/推荐 → 矛盾
  - 该体质判「宜」，短句里出现 忌/禁/不宜/避免 → 矛盾
「慎」档不查：慎本身就是"可以但注意"，与两类措辞都不冲突。
"""

from __future__ import annotations

import re
import sqlite3

import rule_engine as engine

CONSTITUTIONS = engine.SUPPORTED_CONSTITUTIONS

# 指向体质的短句：气虚/湿热 + 最多 10 字
CLAUSE = re.compile(r"(气虚|湿热)(?:者|体质|的人)?([^，。；、,;]{0,10})")
POSITIVE = ("可食", "可吃", "放心吃", "适量", "为宜", "推荐", "可以吃")
NEGATIVE = ("忌", "禁食", "不宜", "避免", "不要吃")


def find_mismatches(db_path=None) -> list[dict]:
    """返回 [{dish, constitution, verdict, clause, problem}]。"""
    path = db_path or engine.DATABASE_PATH
    rules = {c: engine.load_rules(c) for c in CONSTITUTIONS}

    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        dishes = [dict(r) for r in con.execute(
            "SELECT id, name, explanation FROM Dish"
        )]
        tags: dict[int, set[str]] = {}
        for r in con.execute("SELECT dish_id, tag FROM Dish_Tag"):
            tags.setdefault(r["dish_id"], set()).add(r["tag"])

    out: list[dict] = []
    for d in dishes:
        text = d["explanation"] or ""
        if not text:
            continue
        for con_name, rules_for in rules.items():
            verdict = engine.evaluate(
                {"id": d["id"], "name": d["name"]}, con_name,
                rules=rules_for, tags=tags.get(d["id"], set()),
            )["verdict"]
            for m in CLAUSE.finditer(text):
                if m.group(1) != con_name:
                    continue
                clause = m.group(0)
                if verdict == "禁" and any(w in clause for w in POSITIVE):
                    out.append({"dish": d["name"], "constitution": con_name,
                                "verdict": verdict, "clause": clause,
                                "problem": "判禁但文案说可以吃"})
                elif verdict == "宜" and any(w in clause for w in NEGATIVE):
                    out.append({"dish": d["name"], "constitution": con_name,
                                "verdict": verdict, "clause": clause,
                                "problem": "判宜但文案说忌讳"})
    return out


if __name__ == "__main__":
    items = find_mismatches()
    print(f"文案与判定矛盾：{len(items)} 条")
    for x in items:
        print(f"  {x['dish']}（{x['constitution']}={x['verdict']}）：{x['clause']} → {x['problem']}")
