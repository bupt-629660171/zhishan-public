# -*- coding: utf-8 -*-
"""v3 设计图：桌面端整页 + 移动端布局示意（PIL 绘制，沙箱无法截图）。

输出：
  design/preview-v3-desktop.png
  design/preview-v3-mobile.png
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG, SURFACE, SURFACE2 = "#FAF6EE", "#FFFDF8", "#F5EFE2"
LINE, INK, INK2, INK3 = "#E4DBC9", "#2B251E", "#6B6152", "#8C8171"
LEAF, LEAF_SOFT = "#5E7F52", "#E7EEDF"
CLAY, CLAY_SOFT = "#B9643F", "#F6E3D8"
GOLD, GOLD_SOFT = "#C8973F", "#F7ECD5"
FD = Path(r"C:\Windows\Fonts")


def ft(s, size, bold=False):
    if all(ord(c) < 128 for c in s):
        return ImageFont.truetype(str(FD / "consola.ttf"), size)
    return ImageFont.truetype(str(FD / ("msyhbd.ttc" if bold else "msyh.ttc")), size)


class C:
    def __init__(self, w, h=3000):
        self.w = w
        self.img = Image.new("RGB", (w, h), BG)
        self.d = ImageDraw.Draw(self.img)

    def t(self, x, y, s, size=15, color=INK, bold=False, anchor="la"):
        self.d.text((x, y), s, font=ft(s, size, bold), fill=color, anchor=anchor)

    def wrap(self, s, size, width):
        f = ft(s, size)
        out, cur = [], ""
        for ch in s:
            if self.d.textlength(cur + ch, font=f) > width:
                out.append(cur); cur = ch
            else:
                cur += ch
        if cur:
            out.append(cur)
        return out

    def p(self, x, y, s, size=15, color=INK2, width=600, lh=26):
        for ln in self.wrap(s, size, width):
            self.t(x, y, ln, size, color); y += lh
        return y

    def card(self, box, fill=SURFACE, border=LINE, r=8, w=1):
        self.d.rounded_rectangle(box, radius=r, fill=fill, outline=border, width=w)

    def btn(self, x, y, label, size=15, primary=True, w=None, h=46):
        w = w or int(self.d.textlength(label, font=ft(label, size)) + 44)
        self.d.rounded_rectangle((x, y, x + w, y + h), radius=7,
                                 fill=LEAF if primary else SURFACE,
                                 outline="#4E6B44" if primary else LINE)
        self.t(x + w / 2, y + h / 2, label, size, "#FFFFFF" if primary else INK2, True, "mm")
        return w

    def pill(self, x, y, label, fg, bg, border):
        w = int(self.d.textlength(label, font=ft(label, 12)) + 40)
        self.d.rounded_rectangle((x, y, x + w, y + 28), radius=14, fill=bg, outline=border)
        self.d.ellipse((x + 12, y + 11, x + 18, y + 17), fill=fg)
        self.t(x + 24, y + 14, label, 12, fg, True, "lm")

    def tag(self, x, y, label, done=True):
        fg = LEAF if done else CLAY
        bg = LEAF_SOFT if done else CLAY_SOFT
        bd = "#CBDCC0" if done else "#EBC7B6"
        w = int(self.d.textlength(label, font=ft(label, 11)) + 18)
        self.d.rounded_rectangle((x, y, x + w, y + 22), radius=11, fill=bg, outline=bd)
        self.t(x + 9, y + 11, label, 11, fg, anchor="lm")
        return w

    def bowl(self, cx, cy, s=1.0):
        d = self.d
        R, ry, H = 86 * s, 18 * s, 78 * s
        ink = max(2, int(2.5 * s))
        d.ellipse((cx - R * .9, cy + H + 4 * s, cx + R * .9, cy + H + 24 * s), fill="#EADFC8")
        d.polygon([(cx - R, cy), (cx + R, cy), (cx + R * .66, cy + H), (cx - R * .66, cy + H)],
                  fill=SURFACE, outline=INK, width=ink)
        d.ellipse((cx - R * .66, cy + H - 8 * s, cx + R * .66, cy + H + 6 * s),
                  fill=SURFACE, outline=INK, width=ink)
        d.ellipse((cx - R, cy - ry, cx + R, cy + ry), fill=SURFACE, outline=INK, width=ink)
        d.ellipse((cx - R * .88, cy - ry * .8, cx + R * .88, cy + ry * .8), fill="#E0A17C")
        d.ellipse((cx - R * .88, cy - ry * .8, cx + R * .88, cy - ry * .05), fill="#CB8B66")
        for k in range(3):
            o = (k - 1) * 7 * s
            d.arc((cx - R * .6 + o, cy - ry * .6 + o * .3, cx + R * .48 + o, cy + ry * .6 + o * .3),
                  start=200, end=340, fill="#F5E6C4", width=max(2, int(3 * s)))
        d.ellipse((cx - 26 * s, cy - 9 * s, cx + 2 * s, cy + 9 * s), fill=SURFACE)
        d.ellipse((cx - 15 * s, cy - 4 * s, cx - 6 * s, cy + 4 * s), fill="#E8B44E")
        d.ellipse((cx + 20 * s, cy - 11 * s, cx + 48 * s, cy + 3 * s), fill=LEAF)
        d.line((cx + 50 * s, cy - 72 * s, cx + 78 * s, cy + 2 * s), fill=CLAY, width=max(2, int(3 * s)))
        d.line((cx + 62 * s, cy - 76 * s, cx + 86 * s, cy - 2 * s), fill=CLAY, width=max(2, int(3 * s)))
        for dx, dy, rr in ((-22, -42, 6), (-10, -56, 7), (6, -46, 5)):
            d.ellipse((cx + dx * s - rr * s, cy + dy * s - rr * s,
                       cx + dx * s + rr * s, cy + dy * s + rr * s),
                      fill="#FFFFFF", outline="#EADFC8", width=1)

    def guide(self, x, y, size=40, bubble=None):
        d = self.d
        if bubble:
            bw = int(self.d.textlength(bubble, font=ft(bubble, 12)) + 22)
            d.rounded_rectangle((x, y + 4, x + bw, y + 40), radius=7, fill=SURFACE, outline=LINE)
            self.t(x + 11, y + 22, bubble, 12, INK2, anchor="lm")
            x += bw + 8
        u = size / 16
        def r(a, b, w, h, c):
            d.rectangle((x + a * u, y + b * u, x + (a + w) * u, y + (b + h) * u), fill=c)
        r(4, 3, 8, 7, "#E7D9BE"); r(5, 4, 2, 2, INK); r(9, 4, 2, 2, INK)
        r(7, 7, 2, 1, CLAY); r(5, 10, 6, 3, LEAF); r(4, 2, 8, 1, LEAF); r(7, 1, 2, 1, GOLD)

    def plate(self, cx, cy, s=1.0, main="#E3A57F"):
        d = self.d
        u = 4.6 * s
        def e(x, y, rx, ry, c):
            d.ellipse((cx + (x - rx) * u, cy + (y - ry) * u,
                       cx + (x + rx) * u, cy + (y + ry) * u), fill=c)
        e(0, 8, 20, 4, "#EADFC8"); e(0, 2, 20, 9, SURFACE); e(0, 2, 17, 7, "#F3E8D2")
        e(-4, 1, 8, 4, main); e(6, 3, 5, 3, main)
        e(-8, 3, 4, 2, LEAF); e(9, 0, 3, 2, LEAF)
        d.rectangle((cx - 2 * u, cy - 5 * u, cx + 2 * u, cy - 2 * u), fill=GOLD)


def nav(c, links=True, h=62):
    W = c.w
    d = c.d
    d.rectangle((0, 0, W, h), fill="#FBF7EF")
    d.line((0, h, W, h), fill=LINE)
    m = 24 if W < 700 else 120
    d.rounded_rectangle((m, 17, m + 28, 45), radius=5, fill=SURFACE2, outline=LINE)
    d.rectangle((m + 7, 27, m + 21, 30), fill=INK)
    c.t(m + 38, 31, "知源食养", 19 if W > 700 else 17, INK, True, "lm")
    if links:
        x = W - m
        for item in reversed(["体质参考", "忌口设置", "今日推荐", "饮食记录"]):
            w = d.textlength(item, font=ft(item, 15)); x -= w
            c.t(x, 31, item, 15, LEAF if item == "体质参考" else INK2, anchor="lm")
            x -= 28
    else:
        d.rounded_rectangle((W - m - 34, 16, W - m, 46), radius=6, fill=SURFACE, outline=LINE)
        for k in range(3):
            d.rectangle((W - m - 25, 23 + k * 6, W - m - 9, 25 + k * 6), fill=INK)
    return h


def hero(c, y, L, R, compact=False):
    d = c.d
    c.t(L, y, "日常食养参考", 11 if compact else 12, CLAY); y += 24 if compact else 26
    c.t(L, y, "今天吃什么，", 30 if compact else 40, INK, True); y += 40 if compact else 54
    c.t(L, y, "先看看身体感受", 30 if compact else 40, INK, True); y += 48 if compact else 66
    y = c.p(L, y, "根据你最近两周的状态，从食堂菜品里挑出更合适的那几道。",
            14 if compact else 16, INK2, R - L, 24 if compact else 28)
    y = c.p(L, y + 2, "每条建议都附带食材与依据，仅作日常饮食参考。",
            14 if compact else 16, INK2, R - L, 24 if compact else 28)
    y += 14
    if compact:
        c.btn(L, y, "开始选择", 15, True, w=int((R - L - 10) / 2))
        c.btn(L + int((R - L - 10) / 2) + 10, y, "查看推荐", 15, False, w=int((R - L - 10) / 2))
        y += 58
    else:
        w1 = c.btn(L, y, "开始选择", 16, True)
        c.btn(L + w1 + 12, y, "查看今日推荐", 16, False)
        y += 58
        c.bowl(R - 160, y - 128, 0.95)
        c.t(R - 160, y - 20, "一碗热的，比什么建议都实在", 11, INK3, anchor="mm")
        c.guide(R - 250, y + 96, 34, "先选身体感受，我帮你挑")

    # 进度卡
    c.card((L, y + (30 if not compact else 4), R, y + (86 if not compact else 60)))
    py = y + (30 if not compact else 4)
    c.t(L + 16, py + 12, "本周记录", 12, INK2)
    c.t(L + 68, py + 8, "5", 15, INK, True)
    c.t(L + 82, py + 12, "/ 14 天", 12, INK2)
    sx = L + 150 if not compact else L + 16
    sy = py + 18 if not compact else py + 34
    for i in range(14):
        x = sx + i * 18
        col = LEAF if i < 5 else (GOLD if i == 5 else SURFACE2)
        bd = LEAF if i < 5 else (GOLD if i == 5 else LINE)
        d.rounded_rectangle((x, sy, x + 12, sy + 8), radius=2, fill=col, outline=bd)
    if not compact:
        c.t(R - 16, py + 12, "今日任务：记录晚饭", 12, INK2, anchor="ra")
    else:
        c.t(L + 16, py + 44, "今日任务：记录晚饭", 12, INK2)
        c.guide(L, py + 70, 30, "先选身体感受，我帮你挑")
    return y + (86 if not compact else 60) + (84 if compact else 36)


def states(c, y, L, R, compact=False):
    c.t(L, y, "STEP 01", 10, INK3)
    c.tag(L + 62, y - 4, "✓ 已完成")
    y += 22
    c.t(L, y, "最近两周，你更像哪种状态？", 22 if compact else 24, INK, True)
    y += 30
    c.p(L, y, "按最近的实际感受选，可以多选。这些只是饮食参考的起点，不是诊断。",
        13, INK2, R - L, 22)
    y += 38

    items = [("容易疲倦", "睡够了也不解乏，下午三四点最沉。", "近两周出现 5 天", .78, LEAF, True),
             ("容易口干", "总觉得想喝水，嘴里发黏或发苦。", "近两周出现 3 天", .52, GOLD, False),
             ("消化负担较重", "饭后容易胀，油腻的吃不下太多。", "近两周出现 4 天", .64, CLAY, False)]
    if compact:
        for title, desc, meta, pct, col, on in items:
            c.card((L, y, R, y + 96), border=LEAF if on else LINE, w=2 if on else 1)
            c.d.rounded_rectangle((L + 14, y + 14, L + 40, y + 40), radius=5,
                                  fill=LEAF_SOFT if on else SURFACE2, outline=LINE)
            c.d.rectangle((L + 22, y + 25, L + 32, y + 30), fill=col)
            c.t(L + 48, y + 26, title, 15, INK, True, "lm")
            c.p(L + 14, y + 48, desc, 12, INK2, R - L - 28, 19)
            c.d.rounded_rectangle((L + 14, y + 76, R - 14, y + 81), radius=3, fill=SURFACE2)
            c.d.rounded_rectangle((L + 14, y + 76, L + 14 + (R - L - 28) * pct, y + 81), radius=3, fill=col)
            c.t(R - 14, y + 64, meta, 11, INK3, anchor="ra")
            y += 108
    else:
        cw = (R - L - 32) // 3
        for i, (title, desc, meta, pct, col, on) in enumerate(items):
            x = L + i * (cw + 16)
            c.card((x, y, x + cw, y + 150), border=LEAF if on else LINE, w=2 if on else 1)
            c.d.rounded_rectangle((x + 16, y + 14, x + 44, y + 42), radius=5,
                                  fill=LEAF_SOFT if on else SURFACE2, outline=LINE)
            c.d.rectangle((x + 25, y + 25, x + 35, y + 30), fill=col)
            c.t(x + 54, y + 28, title, 16, INK, True, "lm")
            c.p(x + 16, y + 54, desc, 13, INK2, cw - 32, 21)
            c.d.rounded_rectangle((x + 16, y + 104, x + cw - 16, y + 110), radius=3, fill=SURFACE2)
            c.d.rounded_rectangle((x + 16, y + 104, x + 16 + (cw - 32) * pct, y + 110), radius=3, fill=col)
            c.t(x + 16, y + 122, meta, 11, INK3)
            if on:
                c.t(x + cw - 16, y + 122, "已选择", 11, LEAF, anchor="ra")
        y += 150
    return y + 34


def diet(c, y, L, R, compact=False):
    band_h = 210 if compact else 232
    c.d.rectangle((0, y, c.w, y + band_h), fill=SURFACE2)
    c.d.line((0, y, c.w, y), fill=LINE)
    c.d.line((0, y + band_h, c.w, y + band_h), fill=LINE)
    yy = y + 26
    c.t(L, yy, "STEP 02", 10, INK3)
    c.tag(L + 62, yy - 4, "✓ 已完成")
    yy += 22
    c.t(L, yy, "忌口与饮食偏好", 22 if compact else 24, INK, True)
    yy += 30
    c.p(L, yy, "可以多选，也可以什么都不选。选中的会直接从推荐里排除不符合的菜。", 13, INK2, R - L, 22)
    yy += 36
    cx, row_y = L, yy
    for label, on in [("纯素", False), ("蛋奶素", False), ("不吃辣", True), ("无麸质", False), ("不吃苦味", False)]:
        w = int(c.d.textlength(label, font=ft(label, 14 if compact else 15)) + 54)
        if compact and cx + w > R:
            cx = L; row_y += 48
        c.d.rounded_rectangle((cx, row_y, cx + w, row_y + 40), radius=6,
                              fill=LEAF_SOFT if on else SURFACE, outline=LEAF if on else LINE)
        c.d.rounded_rectangle((cx + 12, row_y + 11, cx + 28, row_y + 27), radius=4,
                              fill=LEAF if on else SURFACE, outline=LEAF if on else "#B8AB93", width=2)
        if on:
            c.d.line((cx + 16, row_y + 19, cx + 20, row_y + 23), fill="#FFFFFF", width=2)
            c.d.line((cx + 20, row_y + 23, cx + 25, row_y + 15), fill="#FFFFFF", width=2)
        c.t(cx + 36, row_y + 20, label, 14 if compact else 15, INK, anchor="lm")
        cx += w + 10
    c.t(L, row_y + 54, "已选 1 项 · 全部档口 · 筛选后候选 106 道", 12, INK2)
    return y + band_h + 34


def today(c, y, L, R, compact=False, limit=3):
    c.t(L, y, "STEP 03", 10, INK3)
    c.tag(L + 62, y - 4, "待选择", done=False)
    c.t(L, y + 20, "今日食养推荐", 22 if compact else 24, INK, True)
    if not compact:
        c.p(L, y + 58, "只给三道，避免选择过载。每道都写清为什么、含什么、大概多少热量。", 14, INK2, 700, 22)
        c.btn(R - 100, y + 18, "换一批", 13, False, w=100, h=40)
    else:
        c.p(L, y + 52, "只给三道，避免选择过载。", 13, INK2, R - L, 22)
        c.btn(R - 92, y + 14, "换一批", 12, False, w=92, h=34)
    y += 96 if compact else 102

    cw = (R - L - 36) // 3
    ch = 404 if compact else 416
    data = [
        ("推荐", "约 210 千卡", "山药鸡汤", ["山药 · 鸡腿肉", "清淡", "温性"],
         "山药帮助增加饱腹感，汤水温润；适合近期容易疲倦、想吃点热的人。",
         "含禽肉；不含麸质、乳制品", "￥14", LEAF, LEAF_SOFT, "#CBDCC0", "#E3A57F"),
        ("推荐", "约 320 千卡", "五谷渔粉", ["米粉 · 鱼片", "鲜香", "平性"],
         "汤底温润、米粉好消化，适合饭量小又想吃得热乎的时候。",
         "含鱼类；可能含花生碎", "￥14", LEAF, LEAF_SOFT, "#CBDCC0", "#F0D9A8"),
        ("适量", "约 520 千卡", "黄焖鸡米饭", ["鸡腿肉 · 米饭", "咸鲜", "偏温"],
         "鸡肉顶饱，但汤汁油偏多。想吃得满足可以选，建议配一份青菜。",
         "含禽肉、大豆酱油；油脂较高", "￥14", "#7A5A1E", GOLD_SOFT, "#E8D5A8", CLAY),
    ]
    for i, (tag, kcal, name, metas, why, aller, price, tcol, tbg, tbd, main) in enumerate(data[:limit]):
        x = L if compact else L + i * (cw + 18)
        w = R - L if compact else cw
        c.card((x, y, x + w, y + ch))
        c.pill(x + 14, y + 14, tag, tcol, tbg, tbd)
        c.t(x + w - 14, y + 26, kcal, 11 if compact else 12, INK3, anchor="ra")
        c.d.rounded_rectangle((x + 14, y + 50, x + w - 14, y + 170), radius=7, fill=SURFACE2)
        c.plate(x + w / 2, y + 110, 0.95, main=main)
        c.t(x + 14, y + 184, name, 18 if compact else 20, INK, True)
        cx2 = x + 14
        for mt in metas:
            w2 = int(c.d.textlength(mt, font=ft(mt, 11)) + 18)
            c.d.rounded_rectangle((cx2, y + 214, cx2 + w2, y + 238), radius=5, fill=SURFACE2)
            c.t(cx2 + 9, y + 226, mt, 11, INK2, anchor="lm")
            cx2 += w2 + 6
        c.p(x + 14, y + 248, why, 12, INK2, w - 28, 20)
        c.d.line((x + 14, y + 318, x + w - 14, y + 318), fill=LINE)
        c.p(x + 14, y + 326, aller, 11, INK3, w - 28, 18)
        c.t(x + 14, y + 366, price, 14, INK, True, "lm")
        c.btn(x + w - 88, y + 348, "换一道", 11, False, w=74, h=32)
        y += ch + 18 if compact else 0
    if not compact:
        y += ch
    return y + 38


def codex(c, y, L, R, compact=False):
    band = 470 if compact else 300
    c.d.rectangle((0, y, c.w, y + band), fill=SURFACE2)
    c.d.line((0, y, c.w, y), fill=LINE)
    c.d.line((0, y + band, c.w, y + band), fill=LINE)
    yy = y + 24
    c.t(L, yy, "COLLECTION", 10, INK3); yy += 18
    c.t(L, yy, "本周发现", 22 if compact else 24, INK, True)
    c.tag(L + (108 if compact else 118), yy - 4, "4 / 8 已收集")
    yy += 30
    c.p(L, yy, "吃过或看过食材就会点亮一个。只是记录你的探索，不代表任何评价。", 12, INK2, R - L, 20)
    yy += 32

    # 分类标签
    tabs = [("全部", "4/8", True), ("谷物", "2/3", False), ("蔬菜", "1/3", False),
            ("肉蛋", "1/2", False), ("果品", "0/1", False)]
    tx = L
    for name, cnt, on in tabs:
        label = name + " " + cnt
        w = int(c.d.textlength(label, font=ft(label, 12)) + 26)
        if compact and tx + w > R:
            tx = L; yy += 36
        c.d.rounded_rectangle((tx, yy, tx + w, yy + 30), radius=15,
                              fill=LEAF_SOFT if on else SURFACE,
                              outline="#CBDCC0" if on else LINE)
        c.t(tx + 13, yy + 15, label, 12, "#3F5A36" if on else INK2, on, "lm")
        tx += w + 8
    yy += 44

    cols = 4 if compact else 8
    gap = 10
    size = (R - L - gap * (cols - 1)) // cols
    names = ["山药", "小米", "鸡肉", "青菜"]
    cols_colors = ["#C8973F", "#C8973F", "#B9643F", LEAF]
    rows = 2 if compact else 1
    for i in range(cols * rows):
        r_, c_ = divmod(i, cols)
        x = L + c_ * (size + gap)
        cy = yy + r_ * (size + gap)
        on = i < 4
        c.card((x, cy, x + size, cy + size), fill=SURFACE if on else SURFACE2, border=LINE, r=6)
        if on:
            c.d.ellipse((x + size - 20, cy + 5, x + size - 6, cy + 19), fill=LEAF)
            c.t(x + size - 13, cy + 12, "✓", 9, "#FFFFFF", anchor="mm")
            cxg, cyg = x + size // 2, cy + size // 2 - 6
            c.d.rectangle((cxg - 9, cyg - 6, cxg + 9, cyg + 6), fill=cols_colors[i])
            c.d.rectangle((cxg - 4, cyg - 10, cxg + 4, cyg - 6), fill=cols_colors[i])
            c.t(x + size / 2, cy + size - 16, names[i], 11, INK2, anchor="mm")
        else:
            c.t(x + size / 2, cy + size / 2 + 8, "待发现", 10, "#B0A48E", anchor="mm")
    yy += size * rows + gap * (rows - 1)

    # 分页条
    yy += 14
    c.t(L, yy + 8, "当前：全部 · 第 1 页，共 3 页", 11, INK3)
    c.d.rounded_rectangle((R - 92, yy, R - 58, yy + 30), radius=6, fill=SURFACE, outline=LINE)
    c.t(R - 75, yy + 15, "‹", 13, "#B0A48E", anchor="mm")
    c.t(R - 44, yy + 15, "1 / 3", 11, INK2, anchor="mm")
    c.d.rounded_rectangle((R - 30, yy, R, yy + 30), radius=6, fill=SURFACE, outline=LINE)
    c.t(R - 15, yy + 15, "›", 13, INK2, anchor="mm")
    return y + band + 32


def logsec(c, y, L, R, compact=False):
    h = 585 if compact else 372
    c.d.rectangle((0, y, c.w, y + h), fill=SURFACE2)
    c.d.line((0, y, c.w, y), fill=LINE)
    c.d.line((0, y + h, c.w, y + h), fill=LINE)
    yy = y + 26
    c.t(L, yy, "STEP 04", 10, INK3)
    c.tag(L + 62, yy - 4, "今日未记录", done=False)
    yy += 22
    c.t(L, yy, "接下来两周，记三件事", 22 if compact else 24, INK, True)
    yy += 32
    c.p(L, yy, "吃饭后的感受，一天一记。记录只存在本机，不关联身份，也不作为诊断依据。",
        13, INK2, R - L, 22)
    yy += 38

    # 徽章
    bw = R - L if compact else 0
    bx = L
    for label, extra, kind in [("连续记录", "3 天", LEAF_SOFT), ("完成今日选择", "", LEAF_SOFT),
                               ("发现新菜品", "2 个", GOLD_SOFT)]:
        text = label + (" " + extra if extra else "")
        w = int(c.d.textlength(text, font=ft(text, 12)) + 46)
        if compact and bx + w > R:
            bx = L; yy += 42
        c.d.rounded_rectangle((bx, yy, bx + w, yy + 34), radius=6,
                              fill=kind, outline="#CBDCC0" if kind == LEAF_SOFT else "#E8D5A8")
        c.d.rectangle((bx + 10, yy + 11, bx + 24, yy + 23), fill=LEAF if kind == LEAF_SOFT else GOLD)
        c.t(bx + 32, yy + 17, text, 12, INK2, anchor="lm")
        bx += w + 8
    yy += 46

    if compact:
        c.card((L, yy, R, yy + 150))
        c.t(L + 16, yy + 14, "近 7 天感受", 15, INK, True)
        ry = yy + 42
        for lab, val, pct, col in [("饭后舒适", "5 / 7", .71, LEAF), ("排便规律", "4 / 7", .57, GOLD),
                                   ("下午精力", "3 / 7", .43, CLAY)]:
            c.t(L + 16, ry, lab, 11, INK2)
            c.t(R - 16, ry, val, 11, INK, anchor="ra")
            c.d.rounded_rectangle((L + 16, ry + 18, R - 16, ry + 24), radius=3, fill=SURFACE2)
            c.d.rounded_rectangle((L + 16, ry + 18, L + 16 + (R - L - 32) * pct, ry + 24), radius=3, fill=col)
            ry += 32
        yy += 166
        c.card((L, yy, R, yy + 150))
        c.t(L + 16, yy + 14, "14 天日历", 15, INK, True)
        dw = (R - L - 32 - 6 * 6) // 7
        for i in range(14):
            r_, c_ = divmod(i, 7)
            dx = L + 16 + c_ * (dw + 6)
            dy = yy + 44 + r_ * (dw + 6)
            on = i < 5
            today_ = i == 5
            c.d.rounded_rectangle((dx, dy, dx + dw, dy + dw), radius=3,
                                  fill=LEAF if on else SURFACE,
                                  outline=GOLD if today_ else (LEAF if on else LINE),
                                  width=2 if today_ else 1)
            c.t(dx + dw / 2, dy + dw / 2, str(i + 1), 10,
               "#FFFFFF" if on else (GOLD if today_ else INK3), anchor="mm")
        yy += 160
    else:
        pw = (R - L - 20) // 2
        c.card((L, yy, L + pw, yy + 196))
        c.t(L + 16, yy + 14, "近 7 天感受", 15, INK, True)
        ry = yy + 44
        for lab, val, pct, col in [("饭后舒适", "5 / 7 天", .71, LEAF), ("排便规律", "4 / 7 天", .57, GOLD),
                                   ("下午精力", "3 / 7 天", .43, CLAY)]:
            c.t(L + 16, ry, lab, 12, INK2)
            c.t(L + pw - 16, ry, val, 12, INK, anchor="ra")
            c.d.rounded_rectangle((L + 16, ry + 19, L + pw - 16, ry + 26), radius=3, fill=SURFACE2)
            c.d.rounded_rectangle((L + 16, ry + 19, L + 16 + (pw - 32) * pct, ry + 26), radius=3, fill=col)
            ry += 32

        x2 = L + pw + 20
        c.card((x2, yy, x2 + pw, yy + 196))
        c.t(x2 + 16, yy + 14, "14 天日历", 15, INK, True)
        dw = (pw - 32 - 6 * 7) // 7
        for i in range(14):
            r_, c_ = divmod(i, 7)
            dx = x2 + 16 + c_ * (dw + 7)
            dy = yy + 44 + r_ * (dw + 7)
            on = i < 5
            today_ = i == 5
            c.d.rounded_rectangle((dx, dy, dx + dw, dy + dw), radius=3,
                                  fill=LEAF if on else SURFACE,
                                  outline=GOLD if today_ else (LEAF if on else LINE),
                                  width=2 if today_ else 1)
            c.t(dx + dw / 2, dy + dw / 2, str(i + 1), 10,
               "#FFFFFF" if on else (GOLD if today_ else INK3), anchor="mm")
        c.t(x2 + 16, yy + 172, "已连续记录 3 天，今天记完是第 4 天", 11, INK3)
    return y + h + 32


def notice(c, y, L, R, compact=False):
    h = 118 if compact else 112
    c.card((L, y, R, y + h), fill=GOLD_SOFT, border="#E8D5A8")
    c.d.rounded_rectangle((L + 18, y + 20, L + 50, y + 80), radius=4, fill=SURFACE, outline=INK)
    for k in range(3):
        c.d.rectangle((L + 25 + k * 8, y + 34, L + 31 + k * 8, y + 38), fill=CLAY)
    c.t(L + 66, y + 24, "这是一份饮食参考，不是诊断", 15 if compact else 17, "#5F4A22", True)
    c.p(L + 66, y + 52,
        "本系统只根据你填写的状态，从菜品里做饮食搭配参考，不用于诊断、开方，也不替代医生。"
        "如出现持续不适、明显症状或过敏反应，请及时就医。",
        12 if compact else 14, "#5F4A22", R - L - 96, 20 if compact else 24)
    return y + h + 26


def build_desktop():
    c = C(1280, 3200)
    M = 120
    L, R = M, 1280 - M
    y = nav(c, links=True) + 34
    y = hero(c, y, L, R)
    y = states(c, y, L, R)
    y = diet(c, y, L, R)
    y = today(c, y, L, R, compact=False)
    y = codex(c, y, L, R)
    y = logsec(c, y, L, R)
    y = notice(c, y, L, R)
    c.d.line((0, y, 1280, y), fill=LINE)
    c.t(L, y + 20, "知源食养 · 日常食养参考", 13, INK3)
    c.t(R, y + 20, "沙河校区 · 数据 321 条 · 规则 19 条", 12, INK3, anchor="ra")
    y += 60
    return c.img.crop((0, 0, 1280, y))


def build_mobile():
    W = 390
    c = C(W, 3800)
    M = 18
    L, R = M, W - M
    y = nav(c, links=False, h=56) + 22
    y = hero(c, y, L, R, compact=True)
    y = states(c, y, L, R, compact=True)
    y = diet(c, y, L, R, compact=True)
    y = today(c, y, L, R, compact=True, limit=1)
    y = codex(c, y, L, R, compact=True)
    y = logsec(c, y, L, R, compact=True)
    y = notice(c, y, L, R, compact=True)
    c.d.line((0, y, W, y), fill=LINE)
    c.t(L, y + 18, "知源食养 · 日常食养参考", 11, INK3)
    y += 52
    return c.img.crop((0, 0, W, y))


if __name__ == "__main__":
    d = build_desktop()
    d.save(Path(Path(__file__).resolve().parent / "preview-v3-desktop.png"), quality=95)
    print("desktop", d.size)
    m = build_mobile()
    m.save(Path(Path(__file__).resolve().parent / "preview-v3-mobile.png"), quality=95)
    print("mobile", m.size)
