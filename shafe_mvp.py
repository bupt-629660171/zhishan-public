# -*- coding: utf-8 -*-
"""知源智膳 · 应用服务层（Streamlit 与评测脚本共用的唯一入口）。

架构边界：
    rule_engine.py   ← 确定性规则判定（本地 SQLite，不联网）
    shafe_mvp.py     ← 本文件：编排「检索 → 规则判定 → 大模型解释」，只做解释不碰判定
    app.py           ← 纯前端展示

大模型拿不到"能不能吃"的判断权：它只在 verdict 已定之后，把证据翻译成人话。
"""

from __future__ import annotations

from contextlib import closing

import os
from pathlib import Path
from typing import Callable, Iterable

import rule_engine as engine
from version import DISCLAIMER, RULE_VERSION

try:
    from openai import APIConnectionError, APITimeoutError, OpenAI
except ImportError:  # 未安装 openai 时仍可使用全部本地功能
    OpenAI = None
    APIConnectionError = APITimeoutError = Exception


DATABASE_PATH = engine.DATABASE_PATH
DEFAULT_BASE_URL = os.getenv("ZY_LLM_BASE_URL", "https://myai.bupt.edu.cn/llm-gw/v1")
DEFAULT_MODEL = os.getenv("ZY_LLM_MODEL", "qwen3.8-27b")

ProgressCallback = Callable[[str, str], None]

# 口语直判：不查库也能确定的强信号
DIRECT_BLOCK_TERMS = {
    "甜的": "高糖甜食不属于本系统的优先推荐，建议选择低糖、清淡的具体菜品。",
    "甜食": "高糖甜食不属于本系统的优先推荐，建议选择低糖、清淡的具体菜品。",
    "炸的": "油炸食物油脂较高，气虚或湿热体质均不建议作为日常首选。",
}


def _emit(callback: ProgressCallback | None, level: str, message: str) -> None:
    if callback:
        callback(level, message)


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _normalise_constraints(constraints: Iterable[str] | str | None) -> set[str]:
    if isinstance(constraints, str):
        constraints = [constraints]
    return {_safe_text(item) for item in (constraints or []) if _safe_text(item)}


# ------------------------------------------------------------------ 大模型层
def _create_client(api_key: str, base_url: str):
    if OpenAI is None:
        raise RuntimeError("未安装 openai 依赖")
    return OpenAI(api_key=api_key, base_url=base_url or DEFAULT_BASE_URL, timeout=15.0, max_retries=1)


def _call_ai(
    *,
    api_key: str,
    prompt: str,
    system_prompt: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
) -> tuple[str, str]:
    """返回 (AI 文本, 友好错误信息)；网络失败绝不向外抛异常。"""
    if not api_key:
        return "", "未提供 API Key，已仅展示本地推荐。"
    try:
        client = _create_client(api_key, base_url)
        response = client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        content = _safe_text(response.choices[0].message.content)
        return (content, "") if content else ("", "AI 暂未返回内容，请查看本地推荐。")
    except (APITimeoutError, APIConnectionError, TimeoutError):
        return "", "AI 正在休息，请查看本地推荐。"
    except Exception:
        return "", "AI 正在休息，请查看本地推荐。"


EXPLAIN_SYSTEM_PROMPT = (
    "你是谨慎的中医食养辅助解释器。规则引擎已经给出「能不能吃」的结论，"
    "你只能解释理由、把话说得温和易懂，绝不能新增菜品、改变结论、"
    "也不能作疾病诊断、疗效保证或建议替代就医。"
)

# AI 输出后校验：宁可降级，也不让模型绕过规则层
AI_FORBIDDEN_TERMS = (
    "穴位", "按揉", "针刺", "艾灸", "针灸", "推拿", "刮痧",
    "剂量", "毫克", "克数", "处方", "服药", "用药", "疗程",
    "根治", "治愈", "包治", "疗效保证", "替代就医",
)
# 判定为"禁"时，输出里出现这些词即视为推翻规则
CONTRADICT_WHEN_BLOCKED = ("可以吃", "能吃", "放心吃", "建议食用", "推荐食用", "不妨吃")


