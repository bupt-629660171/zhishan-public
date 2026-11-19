# -*- coding: utf-8 -*-
"""知源智膳 · 菜品属性标签体系。

为什么要有这一层：
    原实现直接用 `forbidden_words.txt` 里的十个词去 `in` 菜品属性文本，
    这既不是"体质规则"，也说不清"哪条规则拦了哪道菜"。

    现在把这一步拆成可审计的两段：
        1) 派生：菜品文本（name + property + explanation）→ 标准化标签（本文件）
        2) 判定：标签 + 体质 → 规则（rules.csv / RuleEngine）

    第 1 段是"数据加工"，可以人工逐条复核；
    第 2 段是"医学规则"，交给导师审核。

标签必须是"食物属性"，不是"体质"——体质只在规则里出现，
这样同一道菜在不同体质下才能得出不同结论。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TagDef:
    tag: str          # 标签名（英文短码，入库稳定）
    label: str        # 中文名（展示用）
    pattern: str      # 在 name+property+explanation 上匹配的正则
    rationale: str    # 这个标签在中医上意味着什么

    def compile(self) -> re.Pattern[str]:
        return re.compile(self.pattern)


TAG_DEFS: tuple[TagDef, ...] = (
    TagDef(
        "spicy", "辛辣",
        r"辛辣|麻辣|辛温|辛热|大辛|酸辣|椒麻|藤椒|辣椒|辣子|芥末|蒜苗",
        "辛温发散，易耗气伤津、助热生火",
    ),
    TagDef(
        "fried", "油炸煎烤",
        r"油炸|酥肉|炸|煎|烤|熏|铁板|油条|麻花",
        "高温油脂，性偏燥热，难消化，易生痰湿",
    ),
    TagDef(
        "greasy", "重油肥腻",
        r"重油|多油|油腻|肥腻|肥牛|五花|腊肠|肘花|肥肠|油脂|高脂",
        "油脂厚重，碍脾胃运化，易生湿生痰",
    ),
    TagDef(
        "rich", "滋腻",
        r"滋腻|黏腻|粘腻|甜腻|甘温|碍胃|难消化|不易消化",
        "滋腻碍胃，脾虚者运化无力",
    ),
    TagDef(
        "sweet", "甜腻高糖",
        r"高糖|高糖高油|甜腻|糖分|蜜汁|蛋糕|蛋挞|甜品|含糖",
        "甘甜生湿助痰，多食困脾",
    ),
    TagDef(
        "mild_spicy", "微辛",
        r"微辣|微辛|略辛|蒜蓉|青椒|藤椒|黑椒|孜然|胡椒",
        "辛味轻微，一般不构成主要禁忌",
    ),
    TagDef(
        "dry_heat", "温燥",
        r"温燥|燥热|偏燥|大燥|上火|燥火|辛燥|助热",
        "温燥伤津，易化热上火",
    ),
    TagDef(
        "heat", "大热",
        r"大热|大辛大热|辛热|极热|火毒",
        "大热之性，助火生毒",
    ),
    TagDef(
        "cold", "寒凉",
        r"寒凉|大寒|微寒|生冷|冷饮|寒性|(?:性|味)寒|(?:^|｜)寒",
        "寒凉伤脾阳，脾虚者易腹泻、食欲下降",
    ),
    TagDef(
        "tonify", "温补",
        r"温补|滋补|补气|益气|健脾|养胃|温润|温中|补脾|补虚",
        "温补脾胃、扶助正气，气虚者相宜",
    ),
    TagDef(
        "light", "清淡",
        r"清淡|少油|低脂|低卡|凉润|清润|清热|利水|去火|生津|软坚",
        "清淡少油、清利之性，湿热者相宜",
    ),
    TagDef(
        "phlegm", "发物",
        r"发物|海鲜|虾|蟹|螺|贝|鹅肉|羊肉|菌|笋|韭菜",
        "发物易动风生痰、诱发宿疾，湿热及过敏体质慎",
    ),
    TagDef(
        "neutral", "平性",
        r"^$",  # 不靠关键字触发，由 derive_tags 兜底添加
        "未命中任何偏性，按平性处理",
    ),
    TagDef(
        "moderate", "适量",
        r"适量|为宜|适中|可食|少食|少吃",
        "性质平和，可适量，不宜过量",
    ),
    TagDef(
        "carb", "主食碳水",
        r"米饭|面食|饼|馒头|米粉|米线|包子|饺子|馄饨|粥|发糕|杂粮|土豆|玉米",
        "主食类，提供能量，需注意总量与搭配",
    ),
)

# 否定上下文：出现这些片段时，对应的正向证据不计入
# 例：`greasy` 的"重油"不应在"少油"里命中；"解腻"也不等于"油腻"
NEGATIONS: dict[str, tuple[str, ...]] = {
    "greasy": ("少油", "不油", "低脂", "解腻", "去腻", "不腻", "易消化"),
    "sweet": ("低糖", "少糖", "无糖", "升糖", "含糖量低"),
    "cold": ("不寒", "性平"),
    "dry_heat": ("不上火", "不燥", "不易上火", "不易生热"),
    "fried": ("非油炸", "不炸"),
}

_COMPILED = {d.tag: d.compile() for d in TAG_DEFS}
_BY_TAG = {d.tag: d for d in TAG_DEFS}


def tag_label(tag: str) -> str:
    d = _BY_TAG.get(tag)
    return d.label if d else tag


def tag_rationale(tag: str) -> str:
    d = _BY_TAG.get(tag)
    return d.rationale if d else ""


def derive_tags(*texts: str) -> set[str]:
    """从菜品文本派生标签集合（不读写数据库，纯函数，便于单测）。"""
    # 用分隔符拼接，避免字段边界处拼出伪词（如"温甘"+"温中"→"甘温"）
    combined = "｜".join(t or "" for t in texts)
    if not combined:
        return {"neutral"}

    tags: set[str] = set()
    for tag, pattern in _COMPILED.items():
        for match in pattern.finditer(combined):
            window = combined[max(0, match.start() - 24): match.end() + 24]
            if any(neg in window for neg in NEGATIONS.get(tag, ())):
                continue
            tags.add(tag)
            break
    if not tags:
        tags.add("neutral")
    return tags
