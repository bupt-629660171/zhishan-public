# -*- coding: utf-8 -*-
"""知源食养 · 设计令牌与展示组件（v3：轻任务流 + 像素点缀）。

原则：
  - 颜色/字号/间距只在这里定义，app.py 不再写死色值；
  - 像素只出现在图标、徽章、插画；
  - 状态一律"图标 + 文字 + 颜色"三重编码。
"""

from __future__ import annotations

COLORS = {
    "bg": "#FAF6EE",
    "surface": "#FFFDF8",
    "surface2": "#F5EFE2",
    "line": "#E4DBC9",
    "ink": "#2B251E",
    "ink2": "#6B6152",
    "ink3": "#8C8171",
    "leaf": "#5E7F52",
    "leaf_soft": "#E7EEDF",
    "clay": "#B9643F",
    "clay_soft": "#F6E3D8",
    "gold": "#C8973F",
    "gold_soft": "#F7ECD5",
}

# 判定：推荐 / 适量 / 暂不建议（避免"宜慎禁"的医疗感）
VERDICT = {
    "宜": {"icon": "✓", "text": "推荐", "fg": COLORS["leaf"], "bg": COLORS["leaf_soft"], "bd": "#CBDCC0"},
    "慎": {"icon": "!", "text": "适量", "fg": "#7A5A1E", "bg": COLORS["gold_soft"], "bd": "#E8D5A8"},
    "禁": {"icon": "✕", "text": "暂不建议", "fg": COLORS["clay"], "bg": COLORS["clay_soft"], "bd": "#EBC7B6"},
}

FONT = ('-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", '
        '"Hiragino Sans GB", sans-serif')


