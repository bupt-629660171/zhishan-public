# -*- coding: utf-8 -*-
"""单元测试：标签派生层（tags.py）。

只测纯函数，不碰数据库，保证"改关键词不会悄悄改变语义"。
运行：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tags  # noqa: E402


class TestDeriveTags(unittest.TestCase):
    def test_spicy_and_greasy(self):
        got = tags.derive_tags("麻辣香锅", "辛辣、重油", "辛温助热，油腻生湿，湿热体质应少吃。")
        self.assertIn("spicy", got)
        self.assertIn("greasy", got)

    def test_bland_dish_has_no_pungent_tag(self):
        got = tags.derive_tags("清炒时蔬", "清淡、少油", "蔬菜清淡易消化，可帮助减少油腻和积热。")
        self.assertIn("light", got)
        self.assertNotIn("spicy", got)
        self.assertNotIn("greasy", got)  # "少油" 不能算重油

    def test_negation_window(self):
        # "中和猪肉的油腻" 出现在解释里，但属性是"温润易消化"，不应判为重油
        got = tags.derive_tags(
            "猪肉白萝卜包子", "温润易消化", "萝卜下气消食，中和猪肉的油腻，适合做主食。"
        )
        self.assertNotIn("greasy", got)

    def test_garlic_paste_is_mild_not_spicy(self):
        got = tags.derive_tags("蒜蓉西兰花", "清淡平性", "高纤维，抗氧化，清淡少油，非常健康，减脂首选。")
        self.assertIn("mild_spicy", got)
        self.assertNotIn("spicy", got)

    def test_empty_falls_back_to_neutral(self):
        self.assertEqual(tags.derive_tags("", "", ""), {"neutral"})

    def test_unknown_text_falls_back_to_neutral(self):
        self.assertEqual(tags.derive_tags("菠菜鸡蛋", "平性养阴", ""), {"neutral"})

    def test_high_sugar_cake(self):
        got = tags.derive_tags("蛋糕", "甜腻生湿", "糖分过高，滋腻脾胃，加重湿热，尽量少吃。")
        self.assertIn("sweet", got)
        self.assertIn("rich", got)

    def test_high_fat_shaomai(self):
        got = tags.derive_tags("蛋黄烧卖", "高脂高碳", "糯米+蛋黄+油脂，极难消化，易生湿滞气。")
        self.assertIn("rich", got)

    def test_every_tag_has_label_and_rationale(self):
        for d in tags.TAG_DEFS:
            self.assertTrue(tags.tag_label(d.tag))
            self.assertTrue(tags.tag_rationale(d.tag))


if __name__ == "__main__":
    unittest.main(verbosity=2)