def validate_ai_text(
    text: str, *, verdict: str, allowed_dishes: set[str]
) -> tuple[bool, str]:
    """校验大模型输出是否越界。返回 (是否通过, 不通过原因)。

    三条硬规则：
      1. 不得出现穴位/剂量/处方等医疗行为词；
      2. 判定为"禁"时不得出现"可以吃"这类反转表述；
      3. 不得出现未被规则放行的菜名（防止模型私自加菜）。
    """
    body = (text or "").strip()
    if not body:
        return False, "AI 输出为空"

    for term in AI_FORBIDDEN_TERMS:
        if term in body:
            return False, f"AI 输出含违禁医疗词「{term}」"

    if verdict == "禁":
        for term in CONTRADICT_WHEN_BLOCKED:
            if term in body:
                return False, f"AI 输出与「禁」结论冲突：「{term}」"

    outer = body
    for name in allowed_dishes:
        outer = outer.replace(name, "")
    # 放行菜名剔除后，若仍出现库内其它菜名，说明模型私自加菜
    for name in _all_dish_names():
        if len(name) >= 3 and name in outer:
            return False, f"AI 输出出现未放行菜名「{name}」"

    return True, ""


def _all_dish_names() -> list[str]:
    import sqlite3

    try:
        with closing(sqlite3.connect(DATABASE_PATH)) as con:
            return [r[0] for r in con.execute("SELECT name FROM Dish")]
    except sqlite3.Error:
        return []


def _explain_plan(result: dict, api_key: str, base_url: str, model: str) -> tuple[str, str]:
    dishes = "\n".join(
        f"- {d['name']}｜判定：{d['verdict']}｜命中规则：{d['rule_id']}｜依据：{d['rationale']}"
        for d in result["recommendations"]
    )
    prompt = f"""
体质：{result['constitution']}
用户限制：{'、'.join(result.get('constraints') or []) or '无'}
规则引擎已通过的菜品：
{dishes}

请为每道菜写不超过 50 字的温和解释，只复述上面的依据，不得改变判定、不得新增菜品。
""".strip()
    text, err = _call_ai(
        api_key=api_key, prompt=prompt, system_prompt=EXPLAIN_SYSTEM_PROMPT,
        base_url=base_url, model=model,
    )
    if not text:
        return "", err

    allowed = {d["name"] for d in result["recommendations"]}
    ok, reason = validate_ai_text(text, verdict="宜", allowed_dishes=allowed)
    if not ok:
        return "", f"{reason}，已降级为本地解释。"
    return text, ""


# ------------------------------------------------------------------ 公开 API
def generate_diet_plan(
    constitution: str,
    emotion: str = "平和",
    constraints: Iterable[str] | str | None = None,
    has_ai_access: bool = False,
    *,
    api_key: str = "",
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    progress_callback: ProgressCallback | None = None,
    seed: int | None = None,
    campus: str | None = None,
) -> dict:
    """生成方案：本地规则判定 → （可选）AI 解释。"""
    constitution = _safe_text(constitution)
    constraint_set = _normalise_constraints(constraints)
    _emit(progress_callback, "info", "🔍 正在检索菜品库并执行体质规则判定...")

    result = engine.plan(constitution, constraints=constraint_set, limit=3, seed=seed, campus=campus)
    result["emotion"] = _safe_text(emotion)
    result["ai_message"] = ""
    result["ai_error"] = ""

    if result.get("status") == "error":
        return result
    if result.get("status") == "empty":
        _emit(progress_callback, "warning", "⚠️ 严格过滤后没有符合条件的菜品。")
        return result

    _emit(
        progress_callback,
        "success",
        f"✅ 体质规则已拦截 {result['blocked_count']} 道，剩余 {result['remaining_count']} 道候选。",
    )
    if has_ai_access and api_key and result["recommendations"]:
        _emit(progress_callback, "info", "🤖 正在呼叫大模型生成受约束解释（不参与判定）...")
        result["ai_message"], result["ai_error"] = _explain_plan(result, api_key, base_url, model)
        _emit(
            progress_callback,
            "success" if result["ai_message"] else "warning",
            "✅ AI 解释生成完成。" if result["ai_message"] else f"⚠️ {result['ai_error']}",
        )
    return result