def css() -> str:
    c = COLORS
    return f"""
    <style>
    :root {{
      --bg:{c['bg']}; --surface:{c['surface']}; --surface2:{c['surface2']};
      --line:{c['line']}; --ink:{c['ink']}; --ink2:{c['ink2']}; --ink3:{c['ink3']};
      --leaf:{c['leaf']}; --leaf-soft:{c['leaf_soft']};
      --clay:{c['clay']}; --clay-soft:{c['clay_soft']};
      --gold:{c['gold']}; --gold-soft:{c['gold_soft']};
    }}
    html, body, [class*="css"] {{ font-family:{FONT}; }}
    .stApp {{ background:var(--bg); }}
    .block-container {{ max-width:1120px; padding:1.4rem 1.5rem 4rem; }}
    #MainMenu, footer {{ visibility:hidden; }}

    /* 品牌 */
    .brand {{ display:flex; align-items:center; gap:.6rem; margin-bottom:.2rem; }}
    .brand h1 {{ font-size:1.55rem; margin:0; color:var(--ink); letter-spacing:.01em; }}
    .brand .sub {{ font-size:.78rem; color:var(--ink3); }}
    .tagline {{ color:var(--ink2); font-size:.95rem; margin:0 0 1rem; }}

    /* 卡片 */
    .card {{ background:var(--surface); border:1px solid var(--line); border-radius:8px;
             padding:1rem 1.1rem; box-shadow:0 1px 0 rgba(59,50,39,.04), 0 2px 8px rgba(59,50,39,.05); }}

    /* 判定徽章 */
    .vbadge {{ display:inline-flex; align-items:center; gap:.35rem; padding:.16rem .6rem;
               border-radius:999px; font-size:.78rem; font-weight:600; line-height:1.7; }}
    .vbadge .ico {{ font-weight:700; }}

    /* STEP 标头 */
    .step {{ display:flex; align-items:center; gap:.6rem; margin:1.6rem 0 .3rem; }}
    .step .num {{ font-family:Consolas,monospace; font-size:.68rem; letter-spacing:.12em; color:var(--ink3); }}
    .step h2 {{ font-size:1.15rem; margin:0; color:var(--ink); }}
    .step .state {{ margin-left:.2rem; font-family:Consolas,monospace; font-size:.68rem;
                    padding:.12rem .45rem; border-radius:999px; border:1px solid; }}
    .step .state.done {{ color:var(--leaf); border-color:#CBDCC0; background:var(--leaf-soft); }}
    .step .state.todo {{ color:var(--clay); border-color:#EBC7B6; background:var(--clay-soft); }}
    .step-sub {{ color:var(--ink2); font-size:.86rem; margin:0 0 .9rem; }}

    /* 进度卡 */
    .progress {{ display:flex; align-items:center; gap:.8rem; flex-wrap:wrap;
                 background:var(--surface); border:1px solid var(--line); border-radius:8px;
                 padding:.7rem .9rem; margin:.2rem 0 1rem; }}
    .progress .lab {{ font-size:.8rem; color:var(--ink2); }}
    .progress .lab b {{ font-family:Consolas,monospace; color:var(--ink); font-size:.95rem; }}
    .seg {{ display:flex; gap:3px; }}
    .seg i {{ width:13px; height:7px; border-radius:2px; background:var(--surface2);
              border:1px solid var(--line); display:block; }}
    .seg i.on {{ background:var(--leaf); border-color:var(--leaf); }}
    .seg i.today {{ background:var(--gold); border-color:var(--gold); }}

    /* 向导 */
    .guide {{ display:flex; align-items:flex-start; gap:.5rem; justify-content:flex-end; margin:.3rem 0 .6rem; }}
    .guide .bubble {{ background:var(--surface); border:1px solid var(--line); border-radius:8px;
                      padding:.4rem .65rem; font-size:.8rem; color:var(--ink2); max-width:230px; }}

    /* 徽章 */
    .badges {{ display:flex; gap:.5rem; flex-wrap:wrap; margin:.2rem 0 .8rem; }}
    .badge {{ display:inline-flex; align-items:center; gap:.4rem; font-size:.78rem;
              background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:.35rem .6rem; }}
    .badge.on {{ background:var(--leaf-soft); border-color:#CBDCC0; color:#3F5A36; }}
    .badge.gold {{ background:var(--gold-soft); border-color:#E8D5A8; color:#7A5A1E; }}

    /* 图鉴 */
    .stamps {{ display:grid; grid-template-columns:repeat(8,1fr); gap:.55rem; }}
    .stamp {{ aspect-ratio:1; border:1px solid var(--line); border-radius:6px; background:var(--surface);
              display:flex; flex-direction:column; align-items:center; justify-content:center;
              gap:.2rem; font-size:.7rem; color:var(--ink2); }}
    .stamp.on {{ background:var(--leaf-soft); border-color:#CBDCC0; }}
    .stamp.locked {{ background:var(--surface2); color:#B0A48E; }}

    /* 按钮 */
    .stButton > button {{ min-height:42px; border-radius:6px; }}
    @media (max-width:760px) {{
      .block-container {{ padding:.8rem .8rem 4rem; }}
      .stamps {{ grid-template-columns:repeat(4,1fr); }}
    }}

    /* v4 首屏：食养探索舱 */
    [data-testid="stHeader"] {{ background:transparent; }}
    [data-testid="stSidebar"] {{ background:#F2E9D8; border-right:1px solid var(--line); }}
    [data-testid="stTabs"] [data-baseweb="tab-list"] {{
      gap:.35rem; padding:.3rem; border:1px solid var(--line); border-radius:14px;
      background:rgba(255,253,248,.78); backdrop-filter:blur(12px);
      position:sticky; top:.45rem; z-index:20; box-shadow:0 10px 30px rgba(70,55,35,.06);
    }}
    [data-testid="stTabs"] [data-baseweb="tab"] {{ border-radius:10px; padding:.5rem .9rem; }}
    [data-testid="stTabs"] [aria-selected="true"] {{ background:var(--ink)!important; color:#FFF9EC!important; }}
    .stButton > button {{
      border:1px solid #D9CDB9; background:#FFFDF8; color:var(--ink); font-weight:650;
      box-shadow:0 5px 0 #E7DDCB; transition:transform .14s ease, box-shadow .14s ease, border-color .14s ease;
    }}
    .stButton > button:hover {{ transform:translateY(-2px); border-color:var(--leaf); box-shadow:0 7px 0 #DCE6D5; color:var(--leaf); }}
    .stButton > button:active {{ transform:translateY(3px); box-shadow:0 2px 0 #E7DDCB; }}
    .stButton > button[kind="primary"] {{ background:var(--leaf); color:white; border-color:#496940; box-shadow:0 5px 0 #3F5B37; }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:14px; border-color:var(--line)!important; background:rgba(255,253,248,.78); }}

    .hero-shell {{
      position:relative; overflow:hidden; min-height:430px; margin:.15rem 0 1.05rem;
      border:1px solid rgba(73,94,62,.28); border-radius:24px; color:#FDF8EC;
      background:
        radial-gradient(circle at 78% 42%, rgba(225,181,92,.30), transparent 23%),
        radial-gradient(circle at 16% 12%, rgba(255,255,255,.10), transparent 25%),
        linear-gradient(125deg,#1F2C22 0%,#314633 54%,#5B4430 125%);
      box-shadow:0 28px 70px rgba(55,43,28,.18); isolation:isolate;
    }}
    .hero-shell:before {{
      content:""; position:absolute; inset:0; opacity:.17; pointer-events:none;
      background-image:linear-gradient(rgba(255,255,255,.18) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.18) 1px,transparent 1px);
      background-size:32px 32px; mask-image:linear-gradient(to right,black,transparent 62%);
    }}
    .hero-shell:after {{
      content:""; position:absolute; width:420px; height:420px; right:-105px; top:-145px;
      border:1px solid rgba(255,238,190,.28); border-radius:50%; box-shadow:0 0 0 34px rgba(255,238,190,.035),0 0 0 68px rgba(255,238,190,.025);
    }}
    .hero-grid {{ display:grid; grid-template-columns:1.15fr .85fr; min-height:430px; }}
    .hero-copy {{ position:relative; z-index:2; padding:3.25rem 1.2rem 2.8rem 3.1rem; display:flex; flex-direction:column; justify-content:center; }}
    .hero-kicker {{ font-family:Consolas,monospace; font-size:.72rem; letter-spacing:.18em; color:#E9CA82; margin-bottom:1rem; }}
    .hero-title {{ margin:0; font-size:clamp(2.6rem,5.3vw,5.2rem); line-height:.98; letter-spacing:-.065em; font-weight:850; }}
    .hero-title em {{ color:#EBC56D; font-style:normal; position:relative; }}
    .hero-desc {{ color:rgba(255,249,235,.72); font-size:.96rem; line-height:1.9; max-width:37rem; margin:1.35rem 0 1.55rem; }}
    .hero-chips {{ display:flex; gap:.55rem; flex-wrap:wrap; }}
    .hero-chip {{ border:1px solid rgba(255,255,255,.20); border-radius:999px; padding:.36rem .72rem; font-size:.75rem; color:#F6EEDC; background:rgba(255,255,255,.07); backdrop-filter:blur(8px); }}
    .hero-chip b {{ color:#F1CA70; font-family:Consolas,monospace; }}
    .hero-art {{ position:relative; min-height:400px; z-index:2; display:grid; place-items:center; }}
    .orbit {{ position:absolute; width:285px; height:285px; border:1px solid rgba(255,239,193,.36); border-radius:50%; animation:orbit 18s linear infinite; }}
    .orbit:before,.orbit:after {{ content:""; position:absolute; width:12px; height:12px; border:3px solid #EBC56D; background:#314633; box-shadow:0 0 0 5px rgba(235,197,109,.10); }}
    .orbit:before {{ left:28px; top:34px; }} .orbit:after {{ right:19px; bottom:49px; }}
    .pixel-bowl {{ position:relative; width:225px; height:156px; filter:drop-shadow(0 24px 17px rgba(0,0,0,.24)); animation:float 4.6s ease-in-out infinite; }}
    .bowl-rim {{ position:absolute; left:12px; right:12px; top:55px; height:38px; border:5px solid #F8EAC8; border-radius:50%; background:#C77B4F; box-shadow:inset 0 0 0 10px #E7A46F; }}
    .bowl-body {{ position:absolute; left:26px; right:26px; top:76px; height:74px; border:5px solid #F8EAC8; border-top:0; background:#F2DEC0; clip-path:polygon(0 0,100% 0,84% 100%,16% 100%); }}
    .ingredient {{ position:absolute; z-index:3; border-radius:50%; box-shadow:5px 5px 0 rgba(31,44,34,.45); }}
    .i1 {{ width:35px;height:24px;background:#E9C35E;left:70px;top:61px; }}
    .i2 {{ width:42px;height:26px;background:#799568;right:61px;top:58px; }}
    .i3 {{ width:31px;height:20px;background:#F5E9C5;left:104px;top:65px; }}
    .steam-px {{ position:absolute; width:10px;height:10px;background:#F5E9C5; top:25px; left:86px; box-shadow:18px -18px 0 rgba(245,233,197,.78),42px 4px 0 rgba(245,233,197,.55); animation:steam 2.3s steps(4) infinite; }}
    .art-label {{ position:absolute; bottom:1.8rem; font-family:Consolas,monospace; font-size:.68rem; letter-spacing:.15em; color:rgba(255,249,235,.48); }}
    .quest-dock {{ display:grid; grid-template-columns:repeat(4,1fr); gap:.55rem; margin-top:.2rem; }}
    .quest-node {{ padding:.65rem .75rem; border-left:2px solid var(--line); color:var(--ink2); font-size:.75rem; }}
    .quest-node b {{ display:block; color:var(--ink); font-size:.84rem; margin-bottom:.1rem; }}
    .quest-node.on {{ border-left-color:var(--leaf); background:linear-gradient(90deg,var(--leaf-soft),transparent); }}
    @keyframes float {{ 50% {{ transform:translateY(-12px) rotate(-1deg); }} }}
    @keyframes orbit {{ to {{ transform:rotate(360deg); }} }}
    @keyframes steam {{ to {{ transform:translateY(-28px); opacity:0; }} }}
    @media (prefers-reduced-motion:reduce) {{ .orbit,.pixel-bowl,.steam-px {{ animation:none; }} }}
    @media (max-width:760px) {{
      .hero-shell {{ min-height:auto; border-radius:18px; }} .hero-grid {{ grid-template-columns:1fr; }}
      .hero-copy {{ padding:2.25rem 1.3rem 1rem; }} .hero-title {{ font-size:2.75rem; }}
      .hero-art {{ min-height:285px; }} .orbit {{ width:230px;height:230px; }} .pixel-bowl {{ transform:scale(.82); }}
      .quest-dock {{ grid-template-columns:1fr 1fr; }}
    }}
    </style>
    """


