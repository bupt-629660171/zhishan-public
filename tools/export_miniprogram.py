# -*- coding: utf-8 -*-
"""导出小程序离线数据包：菜品 + 标签 + 规则 + 限制 + 情志。

输出：
  miniprogram/data/db.json      小程序运行时读取
  miniprogram/data/expected.json  Python 引擎的判定结果（用于 JS 引擎对拍）
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "miniprogram" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DB = ROOT / "food.db"


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    import sys
    sys.path.insert(0, str(ROOT))
    from version import RULE_VERSION, TAG_VERSION

    dishes = []
    for r in con.execute("""SELECT d.id, d.name, d.property, d.explanation, d.calories,
                                   COALESCE(d.kind,'dish') AS kind FROM Dish d ORDER BY d.id"""):
        canteen = [
            {
                "location": c["location"],
                "window": c["window_name"],
                "price": c["price"],
            }
            for c in con.execute(
                "SELECT location, window_name, price FROM Canteen WHERE dish_id=?", (r["id"],)
            )
        ]
        campus = [
            c["campus"]
            for c in con.execute("SELECT campus FROM Dish_Source WHERE dish_id=?", (r["id"],))
        ]
        tags = [t["tag"] for t in con.execute("SELECT tag FROM Dish_Tag WHERE dish_id=? ORDER BY tag", (r["id"],))]
        dishes.append(
            {
                "id": r["id"],
                "name": r["name"],
                "property": r["property"] or "",
                "explanation": r["explanation"] or "",
                "calories": r["calories"],
                "kind": r["kind"],
                "canteen": canteen,
                "campus": campus,
                "tags": tags,
            }
        )

    rules: dict[str, list] = {}
    for r in con.execute(
        "SELECT constitution, code, action, tag, rationale, source_ref FROM Rules "
        "WHERE status IN ('草案','已审核') ORDER BY constitution, code"
    ):
        rules.setdefault(r["constitution"], []).append(
            {
                "code": r["code"],
                "action": r["action"],
                "tag": r["tag"],
                "rationale": r["rationale"],
                "source_ref": r["source_ref"] or "",
            }
        )

    constraints: dict[str, list[int]] = {}
    for r in con.execute("SELECT constraint_type, dish_id FROM Constraint_Rule"):
        constraints.setdefault(r["constraint_type"], []).append(r["dish_id"])

    emotions: dict[str, list[int]] = {}
    for r in con.execute("SELECT emotion, constitution, action, dish_id FROM Emotion_Rule"):
        if r["action"] == "推荐":
            emotions[str(r["dish_id"])] = emotions.get(str(r["dish_id"]), [])
            emotions[str(r["dish_id"])].append(f"{r['emotion']}|{r['constitution']}")

    db = {
        "meta": {
            "rule_version": RULE_VERSION,
            "tag_version": TAG_VERSION,
            "count": len(dishes),
        },
        "dishes": dishes,
        "rules": rules,
        "constraints": constraints,
        "emotions": emotions,
    }

    # Python 侧判定，作为 JS 对拍基准
    import rule_engine as engine

    expected = {}
    for con_name in ("气虚", "湿热"):
        expected[con_name] = {}
        for d in dishes:
            if d["kind"] != "dish":
                continue
            v = engine.evaluate({"id": d["id"], "name": d["name"]}, con_name, tags=set(d["tags"]))
            expected[con_name][d["name"]] = v["verdict"]

    (OUT_DIR / "db.json").write_text(
        json.dumps(db, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (ROOT / "tools" / "_expected.json").write_text(
        json.dumps(expected, ensure_ascii=False), encoding="utf-8"
    )

    # 小程序不能 require JSON，另存一份 db.js
    (OUT_DIR / "db.js").write_text(
        "module.exports = " + json.dumps(db, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )

    size = (OUT_DIR / "db.json").stat().st_size / 1024
    print(f"导出 {len(dishes)} 道菜 / {sum(len(v) for v in rules.values())} 条规则 → db.json {size:.0f} KB")
    con.close()


if __name__ == "__main__":
    main()
