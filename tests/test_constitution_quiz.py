# -*- coding: utf-8 -*-
"""体质自评模块的单元测试。"""
import unittest

import constitution_quiz as quiz


class TestScoring(unittest.TestCase):
    def test_all_none_is_zero(self):
        scores = quiz.score({})
        self.assertEqual(len(scores), 9)
        self.assertTrue(all(v == 0 for v in scores.values()))

    def test_single_type_high(self):
        answers = {"qi_1": "经常", "qi_2": "经常"}
        scores = quiz.score(answers)
        self.assertGreater(scores["气虚"], 60)
        self.assertEqual(scores["湿热"], 0)

    def test_formula_matches_standard(self):
        # 两个条目，原始分 3+4=7 → [(7-2)/(2*4)]*100 = 62.5
        scores = quiz.score({"qi_1": "有时", "qi_2": "经常"})
        self.assertAlmostEqual(scores["气虚"], 62.5, places=1)

    def test_partial_answers_treated_as_none(self):
        # 只答一题"总是"(5)，另一题按"没有"(1) 计：[(6-2)/8]*100 = 50
        scores = quiz.score({"qi_1": "总是"})
        self.assertAlmostEqual(scores["气虚"], 50.0, places=1)

    def test_answered_count(self):
        self.assertEqual(quiz.answered({}), 0)
        self.assertEqual(quiz.answered({"qi_1": "有时", "damp_1": "很少"}), 2)


class TestClassify(unittest.TestCase):
    def test_supported_type(self):
        scores = {t: 0 for t in quiz.TYPES}
        scores["气虚"] = 70
        result = quiz.classify(scores)
        self.assertEqual(result["type"], "气虚")
        self.assertTrue(result["supported"])
        self.assertEqual(result["level"], "明显倾向")

    def test_unsupported_type(self):
        scores = {t: 0 for t in quiz.TYPES}
        scores["阳虚"] = 70
        result = quiz.classify(scores)
        self.assertEqual(result["type"], "阳虚")
        self.assertFalse(result["supported"])
        self.assertIn("暂未收录", result["note"])

    def test_mild_tendency(self):
        scores = {t: 0 for t in quiz.TYPES}
        scores["湿热"] = 35
        result = quiz.classify(scores)
        self.assertEqual(result["level"], "轻度倾向")

    def test_unclear_when_low(self):
        scores = {t: 10 for t in quiz.TYPES}
        result = quiz.classify(scores)
        self.assertEqual(result["type"], "不明显")
        self.assertFalse(result["supported"])

    def test_balanced(self):
        scores = {t: 0 for t in quiz.TYPES}
        scores["平和"] = 80
        result = quiz.classify(scores)
        self.assertEqual(result["type"], "平和")
        self.assertFalse(result["supported"])

    def test_mixed_tendency_flagged(self):
        scores = {t: 0 for t in quiz.TYPES}
        scores["气虚"] = 62
        scores["阳虚"] = 60
        result = quiz.classify(scores)
        self.assertIn("阳虚", result["also"])


if __name__ == "__main__":
    unittest.main()
