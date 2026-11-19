# -*- coding: utf-8 -*-
"""单元测试：规则引擎与检索层（rule_engine.py）。

需要先用 python init_db.py 建好 food.db。
运行：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rule_engine as engine  # noqa: E402


@unittest.skipUnless(engine.DATABASE_PATH.exists(), "缺少 food.db，请先运行 python init_db.py")
class TestEvaluate(unittest.TestCase):
    def _dish(self, name: str) -> dict:
        import sqlite3

        with sqlite3.connect(engine.DATABASE_PATH) as con:
            row = con.execute("SELECT id, name FROM Dish WHERE name=?", (name,)).fetchone()
        self.assertIsNotNone(row, f"库内缺少菜品 {name}")
        return {"id": row[0], "name": row[1]}

    def test_qi_deficiency_blocks_spicy(self):
        v = engine.evaluate(self._dish("麻辣香锅"), "气虚")
        self.assertEqual(v["verdict"], "禁")
        self.assertTrue(any(e["rule_id"] == "QX_NO_SPICY" for e in v["evidence"]))

    def test_damp_heat_blocks_fried(self):
        v = engine.evaluate(self._dish("脆皮鸡饭"), "湿热")
        self.assertEqual(v["verdict"], "禁")

    def test_qi_deficiency_allows_tonify(self):
        v = engine.evaluate(self._dish("山药鸡汤"), "气虚")
        self.assertIn(v["verdict"], ("宜", "慎"))
        self.assertTrue(any(e["action"] == "宜" for e in v["evidence"]))

    def test_cold_blocks_for_qi_only(self):
        qi = engine.evaluate(self._dish("西瓜"), "气虚")
        damp = engine.evaluate(self._dish("西瓜"), "湿热")
        self.assertEqual(qi["verdict"], "禁")
        self.assertNotEqual(damp["verdict"], "禁")

    def test_neutral_dish_is_traceable(self):
        v = engine.evaluate(self._dish("菠菜鸡蛋"), "气虚")
        self.assertEqual(v["verdict"], "宜")
        self.assertEqual(v["evidence"][0]["rule_id"], "NEUTRAL")
        self.assertTrue(v["evidence"][0]["source_ref"])

    def test_unsupported_constitution(self):
        v = engine.evaluate(self._dish("米饭"), "阳虚")
        self.assertEqual(v["verdict"], "未知")

    def test_every_verdict_has_traceable_evidence(self):
        v = engine.evaluate(self._dish("黄焖鸡米饭"), "气虚")
        for e in v["evidence"]:
            for key in ("rule_id", "source_ref", "rule_version", "rationale"):
                self.assertTrue(e[key], f"证据缺少 {key}")


@unittest.skipUnless(engine.DATABASE_PATH.exists(), "缺少 food.db，请先运行 python init_db.py")
class TestSearch(unittest.TestCase):
    def test_exact_name(self):
        r = engine.search_dish("清蒸鱼")
        self.assertEqual(r["status"], "hit")
        self.assertEqual(r["matched_by"], "exact")

    def test_alias(self):
        r = engine.search_dish("香锅")
        self.assertEqual(r["status"], "hit")
        self.assertEqual(r["candidates"], ["麻辣香锅"])
        self.assertEqual(r["matched_by"], "alias")

    def test_single_char_is_ambiguous(self):
        r = engine.search_dish("肉")
        self.assertEqual(r["status"], "ambiguous")
        self.assertGreater(len(r["candidates"]), 1)

    def test_miss(self):
        r = engine.search_dish("燕麦拿铁")
        self.assertEqual(r["status"], "miss")

    def test_empty(self):
        self.assertEqual(engine.search_dish("")["status"], "miss")


@unittest.skipUnless(engine.DATABASE_PATH.exists(), "缺少 food.db，请先运行 python init_db.py")
class TestPlan(unittest.TestCase):
    def test_constitution_changes_ban_set(self):
        s = engine.sensitivity()
        self.assertGreater(s["气虚禁"], 0)
        self.assertGreater(s["湿热禁"], 0)
        # 两侧禁集大小可能恰好相同，关键是"禁的菜不一样"
        self.assertTrue(s["仅气虚禁"], "气虚应有湿热不禁的菜")
        self.assertTrue(s["仅湿热禁"], "湿热应有气虚不禁的菜")
        self.assertGreater(s["判定不同"], 0)

    def test_plan_has_trace_fields(self):
        r = engine.plan("气虚", seed=1)
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["recommendations"])
        for d in r["recommendations"]:
            for key in ("rule_id", "source_ref", "rule_version", "evidence", "verdict"):
                self.assertIn(key, d)
                self.assertTrue(d[key] != "" if key != "evidence" else isinstance(d[key], list))

    def test_yi_sorted_first(self):
        r = engine.plan("气虚", seed=3)
        verdicts = [d["verdict"] for d in r["recommendations"]]
        self.assertNotIn(verdicts[0], ("禁",))
        self.assertEqual(verdicts[0], "宜")

    def test_vegetarian_constraint_removes_meat(self):
        r = engine.plan("气虚", constraints={"素食"}, seed=1)
        for d in r["recommendations"]:
            self.assertFalse(any(w in d["name"] for w in ("鸡", "牛", "猪", "鱼", "虾", "肉")))

    def test_campus_filter(self):
        """按校区筛选后，结果只能来自该校区。"""
        r = engine.plan("气虚", campus="通用", limit=5, seed=1)
        self.assertTrue(r["recommendations"])
        for d in r["recommendations"]:
            self.assertTrue(d["canteen_info"].startswith("全国通用"), d["canteen_info"])

    def test_vegetarian_split(self):
        """纯素不含蛋奶；蛋奶素允许蛋奶。"""
        pure = engine.plan("气虚", constraints={"素食"}, limit=300, seed=1)
        lacto = engine.plan("气虚", constraints={"蛋奶素"}, limit=300, seed=1)
        pure_names = [d["name"] for d in pure["recommendations"]]
        self.assertFalse([n for n in pure_names if any(x in n for x in ("蛋", "奶"))])
        lacto_names = [d["name"] for d in lacto["recommendations"]]
        self.assertTrue([n for n in lacto_names if any(x in n for x in ("蛋", "奶"))])

    def test_empty_result_when_over_constrained(self):
        r = engine.plan("气虚", constraints={"素食", "无麸质", "不吃辣", "不吃苦味"}, seed=1)
        self.assertIn(r["status"], ("ok", "empty"))


if __name__ == "__main__":
    unittest.main(verbosity=2)


@unittest.skipUnless(engine.DATABASE_PATH.exists(), "缺少 food.db，请先运行 python init_db.py")
class TestCopyConsistency(unittest.TestCase):
    """文案写"可以适量"却判「禁」，用户会认为系统自相矛盾。"""

    def test_no_contradiction_between_copy_and_verdict(self):
        import consistency

        bad = consistency.find_mismatches()
        self.assertEqual(
            bad, [], f"文案与判定矛盾：{[(x['dish'], x['constitution'], x['clause']) for x in bad]}"
        )


@unittest.skipUnless(engine.DATABASE_PATH.exists(), "缺少 food.db，请先运行 python init_db.py")
class TestAlternatives(unittest.TestCase):
    """每道推荐都要有可替换项，且替代品不能是被拦的菜。"""

    def test_recommendations_have_safe_alternatives(self):
        r = engine.plan("气虚", seed=7)
        self.assertTrue(r["recommendations"])
        for d in r["recommendations"]:
            self.assertIn("alternatives", d)
            self.assertLessEqual(len(d["alternatives"]), 2)
            for a in d["alternatives"]:
                self.assertNotEqual(a["name"], d["name"])
                self.assertNotEqual(a["verdict"], "禁", "替代品不能是判禁的菜")
