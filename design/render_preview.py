# -*- coding: utf-8 -*-
"""UI v2 静态设计图（PIL）。中文用雅黑，等宽只给 ASCII；色带先量高再画，避免重叠。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W = 1280
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
    def __init__(self):
        self.img = Image.new("RGB", (W, 3000), BG)
        self.d = ImageDraw.Draw(self.img)
        self.y = 0

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

    def bowl(self, cx, cy, s=1.0):
        """热汤面插画：cy 为碗沿中心。"""
        d = self.d
        R = 108 * s
        ry = 22 * s
        H = 96 * s
        ink = max(3, int(3 * s))

        # 投影
        d.ellipse((cx - R * .95, cy + H + 6 * s, cx + R * .95, cy + H + 30 * s), fill="#EADFC8")
        # 碗身（梯形）
        d.polygon([(cx - R, cy), (cx + R, cy), (cx + R * .68, cy + H), (cx - R * .68, cy + H)],
                  fill="#FFFDF8", outline=INK, width=ink)
        # 碗底
        d.ellipse((cx - R * .68, cy + H - 10 * s, cx + R * .68, cy + H + 8 * s),
                  fill="#FFFDF8", outline=INK, width=ink)
        # 碗沿
        d.ellipse((cx - R, cy - ry, cx + R, cy + ry), fill="#FFFDF8", outline=INK, width=ink)
        # 汤面
        d.ellipse((cx - R * .88, cy - ry * .82, cx + R * .88, cy + ry * .82), fill="#E0A17C")
        d.ellipse((cx - R * .88, cy - ry * .82, cx + R * .88, cy - ry * .1), fill="#CB8B66")
        # 面条（弧线）
        for k in range(3):
            off = (k - 1) * 9 * s
            d.arc((cx - R * .62 + off, cy - ry * .62 + off * .3,
                   cx + R * .5 + off, cy + ry * .62 + off * .3),
                  start=200, end=340, fill="#F5E6C4", width=max(3, int(4 * s)))
        # 蛋
        d.ellipse((cx - 34 * s, cy - 12 * s, cx + 2 * s, cy + 12 * s), fill="#FFFDF8")
        d.ellipse((cx - 20 * s, cy - 6 * s, cx - 8 * s, cy + 6 * s), fill="#E8B44E")
        # 青菜
        d.ellipse((cx + 26 * s, cy - 14 * s, cx + 62 * s, cy + 4 * s), fill="#5E7F52")
        d.ellipse((cx + 40 * s, cy - 18 * s, cx + 58 * s, cy - 4 * s), fill="#4E6B44")
        # 筷子
        d.line((cx + 62 * s, cy - 92 * s, cx + 96 * s, cy + 2 * s), fill="#B9643F", width=max(3, int(4 * s)))
        d.line((cx + 76 * s, cy - 96 * s, cx + 104 * s, cy - 2 * s), fill="#B9643F", width=max(3, int(4 * s)))
        # 蒸汽
        for dx, dy, rr in ((-30, -58, 9), (-14, -76, 10), (8, -62, 8)):
            d.ellipse((cx + dx * s - rr * s, cy + dy * s - rr * s,
                       cx + dx * s + rr * s, cy + dy * s + rr * s),
                      fill="#FFFFFF", outline="#EADFC8", width=max(2, int(2 * s)))

    def plate(self, cx, cy, s=1.0, main="#E3A57F"):
        u = 4.6 * s
        d = self.d
        def e(x, y, rx, ry, c):
            d.ellipse((cx + (x - rx) * u, cy + (y - ry) * u,
                       cx + (x + rx) * u, cy + (y + ry) * u), fill=c)
        e(0, 8, 20, 4, "#EADFC8")
        e(0, 2, 20, 9, SURFACE)
        e(0, 2, 17, 7, "#F3E8D2")
        e(-4, 1, 8, 4, main); e(6, 3, 5, 3, main)
        e(-8, 3, 4, 2, LEAF); e(9, 0, 3, 2, LEAF)
        d.rectangle((cx - 2 * u, cy - 5 * u, cx + 2 * u, cy - 2 * u), fill=GOLD)


def build():
    c = C()
    M = 120
    L, R = M, W - M
    d = c.d

    # 导航
    d.rectangle((0, 0, W, 62), fill="#FBF7EF")
    d.line((0, 62, W, 62), fill=LINE)
    d.rounded_rectangle((L, 17, L + 28, 45), radius=5, fill=SURFACE2, outline=LINE)
    d.rectangle((L + 7, 27, L + 21, 30), fill=INK)
    c.t(L + 38, 31, "知源食养", 19, INK, True, "lm")
    x = R
    for item in reversed(["体质参考", "忌口设置", "今日推荐", "饮食记录"]):
        w = d.textlength(item, font=ft(item, 15)); x -= w
        c.t(x, 31, item, 15, LEAF if item == "体质参考" else INK2, anchor="lm"); x -= 28
    y = 96

    # 首屏
    c.t(L, y, "日常食养参考", 12, CLAY); y += 26
    c.t(L, y, "今天吃什么，", 40, INK, True); y += 54
    c.t(L, y, "先看看身体感受", 40, INK, True); y += 66
    y = c.p(L, y, "根据你最近两周的状态，从食堂菜品里挑出更合适的那几道。", 16, INK2, 520, 28)
    y = c.p(L, y + 2, "每条建议都附带食材与依据，仅作日常饮食参考。", 16, INK2, 520, 28)
    y += 16
    w1 = c.btn(L, y, "开始选择", 16, True)
    c.btn(L + w1 + 12, y, "查看今日推荐", 16, False)
    c.bowl(R - 150, y - 70, 1.0)
    c.t(R - 150, y + 66, "一碗热的，比什么建议都实在", 12, INK3, anchor="mm")
    y += 104

    # 状态
    c.t(L, y, "STEP 01", 11, INK3); y += 20
    c.t(L, y, "最近两周，你更像哪种状态？", 24, INK, True); y += 32
    c.p(L, y, "按最近的实际感受选，可以多选。这些只是饮食参考的起点，不是诊断。", 14, INK2, 760, 22)
    y += 42

    cw = (R - L - 32) // 3
    cards = [("容易疲倦", "睡够了也不解乏，下午三四点最沉。", "近两周 5 天以上", .78, LEAF, True),
             ("容易口干", "总觉得想喝水，嘴里发黏或发苦。", "近两周 3 天以上", .52, GOLD, False),
             ("消化负担较重", "饭后容易胀，油腻的吃不下太多。", "近两周 4 天以上", .64, CLAY, False)]
    ch = 156
    for i, (title, desc, meta, pct, col, on) in enumerate(cards):
        x = L + i * (cw + 16)
        c.card((x, y, x + cw, y + ch), border=LEAF if on else LINE, w=2 if on else 1)
        d.rounded_rectangle((x + 16, y + 16, x + 44, y + 44), radius=5,
                            fill=LEAF_SOFT if on else SURFACE2, outline=LINE)
        d.rectangle((x + 25, y + 27, x + 35, y + 32), fill=col)
        c.t(x + 54, y + 30, title, 16, INK, True, "lm")
        c.p(x + 16, y + 56, desc, 13, INK2, cw - 32, 21)
        d.rounded_rectangle((x + 16, y + 108, x + cw - 16, y + 114), radius=3, fill=SURFACE2)
        d.rounded_rectangle((x + 16, y + 108, x + 16 + (cw - 32) * pct, y + 114), radius=3, fill=col)
        c.t(x + 16, y + 126, meta, 12, INK3)
        if on:
            c.t(x + cw - 16, y + 126, "已选择", 12, LEAF, anchor="ra")
    y += ch + 40

    # 忌口（先画带，再画内容）
    band_h = 244
    d.rectangle((0, y, W, y + band_h), fill=SURFACE2)
    d.line((0, y, W, y), fill=LINE); d.line((0, y + band_h, W, y + band_h), fill=LINE)
    yy = y + 28
    c.t(L, yy, "STEP 02", 11, INK3); yy += 20
    c.t(L, yy, "忌口与饮食偏好", 24, INK, True); yy += 32
    c.p(L, yy, "可以多选，也可以什么都不选。选中的会直接从推荐里排除不符合的菜。", 14, INK2, 760, 22)
    yy += 40
    cx = L
    for label, on in [("纯素", False), ("蛋奶素", False), ("不吃辣", True),
                      ("无麸质", False), ("不吃苦味", False)]:
        w = int(d.textlength(label, font=ft(label, 15)) + 62)
        d.rounded_rectangle((cx, yy, cx + w, yy + 44), radius=7,
                            fill=LEAF_SOFT if on else SURFACE, outline=LEAF if on else LINE)
        d.rounded_rectangle((cx + 14, yy + 13, cx + 32, yy + 31), radius=4,
                            fill=LEAF if on else SURFACE, outline=LEAF if on else "#B8AB93", width=2)
        if on:
            d.line((cx + 19, yy + 22, cx + 23, yy + 26), fill="#FFFFFF", width=2)
            d.line((cx + 23, yy + 26, cx + 28, yy + 17), fill="#FFFFFF", width=2)
        c.t(cx + 42, yy + 22, label, 15, INK, anchor="lm")
        cx += w + 12
    c.t(L, yy + 60, "已选 1 项   ·   当前范围：全部档口   ·   筛选后候选 106 道", 13, INK2)
    y += band_h + 40

    # 推荐
    c.t(L, y, "STEP 03", 11, INK3)
    c.t(L, y + 20, "今日食养推荐", 24, INK, True)
    c.p(L, y + 58, "只给三道，避免选择过载。每道都写清为什么、含什么、大概多少热量。", 14, INK2, 760, 22)
    c.btn(R - 100, y + 18, "换一批", 13, False, w=100, h=40)
    y += 102

    cw = (R - L - 36) // 3
    ch = 420
    dishes = [
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
    for i, (tag, kcal, name, metas, why, aller, price, tcol, tbg, tbd, main) in enumerate(dishes):
        x = L + i * (cw + 18)
        c.card((x, y, x + cw, y + ch))
        c.pill(x + 16, y + 16, tag, tcol, tbg, tbd)
        c.t(x + cw - 16, y + 28, kcal, 12, INK3, anchor="ra")
        d.rounded_rectangle((x + 16, y + 54, x + cw - 16, y + 182), radius=7, fill=SURFACE2)
        c.plate(x + cw / 2, y + 112, 0.95, main=main)
        c.t(x + 16, y + 196, name, 20, INK, True)
        cx2 = x + 16
        for mt in metas:
            w2 = int(d.textlength(mt, font=ft(mt, 12)) + 20)
            d.rounded_rectangle((cx2, y + 230, cx2 + w2, y + 256), radius=5, fill=SURFACE2)
            c.t(cx2 + 10, y + 243, mt, 12, INK2, anchor="lm")
            cx2 += w2 + 8
        c.p(x + 16, y + 272, why, 13, INK2, cw - 32, 22)
        d.line((x + 16, y + 344, x + cw - 16, y + 344), fill=LINE)
        c.p(x + 16, y + 354, aller, 12, INK3, cw - 32, 19)
        c.t(x + 16, y + 396, price, 15, INK, True, "lm")
        c.btn(x + cw - 96, y + 378, "换一道", 12, False, w=80, h=36)
    y += ch + 44

    # 记录（先画带）
    band_h = 336
    d.rectangle((0, y, W, y + band_h), fill=SURFACE2)
    d.line((0, y, W, y), fill=LINE); d.line((0, y + band_h, W, y + band_h), fill=LINE)
    yy = y + 28
    c.t(L, yy, "STEP 04", 11, INK3); yy += 20
    c.t(L, yy, "接下来两周，记三件事", 24, INK, True); yy += 32
    c.p(L, yy, "吃饭后的感受，一天一记。记录只存在本机，不关联身份，也不作为诊断依据。", 14, INK2, 760, 22)
    yy += 42

    pw = (R - L - 20) // 2
    c.card((L, yy, L + pw, yy + 168))
    c.t(L + 18, yy + 16, "近 7 天感受", 16, INK, True)
    c.t(L + 18, yy + 42, "数字是你自己打勾的天数", 12, INK3)
    ry = yy + 68
    for lab, val, pct, col in [("饭后舒适", "5 / 7 天", .71, LEAF),
                               ("排便规律", "4 / 7 天", .57, GOLD),
                               ("下午精力", "3 / 7 天", .43, CLAY)]:
        c.t(L + 18, ry, lab, 12, INK2)
        c.t(L + pw - 18, ry, val, 12, INK, anchor="ra")
        d.rounded_rectangle((L + 18, ry + 20, L + pw - 18, ry + 28), radius=4, fill=SURFACE2)
        d.rounded_rectangle((L + 18, ry + 20, L + 18 + (pw - 36) * pct, ry + 28), radius=4, fill=col)
        ry += 32

    x2 = L + pw + 20
    c.card((x2, yy, x2 + pw, yy + 168))
    c.t(x2 + 18, yy + 16, "14 天日历", 16, INK, True)
    c.t(x2 + 18, yy + 42, "点一下就算当天记过；灰色是还没到", 12, INK3)
    dw = (pw - 36 - 6 * 8) // 7
    for i in range(14):
        r_, c_ = divmod(i, 7)
        dx = x2 + 18 + c_ * (dw + 8)
        dy = yy + 64 + r_ * (dw + 8)
        on = i < 5
        d.rounded_rectangle((dx, dy, dx + dw, dy + dw), radius=4,
                            fill=LEAF if on else SURFACE, outline=LEAF if on else LINE)
        c.t(dx + dw / 2, dy + dw / 2, str(i + 1), 11, "#FFFFFF" if on else INK3, anchor="mm")
    y += band_h + 36

    # 提示
    c.card((L, y, R, y + 122), fill=GOLD_SOFT, border="#E8D5A8")
    d.rounded_rectangle((L + 22, y + 24, L + 58, y + 88), radius=5, fill=SURFACE, outline=INK)
    for k in range(3):
        d.rectangle((L + 30 + k * 8, y + 38, L + 36 + k * 8, y + 42), fill=CLAY)
    c.t(L + 76, y + 30, "这是一份饮食参考，不是诊断", 17, "#5F4A22", True)
    c.p(L + 76, y + 62,
        "本系统只根据你填写的状态，从菜品里做饮食搭配参考，不用于诊断、开方，也不替代医生。"
        "如果出现持续不适、明显症状或过敏反应，请及时就医。",
        14, "#5F4A22", R - L - 110, 24)
    y += 122 + 36

    d.line((0, y, W, y), fill=LINE)
    c.t(L, y + 22, "知源食养 · 日常食养参考", 13, INK3)
    c.t(R, y + 22, "沙河校区 · 数据 321 条 · 规则 19 条", 12, INK3, anchor="ra")
    y += 62

    return c.img.crop((0, 0, W, y))


if __name__ == "__main__":
    img = build()
    out = Path(Path(__file__).resolve().parent / "preview-v2.png")
    img.save(out, quality=95)
    print("saved", out, img.size)
