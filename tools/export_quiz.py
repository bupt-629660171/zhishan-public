# -*- coding: utf-8 -*-
"""把体质自评题库导出给小程序，并生成对拍基准。

输出：
  miniprogram/data/quiz.js        题库 + 等级（构建时生成，勿手改）
  tools/_quiz_expected.json       Python 评分结果（用于 JS 对拍）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import constitution_quiz as quiz  # noqa: E402


def main() -> None:
    payload = {
        "levels": quiz.LEVELS,
        "types": quiz.TYPES,
        "supported": list(quiz.SUPPORTED),
        "questions": [
            {"id": q["id"], "type": q["type"], "text": q["text"]}
            for q in quiz.QUESTIONS
        ],
    }

    # 几组代表性作答，作为 JS 对拍基准
    fixtures = [
        {},
        {"qi_1": "经常", "qi_2": "经常"},
        {"damp_1": "总是", "damp_2": "经常"},
        {"yang_1": "经常", "qi_1": "有时"},
        {"qi_1": "有时", "damp_1": "有时"},
        {"ping_1": "总是"},
    ]
    expected = []
    for answers in fixtures:
        scores = quiz.score(answers)
        result = quiz.classify(scores)
        expected.append(
            {
                "answers": answers,
                "scores": scores,
                "type": result["type"],
                "level": result["level"],
                "supported": result["supported"],
            }
        )

    out = ROOT / "miniprogram" / "data" / "quiz.js"
    out.write_text(
        "module.exports = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    (ROOT / "tools" / "_quiz_expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"导出题目 {len(payload['questions'])} 道 → quiz.js")


if __name__ == "__main__":
    main()
