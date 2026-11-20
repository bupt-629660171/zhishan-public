# -*- coding: utf-8 -*-
"""体质倾向自评（简化版，非诊断）。

设计取舍
--------
完整量表是《中医体质分类与判定》(ZYYXH/T157-2009)，60 个条目、约 10 分钟，
且给出的是"体质判定"结论。本项目只做饮食参考，因此：

  · 只保留每个体质的 1~2 个代表性条目（共 11 题，约 1 分钟）；
  · 结果表述为"倾向"，不写"判定"；
  · 只有气虚、湿热两种能继续给食养建议，其余明确返回"暂不支持"。

计分沿用标准公式，便于对照：
    转化分 = [(原始分 - 条目数) / (条目数 × 4)] × 100
"""

from __future__ import annotations

# 五个等级，与标准量表的 5 级评分一致
LEVELS = ["没有", "很少", "有时", "经常", "总是"]
LEVEL_SCORE = {name: i + 1 for i, name in enumerate(LEVELS)}

SUPPORTED = ("气虚", "湿热")

# 条目：id, 体质, 问题, 是否反向计分
# 反向计分用于"平和"这类正向表述（分越高越平和，不需要反向），此处保留字段备用。
QUESTIONS: list[dict] = [
    {"id": "qi_1", "type": "气虚", "text": "你容易疲乏、睡够了也不解乏吗？"},
    {"id": "qi_2", "type": "气虚", "text": "你说话声音偏低，或懒得说话吗？"},
    {"id": "damp_1", "type": "湿热", "text": "你面部或鼻部容易出油、长痘吗？"},
    {"id": "damp_2", "type": "湿热", "text": "你口苦，或嘴里发黏、不清爽吗？"},
    {"id": "yang_1", "type": "阳虚", "text": "你比一般人怕冷（冬天、空调房）吗？"},
    {"id": "yin_1", "type": "阴虚", "text": "你手脚心发热，或经常口干咽干吗？"},
    {"id": "tan_1", "type": "痰湿", "text": "你感到身体沉重，或腹部松软肥满吗？"},
    {"id": "xue_1", "type": "血瘀", "text": "你皮肤容易出现淤青，或面色偏暗吗？"},
    {"id": "yu_1", "type": "气郁", "text": "你容易闷闷不乐、情绪低落吗？"},
    {"id": "te_1", "type": "特禀", "text": "你容易过敏（花粉、食物、季节变化）吗？"},
    {"id": "ping_1", "type": "平和", "text": "你精力充沛，睡眠和食欲都比较稳定吗？"},
]

TYPES = ["平和", "气虚", "阳虚", "阴虚", "痰湿", "湿热", "血瘀", "气郁", "特禀"]


def score(answers: dict[str, str]) -> dict[str, float]:
    """answers: {题目 id: 等级名}；未作答按"没有"计。

    返回 {体质: 转化分 0~100}。条目越多的体质，分数越平滑。
    """
    totals: dict[str, list[int]] = {}
    for q in QUESTIONS:
        raw = LEVEL_SCORE.get(answers.get(q["id"], "没有"), 1)
        totals.setdefault(q["type"], []).append(raw)

    out: dict[str, float] = {}
    for t, values in totals.items():
        n = len(values)
        raw_sum = sum(values)
        out[t] = round(((raw_sum - n) / (n * 4)) * 100, 1)
    for t in TYPES:
        out.setdefault(t, 0.0)
    return out


def classify(scores: dict[str, float]) -> dict:
    """把分数翻译成"倾向 + 是否可给建议"。

    阈值沿用标准的 40 / 30 两档，但表述为"明显倾向 / 轻度倾向"，避免"判定"。
    """
    ranked = sorted(
        ((t, s) for t, s in scores.items() if t != "平和"), key=lambda kv: kv[1], reverse=True
    )
    top_type, top_score = ranked[0] if ranked else ("", 0.0)

    if scores.get("平和", 0) >= 60 and all(s < 30 for _, s in ranked):
        return {
            "type": "平和",
            "score": scores["平和"],
            "level": "较平稳",
            "supported": False,
            "note": "各方面比较平稳，按日常均衡饮食即可。",
        }

    if top_score < 30:
        return {
            "type": "不明显",
            "score": top_score,
            "level": "不明显",
            "supported": False,
            "note": "没有明显倾向，按日常均衡饮食即可。",
        }

    level = "明显倾向" if top_score >= 40 else "轻度倾向"
    supported = top_type in SUPPORTED
    also = [t for t, s in ranked[1:] if s >= 30 and top_score - s < 10]
    return {
        "type": top_type,
        "score": top_score,
        "level": level,
        "supported": supported,
        "also": also,
        "note": (
            f"可以按{top_type}的食养建议挑选菜品。"
            if supported
            else f"{top_type}类暂未收录规则，暂时不能给针对性建议；可以按通用少油少盐的原则选，"
            "有明显不适请咨询专业人士。"
        ),
    }


def answered(answers: dict[str, str]) -> int:
    return sum(1 for q in QUESTIONS if answers.get(q["id"]))


def result_text(result: dict) -> str:
    if result["type"] in ("不明显", "平和"):
        return f"体质倾向：{result['level']}。{result['note']}"
    extra = ""
    if result.get("also"):
        extra = f"同时{'、'.join(result['also'])}也偏高，属于混合倾向，建议以饮食均衡为主。"
    return (
        f"体质倾向：{result['type']}（{result['level']}，参考分 {result['score']:.0f}）。"
        f"{result['note']}{extra}"
    )
