# -*- coding: utf-8 -*-
"""单元测试：AI 层边界（输出校验 + 失败降级）。

不联网：用 unittest.mock 替换 _call_ai。
运行：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shafe_mvp as service  # noqa: E402


class TestValidateAiText(unittest.TestCase):
    def test_normal_explanation_passes(self):
        ok, why = service.validate_ai_text(
            "这道菜偏温补，适合气虚者每周一两次。", verdict="宜", allowed_dishes={"山药鸡汤"}
        )
        self.assertTrue(ok, why)

    def test_acupoint_is_rejected(self):
        ok, why = service.validate_ai_text(
            "可以按揉足三里穴帮助消化。", verdict="宜", allowed_dishes={"山药鸡汤"}
        )
        self.assertFalse(ok)
        self.assertIn("违禁医疗词", why)

    def test_dosage_is_rejected(self):
        ok, _ = service.validate_ai_text(
            "每日用量 5 毫克即可。", verdict="宜", allowed_dishes={"山药鸡汤"}
        )
        self.assertFalse(ok)

    def test_contradiction_when_blocked(self):
        ok, why = service.validate_ai_text(
            "其实你可以吃，放心吃。", verdict="禁", allowed_dishes={"麻辣香锅"}
        )
        self.assertFalse(ok)
        self.assertIn("冲突", why)

    def test_same_sentence_ok_when_allowed(self):
        ok, why = service.validate_ai_text(
            "麻辣香锅可以吃，但别天天吃。", verdict="禁", allowed_dishes={"麻辣香锅"}
        )
        # 菜名在放行集里，但"可以吃"仍与"禁"冲突 -> 必须拒绝
        self.assertFalse(ok, why)

    def test_unknown_dish_is_rejected(self):
        ok, why = service.validate_ai_text(
            "另外推荐麻辣香锅，很下饭。", verdict="宜", allowed_dishes={"山药鸡汤"}
        )
        self.assertFalse(ok)
        self.assertIn("未放行菜名", why)

    def test_empty_is_rejected(self):
        ok, _ = service.validate_ai_text("   ", verdict="宜", allowed_dishes=set())
        self.assertFalse(ok)


@unittest.skipUnless(service.DATABASE_PATH.exists(), "缺少 food.db，请先运行 python init_db.py")
class TestAiFallback(unittest.TestCase):
    def test_ai_timeout_degrades_to_local(self):
        with mock.patch.object(service, "_call_ai", return_value=("", "AI 正在休息，请查看本地推荐。")):
            r = service.generate_diet_plan(
                "气虚", "平和", [], True, api_key="fake-key"
            )
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["recommendations"])       # 本地结果仍在
        self.assertEqual(r["ai_message"], "")
        self.assertIn("休息", r["ai_error"])

    def test_bad_ai_output_is_downgraded(self):
        with mock.patch.object(
            service, "_call_ai", return_value=("按揉足三里，每日 5 毫克。", "")
        ):
            r = service.generate_diet_plan("气虚", "平和", [], True, api_key="fake-key")
        self.assertEqual(r["ai_message"], "")
        self.assertIn("降级", r["ai_error"])

    def test_template_explanation_works_without_ai(self):
        r = service.generate_diet_plan("气虚", "平和", [], False)
        text = service.template_explanation(r)
        self.assertTrue(text)
        self.assertIn(r["recommendations"][0]["name"], text)

    def test_no_key_does_not_crash(self):
        r = service.generate_diet_plan("气虚", "平和", [], True, api_key="")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["ai_message"], "")

    def test_unknown_dish_returns_unknown(self):
        r = service.check_food("气虚", "燕麦拿铁", has_ai_access=False)
        self.assertEqual(r["status"], "unknown")

    def test_ambiguous_returns_candidates(self):
        r = service.check_food("气虚", "肉", has_ai_access=False)
        self.assertEqual(r["status"], "ambiguous")
        self.assertGreater(len(r["candidates"]), 1)

    def test_blocked_dish_is_blocked(self):
        r = service.check_food("湿热", "麻辣香锅", has_ai_access=False)
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(r["verdict"], "禁")

    def test_direct_term_block(self):
        r = service.check_food("气虚", "来点甜的", has_ai_access=False)
        self.assertEqual(r["status"], "blocked")


@unittest.skipUnless(service.DATABASE_PATH.exists(), "缺少 food.db，请先运行 python init_db.py")
class TestProvenance(unittest.TestCase):
    def test_every_dish_has_source(self):
        with sqlite3.connect(service.DATABASE_PATH) as con:
            dish = con.execute("SELECT COUNT(*) FROM Dish").fetchone()[0]
            src = con.execute("SELECT COUNT(*) FROM Dish_Source").fetchone()[0]
            missing = con.execute(
                "SELECT COUNT(*) FROM Dish d WHERE NOT EXISTS (SELECT 1 FROM Dish_Source s WHERE s.dish_id=d.id)"
            ).fetchone()[0]
        self.assertEqual(src, dish, "Dish_Source 必须一条不漏")
        self.assertEqual(missing, 0)

    def test_no_placeholder_source(self):
        with sqlite3.connect(service.DATABASE_PATH) as con:
            placeholder = con.execute(
                "SELECT COUNT(*) FROM Dish_Source WHERE source_type='待补充' OR collected_by='待补充'"
            ).fetchone()[0]
        self.assertEqual(placeholder, 0, "存在未补全的溯源记录")

    def test_wal_enabled(self):
        with sqlite3.connect(service.DATABASE_PATH) as con:
            mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.lower(), "wal")


if __name__ == "__main__":
    unittest.main(verbosity=2)
