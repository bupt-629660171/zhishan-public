# -*- coding: utf-8 -*-
"""知源智膳 Streamlit 前端。

边界：本文件只做展示与输入，所有判定交给 rule_engine / shafe_mvp。
UI 上必须能看到三样东西，否则不满足“可追溯”验收：
    1) 每道菜的判定档位（禁/慎/宜）
    2) 命中的规则编号与出处
    3) 免责声明
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

# 本地开发时自动读取 .env（python-dotenv 为可选依赖，缺失则忽略）
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import streamlit as st

import constitution_quiz
import rule_engine as engine
import ui_theme
from version import DISCLAIMER, RULE_VERSION
from shafe_mvp import (
    template_dish_explanation,
    template_explanation,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    check_food,
    generate_diet_plan,
    plan_to_text,
)


# 云端 / 全新环境首次启动时没有数据库，自动初始化一次（幂等、约 1 秒）
try:
    if not engine.DATABASE_PATH.exists():
        import init_db as _init_db

        _init_db.main()
except Exception as _exc:  # 初始化失败不阻塞页面，后续读库会给出明确错误
    st.warning(f"数据库初始化失败：{_exc}")

st.set_page_config(
    page_title="知源智膳",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

VERDICT_STYLE = {
    "宜": ("🟢", "适合"),
    "慎": ("🟡", "慎用"),
    "禁": ("🔴", "不宜"),
}


def verdict_badge(verdict: str) -> str:
    return ui_theme.badge(verdict)



def _conf(key: str, default: str = "") -> str:
    """先读环境变量，再读 st.secrets；两者都没有则返回默认值。

    本地用 .env，云端（Streamlit Cloud / 阿里云）用 secrets，同一份代码两处都能跑。
    """
    value = os.getenv(key, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(key, default) or default).strip()
    except Exception:  # 没有 secrets.toml 时会抛错，忽略即可
        return default


st.markdown(ui_theme.css(), unsafe_allow_html=True)

import sqlite3 as _sql_head

from schema import _ensure_tables as _ensure


def _read(sql: str, args: tuple = ()) -> list:
    """只读小工具：每次现查，避免缓存与数据不同步。"""
    con = _sql_head.connect(engine.DATABASE_PATH)
    try:
        _ensure(con)
        con.row_factory = _sql_head.Row
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def _week_progress() -> int:
    rows = _read(
        "SELECT COUNT(*) AS n FROM Checkin WHERE day >= date('now', '-13 day')"
    )
    return int(rows[0]["n"]) if rows else 0


def _streak() -> int:
    days = {r["day"] for r in _read("SELECT day FROM Checkin")}
    from datetime import date, timedelta

    n, cur = 0, date.today()
    while cur.isoformat() in days:
        n += 1
        cur -= timedelta(days=1)
    return n


if "discovered" not in st.session_state:
    st.session_state["discovered"] = set()
if "plan_today" not in st.session_state:
    st.session_state["plan_today"] = False

st.markdown(
    ui_theme.hero(
        recorded=_week_progress(),
        streak=_streak(),
        task_done=st.session_state["plan_today"],
        rule_version=RULE_VERSION,
        step=int(st.session_state.get("wizard_step", 1)),
    ),
    unsafe_allow_html=True,
)
st.markdown(
    ui_theme.progress(_week_progress(), task="记录晚饭" if not st.session_state["plan_today"] else "已完成选择"),
    unsafe_allow_html=True,
)


with st.sidebar:
    st.header("🔐 解释方式")
    _expected = _conf("ZY_ACCESS_PASSWORD")
    _shared_key = _conf("ZY_SHARED_AI_KEY")
    _shared_base = _conf("ZY_SHARED_AI_BASE_URL", DEFAULT_BASE_URL)
    _shared_model = _conf("ZY_SHARED_AI_MODEL", DEFAULT_MODEL)
    _shared_limit = int(_conf("ZY_SHARED_AI_LIMIT", "20") or 20)
    _used = st.session_state.get("shared_ai_calls", 0)

    mode = st.radio(
        "选一种解释方式",
        ["模板解释（免费·无需联网）", "共享额度（免费）", "自带 Key"],
        index=0,
        help="三种方式都不影响判定结果——判定永远由本地规则给出。",
    )

    api_key, base_url, model = "", DEFAULT_BASE_URL, DEFAULT_MODEL
    has_ai_access = False

    if mode == "模板解释（免费·无需联网）":
        st.caption("用规则依据拼一句话，零成本、零隐私外发。")
    elif mode == "共享额度（免费）":
        if not _shared_key:
            st.warning("未配置共享额度（ZY_SHARED_AI_KEY），请改用模板解释或自带 Key。")
        elif _used >= _shared_limit:
            st.warning(f"本会话共享额度已用完（{_used}/{_shared_limit}），可自带 Key。")
        elif not _expected:
            st.warning("未配置 ZY_ACCESS_PASSWORD，共享额度已停用。")
        else:
            access_password = st.text_input("使用密码", type="password")
            if access_password == _expected:
                api_key, base_url, model = _shared_key, _shared_base, _shared_model
                has_ai_access = True
                st.success(f"共享额度：剩余 {_shared_limit - _used} 次")
            else:
                st.info("输入使用密码后启用共享额度。")
    else:
        api_key = st.text_input(
            "你的 API Key", type="password",
            help="密钥仅在本次会话中使用，不写入源码或数据库。",
        ).strip()
        with st.expander("高级模型设置"):
            base_url = st.text_input("API Base URL", value=DEFAULT_BASE_URL).strip()
            model = st.text_input("模型名称", value=DEFAULT_MODEL).strip()
        has_ai_access = bool(api_key)
        if not api_key:
            st.info("也可以不填，直接用模板解释。")

    st.divider()
    st.caption(f"规则版本 {RULE_VERSION}｜本地硬规则优先，AI 只能解释，不能推翻拦截结果。")


def make_progress_callback(container):
    def callback(level: str, message: str) -> None:
        getattr(container, level, container.info)(message)

    return callback


def render_evidence(item: dict) -> None:
    """规则证据块：编号 + 出处 + 一句话依据。"""
    evidence = item.get("evidence") or []
    if not evidence:
        st.caption("⚪ 未命中具体条规，按「慎」处理")
        return
    with st.expander(f"📜 规则依据（{len(evidence)} 条）"):
        for e in evidence:
            st.markdown(
                f"- **{e['rule_id']}**（{e['action']}·{e['tag']}）：{e['rationale']}\n"
                f"  <div class='rule'>出处：{e['source_ref']}｜版本 {e['rule_version']}</div>",
                unsafe_allow_html=True,
            )


def render_ai_result(result: dict) -> None:
    if result.get("ai_message"):
        with st.expander("🤖 AI 受约束解释（不参与判定）", expanded=True):
            st.write(result["ai_message"])
    elif result.get("ai_error"):
        st.caption(f"⚠️ {result['ai_error']}")


plan_tab, checkin_tab, query_tab, feedback_tab, about_tab = st.tabs(
    ["🥗 生成调养方案", "📅 两周记录", "🔎 查询单道菜", "✍️ 反馈纠错", "📚 规则与合规"]
)


with plan_tab:
    _step = int(st.session_state.get("wizard_step", 1))

    if _step == 1:
        st.markdown(ui_theme.step("STEP 01", "最近两周，你更像哪种状态？"), unsafe_allow_html=True)
        st.markdown(
            '<p class="step-sub">按最近的实际感受选，可以多选。这只是饮食参考的起点，不是诊断。</p>',
            unsafe_allow_html=True,
        )
        st.caption("下面 11 道题用于判断倾向，约 1 分钟。结果只作饮食参考，不是诊断。")
        with st.expander("🧭 体质倾向自评（11 题，可跳过）", expanded=False):
            _answers: dict[str, str] = {}
            for _q in constitution_quiz.QUESTIONS:
                _answers[_q["id"]] = st.segmented_control(
                    _q["text"],
                    constitution_quiz.LEVELS,
                    default="没有",
                    key=f"quiz_{_q['id']}",
                ) or "没有"
            _scores = constitution_quiz.score(_answers)
            _result = constitution_quiz.classify(_scores)
            st.markdown(f"**{constitution_quiz.result_text(_result)}**")
            st.caption(
                f"已回答 {constitution_quiz.answered(_answers)} / "
                f"{len(constitution_quiz.QUESTIONS)} 题 · 简化自评，非标准量表"
            )

        suggested = _result["type"] if _result["supported"] else None

        if "selected_constitution" not in st.session_state:
            st.session_state["selected_constitution"] = suggested or "气虚"

        if suggested and st.button(f"采用自评倾向：{suggested}", use_container_width=True):
            st.session_state["selected_constitution"] = suggested

        if suggested is None:
            st.info(
                "自评结果不在当前支持范围（气虚 / 湿热）。可以手动选一个最接近的，"
                "或按通用原则少油少盐；有明显不适请咨询专业人士。"
            )

        constitution = st.segmented_control(
            "本次采用体质（可手动调整）",
            list(engine.SUPPORTED_CONSTITUTIONS),
            key="selected_constitution",
            default=st.session_state.get("selected_constitution", suggested),
        ) or st.session_state.get("selected_constitution", suggested)
        emotion = st.segmented_control(
            "情志自评", ["平和", "思", "怒", "忧", "喜"], default="平和", key="emotion_seg"
        ) or "平和"
        if st.button("下一步：设置忌口 →", use_container_width=True, type="primary"):
            st.session_state["wizard_step"] = 2
            st.rerun()

    elif _step == 2:
        st.markdown(ui_theme.step("STEP 02", "忌口与饮食偏好"), unsafe_allow_html=True)
        constraints = st.pills(
            "饮食限制（点一下选中，再点取消）",
            ["素食", "蛋奶素", "无麸质", "不吃苦味", "不吃辣"],
            selection_mode="multi",
            key="constraint_pills",
            help="素食=纯素（含蛋奶也排除）；蛋奶素只排除肉类，保留蛋奶。",
        ) or []

        import sqlite3 as _sq

        with _sq.connect(engine.DATABASE_PATH) as _c:
            _campuses = [r[0] for r in _c.execute("SELECT DISTINCT campus FROM Dish_Source ORDER BY campus")]
        _campus_options = ["全部"] + _campuses
        if len(_campus_options) <= 6:
            _campus_choice = st.segmented_control(
                "食堂范围", _campus_options, default="全部", key="campus_seg"
            ) or "全部"
        else:
            _campus_choice = st.selectbox("食堂范围", _campus_options, index=0)
        campus = None if _campus_choice == "全部" else _campus_choice

        _b1, _b2 = st.columns([1, 2])
        if _b1.button("← 上一步", use_container_width=True):
            st.session_state["wizard_step"] = 1
            st.rerun()
        if _b2.button("生成今日方案 →", use_container_width=True, type="primary"):
            st.session_state["wizard_step"] = 3
            st.rerun()

    constitution = st.session_state.get("selected_constitution", "气虚")
    emotion = st.session_state.get("emotion_seg", "平和")
    constraints = st.session_state.get("constraint_pills", []) or []
    _campus_now = st.session_state.get("campus_seg", "全部")
    campus = None if _campus_now == "全部" else _campus_now
    signature = (constitution, emotion, tuple(sorted(constraints)))

    if _step == 3:
        if st.button("← 回到忌口", use_container_width=False):
            st.session_state["wizard_step"] = 2
            st.rerun()

        if st.session_state.get("diet_plan_signature") != signature:
            if has_ai_access and mode == "共享额度（免费）":
                st.session_state["shared_ai_calls"] = _used + 1
            with st.expander("🧭 生成过程透明度", expanded=True):
                area = st.container()
                _r = generate_diet_plan(
                    constitution, emotion, constraints, has_ai_access, campus=campus,
                    api_key=api_key, base_url=base_url, model=model,
                    progress_callback=make_progress_callback(area),
                )
            st.session_state["diet_plan"] = _r
            st.session_state["diet_plan_signature"] = signature
            st.session_state["plan_today"] = True

    result = (
        st.session_state.get("diet_plan")
        if st.session_state.get("diet_plan_signature") == signature
        else None
    )
    if result:
        if result.get("status") in {"error", "empty"}:
            st.warning(result.get("message", "暂无结果"))
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("菜品库", result["total_count"])
            c2.metric("规则拦截", result["blocked_count"])
            c3.metric("候选", result["remaining_count"])

            st.markdown(ui_theme.step("STEP 03", "今日食养推荐", True), unsafe_allow_html=True)
            cols = st.columns(max(1, len(result["recommendations"])))
            for col, dish in zip(cols, result["recommendations"]):
                with col, st.container(border=True):
                    st.markdown(f"### {dish['name']}")
                    st.markdown(verdict_badge(dish['verdict']), unsafe_allow_html=True)
                    st.caption(f"属性：{dish.get('property', '-')}")
                    if dish.get("calories") is not None:
                        st.caption(f"参考能量：{dish['calories']:g} 千卡")
                    st.write(dish.get("rationale", "建议适量食用。"))
                    if dish.get("canteen_info"):
                        st.caption(f"📍 {dish['canteen_info']}")
                    if dish.get("alternatives"):
                        st.caption(
                            "换一道："
                            + " / ".join(f"{a['name']}（{a['verdict']}）" for a in dish["alternatives"])
                        )
                    render_evidence(dish)


            # —— 两周小实验：把"信我"换成"试两周" ——
            first = next((d for d in result["recommendations"] if d["verdict"] == "宜"), None)
            if first is None and result["recommendations"]:
                first = result["recommendations"][0]
            if first:
                with st.container(border=True):
                    st.markdown("#### 🧪 两周小实验")
                    st.markdown(
                        f"**先试一道**：明天把「{first['name']}」当作一次尝试，"
                        f"不必一下子改掉所有习惯。"
                    )
                    c1, c2, c3 = st.columns(3)
                    c1.markdown("**① 饭后腹胀**\n胀 / 不胀")
                    c2.markdown("**② 大便成形**\n成形 / 偏稀")
                    c3.markdown("**③ 下午困倦**\n困 / 还好")
                    st.caption(
                        f"记录 14 天（到 {datetime.now().date() + timedelta(days=14)} 回看一次）。"
                        "只记感受，不做诊断；有明显不适请停用并就医。"
                    )

            if result.get("blocked_details"):
                with st.expander(f"🛡️ 查看被拦截的 {result['blocked_count']} 道菜及原因"):
                    for item in result["blocked_details"]:
                        st.write(f"- {item['name']}：{item['reason']}")

            if not result.get("ai_message"):
                with st.expander("📝 本地模板解释（无需联网）", expanded=False):
                    st.write(template_explanation(result))
            render_ai_result(result)
            st.download_button(
                "⬇️ 导出调养方案 TXT",
                data=plan_to_text(result).encode("utf-8-sig"),
                file_name=f"知源智膳调养方案_{datetime.now():%Y%m%d_%H%M}.txt",
                mime="text/plain",
                use_container_width=True,
            )


with checkin_tab:
    st.markdown(ui_theme.step("STEP 04", "接下来两周，记三件事"), unsafe_allow_html=True)
    st.caption("吃饭后的感受，一天一记。只存在本机，不关联身份，也不作为诊断依据。")
    _streak_n = _streak()
    _found = len(st.session_state["discovered"])
    st.markdown(
        ui_theme.badges_html([
            (f"连续记录 <b>{_streak_n}</b> 天" if _streak_n else "今天开始记录", "on" if _streak_n else ""),
            ("完成今日选择" if st.session_state["plan_today"] else "还没选今天吃什么",
             "on" if st.session_state["plan_today"] else ""),
            (f"发现新食材 <b>{_found}</b> 个" if _found else "还没有新发现", "gold" if _found else ""),
        ]),
        unsafe_allow_html=True,
    )

    import sqlite3 as _sql

    from schema import _ensure_tables

    def _conn():
        con = _sql.connect(engine.DATABASE_PATH)
        _ensure_tables(con)
        return con

    with st.form("checkin_form"):
        c1, c2, c3 = st.columns(3)
        day = c1.date_input("日期", value=datetime.now().date())
        bloating = c2.radio("饭后腹胀", ["不胀", "胀"], horizontal=True)
        stool = c3.radio("大便成形", ["成形", "偏稀"], horizontal=True)
        tired = st.radio("下午困倦", ["还好", "困"], horizontal=True)
        note = st.text_input("备注（可选，如：今天吃了什么）")
        if st.form_submit_button("保存今天的记录", use_container_width=True):
            with _conn() as con:
                con.execute(
                    "INSERT OR REPLACE INTO Checkin (day, bloating, stool_ok, tired, note, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (str(day), int(bloating == "胀"), int(stool == "成形"), int(tired == "困"),
                     note.strip(), datetime.now().isoformat(timespec="seconds")),
                )
                con.commit()
            st.success(f"已保存 {day} 的记录")

    try:
        with _conn() as con:
            con.row_factory = _sql.Row
            rows = [dict(r) for r in con.execute(
                "SELECT day, bloating, stool_ok, tired, note FROM Checkin ORDER BY day DESC LIMIT 14"
            )]
    except Exception as exc:
        rows = []
        st.warning(f"读取记录失败：{exc}")

    if not rows:
        st.info("还没有记录。先记 3 天，就能看到变化趋势。")
    else:
        st.markdown("#### 最近记录")
        st.dataframe(
            [
                {
                    "日期": r["day"],
                    "饭后腹胀": "胀" if r["bloating"] else "不胀",
                    "大便": "成形" if r["stool_ok"] else "偏稀",
                    "下午困倦": "困" if r["tired"] else "还好",
                    "备注": r["note"] or "",
                }
                for r in rows
            ],
            use_container_width=True,
            hide_index=True,
        )

        first, last = rows[-1], rows[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("腹胀天数（最近）", int(last["bloating"]), delta=int(last["bloating"]) - int(first["bloating"]))
        c2.metric("大便成形（最近）", "是" if last["stool_ok"] else "否")
        c3.metric("下午困倦（最近）", "困" if last["tired"] else "还好")
        st.caption(
            f"共 {len(rows)} 天记录。这里只呈现你自己的感受变化，不是诊断结论；"
            "若症状加重或持续，请就医。"
        )


    # ---------- 本周发现：食材图鉴（分类 + 分页）----------
    st.markdown(ui_theme.step("COLLECTION", "本周发现"), unsafe_allow_html=True)
    st.markdown(
        '<p class="step-sub">查过的食材会点亮一个。只是记录你的探索，不代表任何评价。</p>',
        unsafe_allow_html=True,
    )

    def _category(name: str) -> str:
        if any(k in name for k in ("米", "面", "麦", "豆", "薯", "玉米", "燕麦", "薏", "荞", "粉")):
            return "五谷"
        if any(k in name for k in ("菜", "瓜", "茄", "椒", "葱", "蒜", "姜", "萝卜", "藕", "笋",
                                    "菌", "菇", "耳", "藻", "带", "紫菜")):
            return "蔬菜"
        if any(k in name for k in ("肉", "鸡", "鸭", "鹅", "蛋", "奶", "鱼", "虾", "蟹", "贝", "蛤", "肝")):
            return "肉蛋"
        if any(k in name for k in ("果", "桃", "梨", "枣", "莓", "橘", "橙", "柚", "蕉", "荔",
                                    "龙眼", "柿", "石", "葡", "苹")):
            return "果品"
        if any(k in name for k in ("油", "盐", "醋", "酱", "糖", "椒", "桂", "八角", "胡椒")):
            return "调味"
        return "其他"

    _ing = [r["name"] for r in _read("SELECT name FROM Dish WHERE COALESCE(kind,'dish')='ingredient' ORDER BY name")]
    _cats: dict[str, list[str]] = {}
    for _n in _ing:
        _cats.setdefault(_category(_n), []).append(_n)

    _cat_names = ["全部"] + [c for c in ("五谷", "蔬菜", "肉蛋", "果品", "调味", "其他") if c in _cats]
    _cat = st.radio("分类", _cat_names, horizontal=True, key="codex_cat", label_visibility="collapsed")
    _pool = _ing if _cat == "全部" else _cats[_cat]
    _page_size = 8
    _pages = max(1, (len(_pool) + _page_size - 1) // _page_size)
    _page = min(st.session_state.get("codex_page", 0), _pages - 1)
    _slice = _pool[_page * _page_size:(_page + 1) * _page_size]

    st.markdown(
        ui_theme.stamps([{"name": n, "on": n in st.session_state["discovered"]} for n in _slice]),
        unsafe_allow_html=True,
    )

    _c1, _c2, _c3 = st.columns([3, 1, 1])
    _done = sum(1 for n in _pool if n in st.session_state["discovered"])
    _c1.caption(f"{_cat} · 已发现 {_done} / {len(_pool)} · 第 {_page + 1} / {_pages} 页")
    if _c2.button("‹ 上一页", use_container_width=True, disabled=_page == 0):
        st.session_state["codex_page"] = _page - 1
        st.rerun()
    if _c3.button("下一页 ›", use_container_width=True, disabled=_page >= _pages - 1):
        st.session_state["codex_page"] = _page + 1
        st.rerun()


with query_tab:
    st.subheader("口语化菜名查询")
    st.caption("支持：香锅、黄焖鸡、拉面、甜的。单字查询会先让你确认具体菜品，不再瞎匹配。")
    c1, c2 = st.columns([1, 2])
    with c1:
        q_constitution = st.segmented_control(
            "查询体质", list(engine.SUPPORTED_CONSTITUTIONS), key="query_constitution"
        ) or list(engine.SUPPORTED_CONSTITUTIONS)[0]
    with c2:
        dish_input = st.text_input("想查询什么菜？", placeholder="例如：我想吃香锅 / 来点甜的")
    q_signature = (q_constitution, dish_input.strip())

    if st.button("🔍 开始双层判定", use_container_width=True):
        with st.expander("🧭 判定过程透明度", expanded=True):
            area = st.container()
            q_result = check_food(
                q_constitution, dish_input, api_key=api_key, has_ai_access=has_ai_access,
                base_url=base_url, model=model, progress_callback=make_progress_callback(area),
            )
        st.session_state["food_query_result"] = q_result
        st.session_state["food_query_signature"] = q_signature

    q_result = (
        st.session_state.get("food_query_result")
        if st.session_state.get("food_query_signature") == q_signature
        else None
    )
    if q_result:
        status = q_result.get("status")
        if status == "blocked":
            st.error(f"⛔ 规则拦截：{q_result['message']}")
        elif status == "safe":
            st.success(f"✅ 规则放行：{q_result['message']}")
        elif status == "ambiguous":
            st.warning(q_result["message"])
            st.write("候选：" + "、".join(q_result.get("candidates", [])))
        elif status == "unknown":
            st.warning(q_result["message"])
        else:
            st.error(q_result.get("message", "查询失败，请稍后重试。"))

        if q_result.get("verdict"):
            st.markdown(
                verdict_badge(q_result["verdict"])
                + f"<span class='muted'> 体质：{q_constitution}</span>",
                unsafe_allow_html=True,
            )
        if q_result.get("evidence"):
            render_evidence(q_result)
        if q_result.get("canteen_info"):
            st.caption(f"📍 档口/价格：{q_result['canteen_info']}")
        if not q_result.get("ai_message"):
            with st.expander("📝 本地模板解释（无需联网）", expanded=False):
                st.write(template_dish_explanation(q_result))
        render_ai_result(q_result)


with feedback_tab:
    st.subheader("反馈纠错")
    st.caption(
        "发现某道菜的性味或依据不对？提交后会进入候选池，**不会直接改库**，"
        "需要人工审核通过才生效。"
    )

    import sqlite3 as _fsql

    with st.form("feedback_form"):
        c1, c2 = st.columns([2, 1])
        fb_name = c1.text_input("菜名", placeholder="例如：红烧排骨")
        fb_kind = c2.selectbox("类型", ["性味/依据有误", "补录新菜"])
        fb_prop = st.text_input("建议性味（可选）", placeholder="例如：温补多油")
        fb_expl = st.text_area("建议依据（可选）", placeholder="写清为什么，越具体越好")
        fb_note = st.text_input("说明（可选）", placeholder="你在哪个窗口看到的、和实际有何不同")
        if st.form_submit_button("提交反馈", use_container_width=True):
            if not fb_name.strip():
                st.warning("请填写菜名")
            else:
                con = _fsql.connect(engine.DATABASE_PATH)
                from schema import _ensure_tables

                _ensure_tables(con)
                con.execute(
                    "INSERT INTO Candidate (kind, name, property, explanation, note, "
                    "status, submitted_by, submitted_at, campus) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("new" if fb_kind == "补录新菜" else "fix",
                     fb_name.strip(), fb_prop.strip(), fb_expl.strip(), fb_note.strip(),
                     "待审", "匿名用户", datetime.now().isoformat(timespec="seconds"), "沙河"),
                )
                con.commit()
                con.close()
                st.success("已提交，等待人工审核。可在下方候选池查看状态。")

    try:
        con = _fsql.connect(engine.DATABASE_PATH)
        con.row_factory = _fsql.Row
        cands = [dict(r) for r in con.execute(
            "SELECT id, kind, name, status, submitted_at, review_comment "
            "FROM Candidate ORDER BY status='待审' DESC, id DESC LIMIT 20"
        )]
        con.close()
    except Exception as exc:
        cands = []
        st.warning(f"读取候选池失败：{exc}")

    if cands:
        st.markdown("#### 候选池（最近 20 条）")
        st.dataframe(
            [
                {"编号": c["id"], "类型": "新菜" if c["kind"] == "new" else "修正",
                 "菜名": c["name"], "状态": c["status"],
                 "提交时间": c["submitted_at"][:16], "审核意见": c["review_comment"] or ""}
                for c in cands
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.caption("审核在命令行执行：python tools.py candidate approve <编号>")
    else:
        st.info("候选池为空。")


with about_tab:
    st.subheader("规则与合规边界")
    st.markdown(
        f"""