def check_food(
    constitution: str,
    dish: str,
    *,
    api_key: str = "",
    has_ai_access: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """查询单道菜：口语直判 → 菜名检索（精确/别名/子串，歧义则列候选）→ 规则判定 → AI 解释。"""
    constitution = _safe_text(constitution)
    raw = _safe_text(dish)
    if not raw:
        return {"status": "error", "message": "请输入要查询的菜名。", "source": "input"}

    compact = "".join(raw.split())
    for term, reason in DIRECT_BLOCK_TERMS.items():
        if term in compact:
            _emit(progress_callback, "warning", "🛡️ 口语关键词已触发本地硬拦截。")
            return {
                "status": "blocked",
                "dish_name": raw,
                "verdict": "禁",
                "property": "高糖/高油风险",
                "message": reason,
                "rationale": reason,
                "source": "direct_term",
                "rule_id": "DIRECT_TERM",
                "source_ref": "人工维护的口语直判词表",
                "rule_version": RULE_VERSION,
                "evidence": [],
                "ai_message": "",
                "ai_error": "",
            }

    _emit(progress_callback, "info", "🔤 正在做菜名归一与检索...")
    found = engine.search_dish(compact)

    if found["status"] == "ambiguous":
        names = found["candidates"]
        _emit(progress_callback, "warning", f"⚠️ 「{raw}」在库内匹配到 {len(names)} 道菜，需要确认具体是哪一道。")
        return {
            "status": "ambiguous",
            "dish_name": raw,
            "message": f"「{raw}」在库内匹配到 {len(names)} 道菜，请从候选中选择或输入完整菜名。",
            "candidates": names,
            "source": "search",
            "ai_message": "",
            "ai_error": "",
        }

    if found["status"] == "miss":
        _emit(progress_callback, "info", "ℹ️ 本地库未收录该菜品。")
        return {
            "status": "unknown",
            "dish_name": raw,
            "verdict": "未知",
            "message": "本地数据库未收录该菜品，无法用规则确认是否适合。建议换用食堂菜单上的具体菜名。",
            "source": "local_database_miss",
            "ai_message": "",
            "ai_error": "",
        }

    name = found["candidates"][0]
    _emit(progress_callback, "info", f"📖 命中菜品「{name}」，执行体质规则判定...")
    dishes = {d["name"]: d for d in _load_dish(name)}
    target = dishes[name]
    verdict = engine.evaluate(target, constitution)
    blocked = verdict["verdict"] == "禁"

    result = {
        "status": "blocked" if blocked else "safe",
        "dish_name": name,
        "verdict": verdict["verdict"],
        "property": target.get("property", ""),
        "message": verdict["rationale"],
        "rationale": verdict["rationale"],
        "canteen_info": target.get("canteen_info", ""),
        "calories": target.get("calories"),
        "source": "rule_engine",
        "rule_id": ",".join(e["rule_id"] for e in verdict["evidence"]) or "DEFAULT_CAUTION",
        "source_ref": "；".join(dict.fromkeys(e["source_ref"] for e in verdict["evidence"]))
        or "规则表默认（无具体条规命中）",
        "rule_version": verdict["rule_version"],
        "evidence": verdict["evidence"],
        "matched_by": found["matched_by"],
        "ai_message": "",
        "ai_error": "",
    }
    _emit(
        progress_callback,
        "warning" if blocked else "success",
        "🛡️ 命中体质禁忌，已拦截。" if blocked else "✅ 未命中该体质的禁忌条规。",
    )

    if has_ai_access and api_key:
        _emit(progress_callback, "info", "🤖 正在呼叫大模型生成受约束解释...")
        prompt = (
            f"体质：{constitution}；菜品：{name}；规则判定：{verdict['verdict']}；"
            f"命中规则：{result['rule_id']}；依据：{verdict['rationale']}。"
            "请用不超过 80 字解释，不得推翻规则结论，不作诊断或疗效承诺。"
        )
        ai_text, ai_err = _call_ai(
            api_key=api_key, prompt=prompt, system_prompt=EXPLAIN_SYSTEM_PROMPT,
            base_url=base_url, model=model,
        )
        if ai_text:
            ok, reason = validate_ai_text(
                ai_text, verdict=verdict["verdict"], allowed_dishes={name}
            )
            if not ok:
                ai_text, ai_err = "", f"{reason}，已降级为本地解释。"
        result["ai_message"], result["ai_error"] = ai_text, ai_err
        _emit(
            progress_callback,
            "success" if result["ai_message"] else "warning",
            "✅ AI 解释生成完成。" if result["ai_message"] else f"⚠️ {result['ai_error']}",
        )
    return result


def _load_dish(name: str) -> list[dict]:
    import sqlite3

    with closing(sqlite3.connect(DATABASE_PATH)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT d.id, d.name, d.property, d.explanation, d.calories,
                (SELECT GROUP_CONCAT(
                    c.location || '｜' || c.window_name ||
                    CASE WHEN c.price IS NULL OR c.price <= 0 THEN '' ELSE '（￥' || c.price || '）' END,
                    '；')
                 FROM Canteen c WHERE c.dish_id = d.id) AS canteen_info
            FROM Dish d WHERE d.name = ?
            """,
            (name,),
        ).fetchall()
    return [dict(r) for r in rows]


def template_explanation(result: dict) -> str:
    """零成本模板解释：只用规则证据拼一句人话，不联网、不消耗额度。

    这是"永远可用"的兜底层：AI 不可用、没额度、不想用 Key 时，用户仍能得到
    一条可读的解释，而不是只有一条规则编号。
    """
    recs = result.get("recommendations") or []
    if not recs:
        return ""
    parts = []
    for d in recs:
        name = d["name"]
        verdict = d.get("verdict", "")
        prop = d.get("property") or ""
        if verdict == "宜":
            lead = f"{name}属性{prop}，与你当前体质不冲突，可以正常吃。" if prop else f"{name}与你当前体质不冲突，可以正常吃。"
        elif verdict == "慎":
            lead = f"{name}属性{prop}，可以吃但别天天吃。" if prop else f"{name}可以吃但别天天吃。"
        else:
            lead = f"{name}属性{prop}，不建议现在吃。" if prop else f"{name}不建议现在吃。"
        parts.append(lead)
    parts.append("如果你更想要一段连贯的解释，可以打开 AI 解释（共享额度或自带 Key）。")
    return "\n\n".join(parts)


def template_dish_explanation(food_result: dict) -> str:
    """单菜查询的零成本解释。"""
    name = food_result.get("dish_name") or "这道菜"
    verdict = food_result.get("verdict") or ""
    prop = food_result.get("property") or ""
    head = f"{name}" + (f"（{prop}）" if prop else "")
    if verdict == "禁":
        return f"{head}：不建议现在吃。依据：{food_result.get('rationale', '')}"
    if verdict == "慎":
        return f"{head}：可以吃，但别频繁吃。依据：{food_result.get('rationale', '')}"
    return f"{head}：与你当前体质不冲突，可以正常吃。依据：{food_result.get('rationale', '')}"


def plan_to_text(result: dict) -> str:
    """把结构化方案转换为可下载的 UTF-8 文本（含规则出处与免责声明）。"""
    lines = ["知源智膳——个性化食养辅助方案", "=" * 24]
    lines.append(f"体质：{result.get('constitution', '未提供')}")
    lines.append(f"情志：{result.get('emotion', '未提供')}")
    constraints = result.get("constraints") or []
    lines.append(f"限制条件：{'、'.join(constraints) if constraints else '无'}")
    lines.append(f"规则版本：{result.get('rule_version', RULE_VERSION)}")
    lines.append("")
    lines.append("本地推荐：")
    for i, dish in enumerate(result.get("recommendations", []), start=1):
        lines.append(f"{i}. {dish['name']}｜判定：{dish.get('verdict', '-')}｜{dish.get('property', '')}")
        lines.append(f"   规则依据：{dish.get('rationale', '')}")
        lines.append(f"   命中规则：{dish.get('rule_id', '-')}（{dish.get('source_ref', '-')}）")
        if dish.get("calories") is not None:
            lines.append(f"   参考能量：{dish['calories']:g} 千卡")
        if dish.get("canteen_info"):
            lines.append(f"   档口/价格：{dish['canteen_info']}")
        if dish.get("alternatives"):
            lines.append(
                "   可替换：" + "、".join(f"{a['name']}（{a['verdict']}）" for a in dish["alternatives"])
            )
    if result.get("ai_message"):
        lines.extend(["", "AI 受约束解释：", result["ai_message"]])
    if result.get("ai_error"):
        lines.extend(["", f"提示：{result['ai_error']}"])
    lines.extend(["", f"说明：{DISCLAIMER}"])
    return "\n".join(lines)


if __name__ == "__main__":
    print(plan_to_text(generate_diet_plan("气虚", "思", [])))
