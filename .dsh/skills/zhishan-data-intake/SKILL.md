---
name: zhishan-data-intake
description: Use when the 知源智膳 repo needs data added or corrected — canteen menu photos or LED boards, an Excel/CSV menu, a filled 待审核 sheet returning for approval, or an expansion from authoritative sources (卫健委药食同源目录/中国食物成分表) covering 基础食材 and 通用菜品. Encodes both intake lines, the Dish.kind split, tag-trigger pitfalls, gold-label expansion, Dish_Review audit, and the acceptance gate.
whenToUse: 用户发菜单照片/表格要求"提取数据导入库"、回传「待审核_*.xlsx」、要求"用权威数据补充食材/菜品"、扩金标，或做补价格/补档口/加别名这类数据维护时。
---

# 知源智膳 · 数据采集与入库

先加载 `zhishan-playbook`。本技能是它的"数据线"：**只改数据，不动规则**。若必须改规则才能得到正确判定，停下来报给用户，走 `tools.py review` 流程。

## 0. 两条数据线，同一套底线

| 线 | 输入 | 产出 |
|---|---|---|
| **A 食堂实采** | 档口照片、菜单表格 | 本校菜品 + 档口 + 价格 + 凭证照片 |
| **B 权威文献** | 药食同源目录、食物成分表、教材性味 | 基础食材（`kind=ingredient`）+ 通用菜品 |

底线三条：**不编造**（看不清就留空/不收录）、**不覆盖**（同名只加档口，不重写老菜语义）、**不抢审核**（性味/依据是待审数据，审核表交给用户填）。

## 1. 数据模型

```
Dish(id, name, property, explanation, calories, kind)   kind: dish | ingredient
Canteen(dish_id, location, window_name, price)          一条菜多个档口 → 多行
Dish_Tag(dish_id, tag, evidence, tag_version)           派生，规则消费方
Dish_Source(dish_id, source_type, source_ref, collected_by, collected_at, campus)
Dish_Review(id, dish_name, decision, reviewer, reviewed_at, comment)   审计日志，无外键
```

**`kind` 的语义**：`ingredient` 只能被查询，**不进推荐方案**（`plan()` 只取 `kind='dish'`）。不设这个区分，方案里会出现"今日推荐：生姜"。

## 2. 线 A：食堂实采

**读图**：先裁切放大再识别，比看压缩图准。

```python
from PIL import Image
im = Image.open(src); w, h = im.size
part = im.crop((int(0.23*w), int(0.28*h), int(0.87*w), int(0.50*h)))
part.resize((part.width*2, part.height*2), Image.LANCZOS).save(out, quality=95)
```

LED 屏会滚动/被挡板遮挡：价格被挡就留空；整行被切掉一半不要猜。

**读表**：`pandas.read_excel(dtype=str).fillna("")`，表头做中文映射（`菜名→name`、`性味→property`、`档口→location`、`价格→price`）。

**查重（必做）**：先 `SELECT name FROM Dish` 建集合。
- 已存在 → 只追加 `Canteen` 行，`property`/`explanation` 原样复制；
- 不存在 → 新菜；
- 档口分类（`一大荤一素`/`套餐`）→ 拒收；但菜名本身含"套餐"的真实菜（`麻辣烫13元套餐`）必须保留，用精确匹配而非子串。

**溯源**：`source_type=档口LED菜单`，`source_ref` 写**仓库内路径**，并先把照片复制进 `docs/sources/`。附件目录会被清理，只写附件路径等于没溯源。

## 3. 线 B：权威文献

**来源分级**（写进 `source_ref`，不要含糊）：

| 级 | 来源 | 用法 |
|---|---|---|
| 甲 | 卫健委/市场监管总局公告、国标 | 界定范围（如药食同源目录 102 种） |
| 乙 | 《中国食物成分表》标准版第 6 版 | 热量参考值，取整 |
| 丙 | 《中医饮食营养学》等教材通行性味 | 性味与食养要点，**必须标"待核对页码"** |

**边界**：只收普通食物 + 药食同源目录内物质。**不收黄芪、当归这类纯药材**，不写剂量、疗程、穴位。

**规模参考**：食材约 110~120 条 / 通用菜品约 80 条；`source_type=权威文献整理`，`campus=通用`，`location=全国通用`，`window_name=基础食材库` 或 `家常菜库`，价格留空。

## 4. 写 property / explanation（决定判定对错）

`property` 2~6 字，`explanation` 20~40 字。属性词会命中 `tags.py` 的正则，直接决定判定：