- **规则版本**：`{RULE_VERSION}`，全部规则状态为 **草案**，待导师审核后方可称为"已审核规则"。
- **判定权在本地**：体质禁忌由 SQLite 规则表 + 纯 Python 引擎执行，大模型不参与"能不能吃"的判断。
- **三层结构**：菜品文本 → 属性标签（tags.py）→ 规则表（rules.csv）→ 判定（rule_engine.py）。
- **可追溯**：每条推荐都带规则编号与出处，可在「规则依据」里展开核对。
- **数据来源**：北京邮电大学沙河校区食堂菜品与档口信息，人工整理，持续补充。
"""
    )
    st.subheader("常见疑问")
    with st.expander("「中医不科学吧？」"):
        st.write(
            "这里不谈理论对错，只谈可验证：每条结论都能点开「规则依据」，看到它引用了哪条规则、出自哪里。"
            "你可以只把它当作一份带出处的饮食筛选清单。"
        )
    with st.expander("「我太忙了，做不到。」"):
        st.write(
            "所以系统每次只给 3 道菜，还可以在卡片下「换一道」。"
            "你不需要改变生活方式，只需要今天选一道菜。"
        )
    with st.expander("「以前试过，没用。」"):
        st.write(
            "这里给的不是泛泛的养生建议，而是沙河食堂里具体到窗口和价格的菜。"
            "如果某条判定你觉得不对，可以在结果页看到它依据的规则编号。"
        )
    with st.expander("「会不会很贵？」"):
        st.write(
            "本地规则库和模板解释完全免费、不需要联网。AI 解释是可选项：可以用项目提供的共享额度（限次），也可以填自己的 Key。"
        )
    with st.expander("「家里人说瞎折腾。」"):
        st.write(
            "可以把结果导出成 TXT 给家人看——里面写清了每条建议的出处，不是「网上说的」。"
        )
    with st.expander("「能不能快点好？」"):
        st.write(
            "不能承诺。本系统只做日常食养辅助，不诊断、不开方、不替代就医；"
            "有明显不适或症状持续，请及时就诊。"
        )
    st.caption(DISCLAIMER)
