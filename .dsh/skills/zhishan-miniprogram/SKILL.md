---
name: zhishan-miniprogram
description: Use when building, changing, or debugging the 知源食养 WeChat mini program (miniprogram/) — adding a page, changing copy or styles, updating dishes/rules so the mini program stays in sync, or diagnosing a rendering/layout bug in WXML/WXSS. Encodes the zero-backend architecture, the single-source export pipeline, the mandatory Python-vs-JS parity check, WXML/WXSS limitations that bite, category/compliance red lines, and the release flow.
whenToUse: 要改小程序页面、样式、数据或判定；小程序显示不对；准备提交审核或发版；或要判断某个需求在小程序里做不做得了。
---

# 知源食养 · 小程序开发

先加载 `zhishan-playbook`（判定与数据规则）和 `zhishan-ui-design`（视觉令牌）。
本技能只管**小程序这一端**：架构、同步、WXML 限制、发布。

## 0. 三条不可动摇

1. **零后端**：判定在手机本地跑，不调 API、不需要域名与服务器。
2. **单一真源**：菜品、规则、题库全部由 Python 导出，小程序里**不手写业务数据**。
3. **对拍必过**：`node tools/parity_check.js` 必须 0 不一致，否则不许发版。

## 1. 架构

```
food.csv / rules.csv / constitution_quiz.py      ← 唯一真源
        │ init_db.py
        ▼
      food.db
        │ export_miniprogram.py / export_quiz.py
        ▼
miniprogram/data/db.js     菜品 + 标签 + 规则 + 忌口映射（约 104 KB）
miniprogram/data/quiz.js   11 道自评题
        │
miniprogram/utils/engine.js ← rule_engine.py 的 JS 移植
miniprogram/utils/quiz.js   ← constitution_quiz.py 的 JS 移植
        │
pages/index · quiz · result · record
```

**为什么不用后端**：321 菜 + 19 规则只有 104 KB，主包上限 2 MB；离线可用，食堂信号差也不怕；
没有服务器就没有隐私与费用问题。

## 2. 改数据后的完整链路

```powershell
python init_db.py
python tools/export_miniprogram.py
python tools/export_quiz.py
node tools/parity_check.js        # 必须 0 不一致
```

只改文案或样式时，跳过前三条，直接改 `pages/` 与 `app.wxss`。

## 3. 引擎移植的四条约定

- **动作优先级**：`禁 > 慎 > 宜`，命中多条取最高档；无命中按"宜"放行。
- **排序**：先按判定（宜在前），再看是否有"宜"类证据，最后按证据条数。
- **随机可复现**：不能用 `Math.random()`，必须自写线性同余生成器（LCG），
  否则同一条件每次推荐都不同，也无法对拍。
- **忌口优先于体质**：用户显式限制（素食/不吃辣）先剔除，再看体质判定。

## 4. WXML / WXSS 限制（最容易踩）

| 限制 | 后果 | 正确做法 |
|---|---|---|
| **不支持方法调用** | `list.indexOf(x)` 在模板里恒为 undefined，芯片永远不高亮 | JS 里预计算 `{name, on}`，模板只做 `item.on ?` |
| **不支持内联 SVG** | 插画无法直接搬网页稿 | 绝对定位方块拼（见 `buildBowl()`），或 base64 图片 |
| **`wx:key` 要稳定** | 用 `index` 会导致列表复用错乱 | 每项带唯一 `id` |
| **`onLoad` 只跑一次** | 从子页返回，父页状态不更新 | 用 `onShow` 重读全局状态 |
| **绝对定位不参与布局** | 文字压到插画上 | 文字容器给 `padding-right` 让位 |
| **浅色插画在浅色卡片上** | 填充与背景同色，只剩描边，像渲染错误 | 换深色底，或加对比描边 |

## 5. 布局自查三问

1. 插画和背景**对比够吗**？（白碗白底 = 隐形）
2. 文字区**给图让位了吗**？（`padding-right`）
3. 窄屏（iPhone SE / 12 mini）下标题**会不会折行压图**？

## 6. 分享

- 转发好友/群：页面实现 `onShareAppMessage`，否则右上角转发是灰的。
- 朋友圈：实现 `onShareTimeline`，打开是**单页模式**，只有这一页内容，底部有"前往小程序"。
- **全部免费**；认证 30 元/年只影响"被搜索"等能力，不影响分享。

## 7. 合规与类目（生死线）

- 类目必须选**「工具」**。选医疗健康要《医疗机构执业许可证》，个人拿不到。
- 界面文案**禁止**出现：体质辨识、调理、诊断、疗效。
  内部规则叫"禁/慎/宜"没问题，对外一律"推荐 / 适量 / 暂不建议"。
- 备案免费但必须做（1–20 个工作日），没备案不能发布。
- 数据全在本机、不采集身份，避免 PIPL 敏感个人信息问题。

## 8. 发布流程

1. 注册小程序（个人主体，免费）
2. 小程序备案（免费，等 1–20 工作日）
3. 微信开发者工具导入 `miniprogram/`（AppID 可先用测试号）
4. 上传 → 提交审核（1–3 天）→ 发布

**发版前必做**：对拍 0 不一致、真机预览一遍、检查文案红线。

## 9. 验收清单

- [ ] `node tools/parity_check.js` 结果为 0
- [ ] `python tools.py gate` 全绿
- [ ] 所有 JS `node --check` 通过
- [ ] 模板里没有 `.indexOf(`、`.map(`、`.filter(`
- [ ] 列表都有稳定 `wx:key`
- [ ] 真机上首屏不压字、按钮够大（≥ 88rpx）
- [ ] 分享卡片标题与路径正确
- [ ] 文案无医疗用语