def hero(recorded: int, streak: int, task_done: bool, rule_version: str) -> str:
    done_text = "今日方案已解锁" if task_done else "今日方案待探索"
    done_cls = "on" if task_done else ""
    return f"""
    <section class="hero-shell">
      <div class="hero-grid">
        <div class="hero-copy">
          <div class="hero-kicker">ZHĪYUÁN · DAILY FOOD QUEST</div>
          <h1 class="hero-title">身体会说话，<br><em>一餐来回应。</em></h1>
          <p class="hero-desc">从最近两周的真实感受出发，在校园食堂里发现更合适的一餐。规则负责判断，AI 只负责解释——每条建议都能追溯。</p>
          <div class="hero-chips">
            <span class="hero-chip">本周记录 <b>{recorded}/14</b></span>
            <span class="hero-chip">连续探索 <b>{streak} 天</b></span>
            <span class="hero-chip">规则版本 <b>{rule_version}</b></span>
          </div>
        </div>
        <div class="hero-art" aria-label="像素风热汤食养罗盘">
          <div class="orbit"></div>
          <div class="pixel-bowl">
            <i class="steam-px"></i><i class="ingredient i1"></i><i class="ingredient i2"></i><i class="ingredient i3"></i>
            <div class="bowl-rim"></div><div class="bowl-body"></div>
          </div>
          <span class="art-label">SCAN · MATCH · TASTE · RECORD</span>
        </div>
      </div>
    </section>
    <div class="quest-dock">
      <div class="quest-node on"><b>01 感受扫描</b>选择最近两周的状态</div>
      <div class="quest-node on"><b>02 边界装备</b>装入忌口与饮食偏好</div>
      <div class="quest-node {done_cls}"><b>03 今日掉落</b>{done_text}</div>
      <div class="quest-node {"on" if recorded else ""}"><b>04 两周图鉴</b>记录感受，点亮发现</div>
    </div>
    """


