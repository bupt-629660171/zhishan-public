---
name: zhishan-ui-design
description: Use when designing or changing any 知源食养 interface — the Streamlit app, a standalone design mockup, a new screen or component, or a visual/interaction review. Encodes the palette and type tokens, the three-fold verdict encoding, the de-medicalized copy rules, the light-gamification boundary, responsive and state requirements, anti-patterns, and how design intent degrades for Streamlit.
whenToUse: 用户要改界面、出设计稿、加组件/页面、评审视觉或交互，或在"要不要加游戏化元素"上做取舍时。
---

# 知源食养 · 界面设计规则

先加载 `zhishan-playbook`。本技能只管**视觉与交互**；判定、数据、规则仍归 playbook 与 `zhishan-data-intake`。

## 0. 一句话立场

**这是饮食参考工具，不是医疗产品，也不是游戏。** 所有设计决定都要能通过这一条检验：
> 用户会不会误以为系统在给他做健康评分或疾病判断？

会，就砍掉。

## 1. 令牌（唯一来源：`ui_theme.py` / `design/zhishan-ui-v2.html`）

| 用途 | 值 |
|---|---|
| 背景 | `#FAF6EE` 暖白 |
| 卡片 | `#FFFDF8` |
| 次级面 | `#F5EFE2` |
| 分割线 | `#E4DBC9` |
| 正文 / 次要 / 辅助 | `#2B251E` / `#6B6152` / `#8C8171` |
| 主色（草绿） | `#5E7F52`，浅底 `#E7EEDF` |
| 辅助（陶土橙） | `#B9643F`，浅底 `#F6E3D8` |
| 点缀（浅金） | `#C8973F`，浅底 `#F7ECD5` |

- 圆角：**4–8px**（卡片 6–8，按钮 6，标签胶囊 999）
- 阴影：一层即可 `0 1px 0 rgba(59,50,39,.05), 0 2px 8px rgba(59,50,39,.06)`
- 边框：1px 实线；**不要 3px 以上黑边**
- 字体：中文 `PingFang SC / Microsoft YaHei`；等宽只给数字与编号（价格、天数、规则号）
- 正文 14–16px，辅助最小 11px

**禁用**：冷蓝、荧光色、高饱和撞色、大面积渐变、纹理堆叠、纯红纯绿。

## 2. 判定：三重编码，永不只靠颜色

| 档位（内部） | 展示文案 | 图标 | 底色 |
|---|---|---|---|
| 宜 | 推荐 | ✓ | 草绿浅底 |
| 慎 | 适量 | ! | 浅金底 |
| 禁 | 暂不建议 | ✕ | 陶土浅底 |

内部规则仍是 禁/慎/宜，**只改展示口径**——数据不动，说法变。

## 3. 文案：去医疗化

| 不要 | 要 |
|---|---|
| 你是气虚体质 | 最近两周你更像"容易疲倦"这一类 |
| 诊断 / 判定 / 证型 | 参考 / 倾向 / 近期感受 |
| 健康评分 / 风险等级 | （不出现任何分数） |
| 治疗 / 调理方案 / 疗效 | 饮食搭配参考 / 今天吃什么 |
| 忌口清单 | 忌口与饮食偏好 |

**每个页面至少一处**声明：仅作日常饮食参考，不用于诊断、开方、不替代医生；持续不适或过敏请就医。

## 4. 游戏化边界

**只做行为反馈，不做能力评价。**

允许：连续记录天数、完成今日选择、发现新食材、今日任务、14 天进度、图鉴收集、小勾/小印章、翻牌 260ms 级微动效。

禁止：经验值、等级、战力、排行榜、健康分、疾病评分、大型庆祝弹窗、全屏动画。

检验：徽章文案如果是"你很健康 85 分"→ 越界；如果是"连续记录 3 天"→ 可以。

## 5. 结构：四步任务流

```
STEP 01 体感状态（多选，写明"近两周出现 N 天"）
STEP 02 忌口偏好（复选框，实时计数）
STEP 03 今日推荐（三列卡片，每卡：判定/热量/食材/口味/温凉/理由/过敏原/价格/换一道）
STEP 04 两周记录（3 指标 + 14 天日历 + 徽章）
附：本周发现（图鉴，按类分组 + 分页 8 格）
```

- 每个 STEP 标头带状态签：`✓ 已完成` / `待完成` / `今日未记录`
- 首屏保留一句主张 + 两个按钮 + 一条本周进度；**不做营销式大 Hero**
- 日历：今日用金色描边 + 圆点标出，不只靠颜色

## 6. 交互与可达性

必须实现：`hover` / `active` / `selected`（`aria-pressed`）/ `disabled` / `:focus-visible`（3px 实色环）。

- 触控目标 ≥ 44px；移动端导航用**汉堡按钮**，不是隐藏菜单
- 动效 ≤ 300ms，且 `prefers-reduced-motion: reduce` 下全部关闭
- 分类/页码类控件用按钮 + `aria-pressed`，不要用 div 模拟

## 7. 反模式（评审直接打回）

营销大标题、满屏粗黑边框、装饰性卡片嵌套、像素化过度（正文也用像素字）、信息拥挤、小字号（<11px）、只用颜色表状态、移动端藏导航、中文乱码（必须 UTF-8）、RPG/卡牌/街机风、虚假数据感。

## 8. 设计稿 → Streamlit 的降级映射

| 设计稿 | Streamlit 实现 |
|---|---|
| 翻牌 / 闪烁 | 去掉，改用步骤状态签与按钮禁用态 |
| 自定义 focus 环 | 保留浏览器默认，不强行覆盖 |
| 三列卡片 | `st.columns`，移动端自动堆叠 |
| 图鉴网格 | HTML `.stamps` + `st.radio` 分类 + 按钮翻页 |
| 像素插画 | 内联 SVG（`shape-rendering="crispEdges"`） |
| 动效 | 仅保留 CSS 过渡，且尊重 reduce-motion |

## 9. 验收清单

- [ ] 颜色只来自令牌，页面里不出现裸色值
- [ ] 判定三档都有图标 + 文字 + 底色
- [ ] 每页有"不是诊断"声明
- [ ] 无分数、无等级、无排行榜
- [ ] 键盘可走完全流程，焦点可见
- [ ] 360px 宽不横向滚动，导航可展开
- [ ] 动效可被 reduce-motion 关闭
- [ ] `python tools.py gate` 全绿（文案一致性会拦"判禁却写可以吃"）