| 意图 | 必须用 | 不会触发 |
|---|---|---|
| 重油 | 重油、多油、油腻、高脂 | 偏油、带油、油厚 |
| 油炸 | 油炸、炸、煎、烤、熏 | 酥（除非"酥肉"） |
| 辛辣 | 辛辣、麻辣、辣椒、酸辣、辛温、黑椒、孜然 | 微辣、蒜蓉、青椒（→ mild_spicy） |
| 大热 | 大热、辛热、火毒 | 温热、偏温 |
| 寒 | 寒凉、大寒、微寒、性寒、**寒甘/寒苦/寒酸**（属性以寒开头）、生冷 | 凉、凉润（→ light） |
| 温燥 | 温燥、燥热、偏燥、上火、助热 | 偏温 |
| 清淡 | 清淡、少油、低脂、凉润、清热、利水、生津 | — |

**三个真踩过的坑**

1. **反向坑**：`少食/少吃/适量/可食` 触发 `moderate`，而 `SH_SUIT_MODERATE` 对湿热是「宜」——在依据里写"湿热者少吃"反而判「宜」。要么改措辞，要么同时给一个禁/慎证据词。
2. **跨字段伪词**：字段曾直接拼接，`温甘`+`温中` 拼出 `甘温` → 误判滋腻。现已改用 `｜` 分隔，不要再改回 `"".join`。
3. **短名反向包含**：`燕麦` 会命中 `燕麦拿铁`。反向包含（菜名在查询里）要求菜名 ≥3 字。

## 5. 落表 → 重建

```powershell
python init_db.py     # 导入 → 建表 → 规则 → 标签 → 忌口派生(Constraint_Rule)
```

必须用 `init_db.py`。跳过它直接改库，新数据不受"素食/无麸质/不吃辣"约束——门禁的素食用例会抓到。

## 6. 判定核对（必做）

对每批新增数据打印：标签 + 气虚判定 + 湿热判定 + 命中规则，逐条读：

- 判定与 `explanation` 是否一致（文字说"忌"、徽章却「宜」＝不一致）；
- 同一类（面食/寒性水果/温补肉）是否成梯度，还是一边倒；
- 分布要合理：寒凉类对气虚应偏「禁」，清淡蔬菜对湿热应偏「宜」。

异常时**先改 property/explanation 或 tags 关键词**，不要动 `rules.csv`。

## 7. 金标扩充（目标 80~120 条）

- 依据**文献性味**独立标注，**不许照抄引擎输出**；每条 `note` 写清为什么。
- 覆盖两种体质的「禁 / 非禁」两类，避免只有一类。
- 新增后 `python eval_metrics.py`；金标若大量失败，先查是不是评测漏算了新 `kind`。
- 当前基线：99 条、准确率 99/99；体质敏感度「仅气虚禁 21 / 仅湿热禁 17」。

## 8. 用户回传审核表

```powershell
python tools.py data-review 待审核_xxx.xlsx                 # dry-run
python tools.py data-review 待审核_xxx.xlsx --write --reviewer 姓名
python init_db.py && python tools.py gate
```

`data-review` 把「改性味/改依据」写回 `food.csv`，并把每条结论记进 `Dish_Review`；驳回的条目数据保持原样，需人工处理。

## 9. 收尾

```powershell
python tools.py gate        # 单测 + 六项指标 + 数据完整性
python tools.py quality     # 溯源覆盖、价格缺失、标签覆盖、kind 分布
git add -A && git commit    # 提交信息写：来源、条数、修了什么、指标变化
```

同时产出一份 `docs/数据采集_<日期>_<窗口>.md` 或 `docs/数据补充_<主题>_<日期>.md`：依据、规模、取舍理由、本次暴露的问题、待办。表格用脚本从库里生成，别手抄。

## 10. 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 方案里出现"生姜" | 食材未排除 | `kind='ingredient'` + `plan()` 过滤 |
| 门禁素食用例失败 | 未派生 `Constraint_Rule` | 用 `init_db.py` |
| 判定全变「宜」/「慎」 | 依据里写了 `适量/少食/可食` | 改措辞或补禁/慎证据词 |
| 属性写"寒甘"没被判寒 | `cold` 未认这种写法 | 已支持；改 tags 前先跑单测 |
| 「燕麦拿铁」查出「燕麦」 | 短名反向包含 | 已要求 ≥3 字 |
| 加金标后准确率暴跌 | 评测走 `plan()` 漏了食材 | 评测须对全表 `evaluate()` |
| 老菜被新数据覆盖 | 同名直接 upsert | 先查重，只加 `Canteen` |
| 价格显示 0 元 | 缺价格填了 `0` | 留空 → `NULL` |

## 11. 已知待裁决（不要擅自改）

1. **发物档位**：`SH_CAUTION_PHLEGM` 对湿热是「慎」，虾蟹鹅肉临床多建议避免——升「禁」属规则变更，需导师定。
2. **气虚被禁的温补品**：羊肉/羊杂因 `QX_NO_HEAT` 对气虚一票否决，与"气虚怕冷宜温补"冲突。
3. **热量与性味页码**：目前只到书名级，引用前需逐条回查。