def badge(verdict: str) -> str:
    v = VERDICT.get(verdict)
    if not v:
        return '<span class="vbadge" style="color:#6B6152;background:#F1EFEA;">? 未知</span>'
    return (f'<span class="vbadge" style="color:{v["fg"]};background:{v["bg"]};'
            f'border:1px solid {v["bd"]}"><span class="ico">{v["icon"]}</span>{v["text"]}</span>')


def step(num: str, title: str, done: bool | None = None) -> str:
    if done is None:
        tag = ""
    else:
        tag = (f'<span class="state {"done" if done else "todo"}">'
               f'{"✓ 已完成" if done else "待完成"}</span>')
    return f'<div class="step"><span class="num">{num}</span><h2>{title}</h2>{tag}</div>'


def progress(recorded: int, total: int = 14, today_index: int = 5, task: str = "记录晚饭") -> str:
    segs = "".join(
        f'<i class="{"on" if i < recorded else ("today" if i == today_index else "")}"></i>'
        for i in range(total)
    )
    return (f'<div class="progress"><span class="lab">本周记录 <b>{recorded}</b> / {total} 天</span>'
            f'<span class="seg">{segs}</span>'
            f'<span class="lab" style="margin-left:auto">今日任务：<b>{task}</b></span></div>')


def guide(text: str) -> str:
    return (f'<div class="guide"><div class="bubble">{text}</div>'
            '<svg width="34" height="34" viewBox="0 0 16 16" shape-rendering="crispEdges">'
            '<rect x="4" y="3" width="8" height="7" fill="#E7D9BE"/>'
            '<rect x="5" y="4" width="2" height="2" fill="#3B3227"/>'
            '<rect x="9" y="4" width="2" height="2" fill="#3B3227"/>'
            '<rect x="7" y="7" width="2" height="1" fill="#B9643F"/>'
            '<rect x="5" y="10" width="6" height="3" fill="#5E7F52"/>'
            '<rect x="4" y="2" width="8" height="1" fill="#5E7F52"/>'
            '<rect x="7" y="1" width="2" height="1" fill="#C8973F"/></svg></div>')


def badges_html(items: list[tuple[str, str]]) -> str:
    """items: [(文本, 'on'|'gold'|'')]"""
    out = []
    for text, kind in items:
        out.append(f'<span class="badge {kind}">{text}</span>')
    return '<div class="badges">' + "".join(out) + "</div>"


def stamps(items: list[dict]) -> str:
    """items: [{name, on}]"""
    cells = []
    for it in items:
        cls = "stamp on" if it["on"] else "stamp locked"
        label = it["name"] if it["on"] else "待发现"
        cells.append(f'<div class="{cls}">{label}</div>')
    return '<div class="stamps">' + "".join(cells) + "</div>"
