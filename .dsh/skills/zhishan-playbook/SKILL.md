---
name: zhishan-playbook
description: Use when working in the 知源智膳 (Zhiyuan Zhishan) TCM dietary assistant repo — changing rules.csv, tags.py, food.csv, the rule engine, AI explanation, evaluation gold labels, or anything that can change a dish's 禁/慎/宜 verdict. Encodes the project's evidence-first workflow, rule-governance and audit rules, data provenance conventions, and the acceptance gate. Load before editing rule, tag, dish, or AI-behavior files.
whenToUse: Any task that adds/changes a rule, tag keyword, dish, alias, gold label, or LLM prompt in <repo>; or when asked whether the system is still "达标"/"可追溯"/"已审核".
---

# 知源智膳 · 项目作业守则

单人项目（项目负责人，北邮雏雁计划）。核心承诺：**判定由本地规则确定性完成，大模型只解释、不判定**。所有"证明"必须能一条命令复现，不接受口头结论。

## 0. 五条红线

1. **判定权不可下放**：LLM 不得参与"能不能吃"的判断，只能复述已有证据。
2. **改规则必须留痕**：`rules.csv` 改动 → 审核记录 → 版本号 → 影响分析，四步缺一不可。
3. **结论必须可追溯**：每条推荐/拦截都要带 `rule_id`、`source_ref`、`rule_version`。
4. **缺数据就写缺**：价格未知写 `NULL` 不写 `0`；档口未知写 `note=档口待核实`，不编造。
5. **指标只许变好**：`python tools.py gate` 不通过就不提交；不要用 `--no-verify` 绕过。

## 1. 改动任何东西的固定流程

```powershell
python tools.py gate          # ① 先确认基线是绿的
# —— 改 rules.csv / tags.py / food.csv / aliases.csv ——
python tools.py snapshot      # ② 改之前存快照（仅改规则时需要）
python init_db.py             # ③ 导入 → 建表 → 规则 → 标签（幂等）
python eval_metrics.py        # ④ 看六项指标
python tools.py resync        # ⑤ 改规则时：看哪些菜翻盘、哪些金标要复核
python tools.py gate          # ⑥ 全绿才提交
```

顺序不能颠：`init_db.py` 内部是"导入菜品 → 建表 → 载规则 → 派生标签"，先派生标签再导入会让新菜没有标签。

## 2. 规则层（`rules.csv` + `rule_engine.py`）

- **三档语义**：`禁` = 不进候选集；`慎` = 可进但标注提醒；`宜` = 优先推荐。
- **冲突取最严**：同一道菜命中多条时，`禁 > 慎 > 宜`。
- **无命中按 `宜`**，并附 `NEUTRAL` 证据（`无禁忌证据即放行`）。不要退回"慎"——那会让所有中性菜都变成黄灯。
- **规则外置**：规则只写在 `rules.csv`，`tags` 必须是 `tags.py` 里已定义的标签，`action` 只能是 `禁/慎/宜`，`source_ref` 必填。
- **审核状态落库**：`status` 只有 `草案` / `已审核`；`已审核` 必须同时有 `reviewer` 与 `reviewed_at`。对外只能说"已审核"当且仅当 `SELECT COUNT(*) FROM Rules WHERE status<>'已审核'` 为 0。
- **审计表独立**：`Rule_Review` 不设外键、只增不改。它是审核日志，必须比当前规则表活得久。
- **改规则的完整动作**：

```powershell
python tools.py snapshot
python tools.py review                # 生成 rules_review_template.csv
# 填 decision（通过/修改）、new_action、new_tags、comment
python tools.py review --apply        # 写回 rules.csv + Rule_Review
# 手工确认 version.py 的 RULE_VERSION（内容变 → 升次版本；仅状态变 → 也升，便于定位）
python init_db.py && python tools.py resync && python tools.py gate
```

## 3. 标签层（`tags.py`）——判定的真正根因

- 判定错，先查标签，不要先改规则。`Dish_Tag` 里存的是"命中了什么"，规则只是消费方。
- 派生是**纯函数** `derive_tags(name, property, explanation)`，改关键词必须同步升 `TAG_VERSION`。
- 否定语境必处理：`少油`≠重油、`解腻`≠油腻、`不上火`≠温燥、`升糖`≠高糖、`微辛`≠辛辣。
- 无任何命中时兜底 `neutral`，保证"每条菜至少一个标签"（门禁会查）。
- 加新标签必须在 `TAG_DEFS` 里给出 `label` 与 `rationale`，否则等于给规则层塞了个黑盒。

## 4. AI 层（`shafe_mvp.py`）

- LLM 输入只允许**结构化字段**：数据库解析出的菜名、下拉框体质、引擎产出的 `rule_id`/依据。**绝不把用户自由文本拼进 prompt**（这是防注入的结构性保证）。
- 输出必须过 `validate_ai_text(text, verdict, allowed_dishes)`，三条硬规则：违禁医疗词（穴位/针刺/艾灸/剂量/毫克/处方/疗程/根治）、与 `禁` 冲突的表述、未放行菜名。任一不过 → 丢弃 AI 文本，`ai_error` 写明降级原因，**本地结果照常返回**。
- 超时：15 s，失败即降级，不抛异常。
- 免责声明：每屏、每份导出都要有；导出走 `plan_to_text()`。

## 5. 数据层（`food.csv` / `Dish_Source`）

- `food.csv` 是唯一真源，`python init_db.py` 幂等导入；改库不算改数据。
- 必须字段：`name, property, explanation, location, window_name, price`；溯源五列：`source_type, source_ref, collected_by, collected_at, campus`。
- 缺失值约定：价格未知 → 留空入库为 `NULL`；档口未知 → `location/window_name` 留空且 `note=档口待核实`。
- 档口分类标签（`一大荤一素`、`套餐`）不是菜品，导入时拒收；但菜名里本来含"套餐"的真实菜（如"麻辣烫13元套餐"）必须保留——用精确匹配/正则，别用子串。
- 一条菜多个档口就写多行（`location+window_name` 不同），`Canteen` 有唯一索引去重。
- `kind` 区分 `dish` 与 `ingredient`：食材只可查询，不进推荐方案。

> 具体的照片识别、权威文献补库、审核表回传流程，见 `zhishan-data-intake` 技能。

## 6. 证据层

- 六项指标 + 金标在 `eval_metrics.py` / `gold_labels.json`。金标是**人工标注**，工具只给建议值（`suggestion` 列），照抄会让评测失去意义。
- `eval_metrics.py --gate`：任何一项 FAIL 返回非零。
- `tools.py gate`：单测 + 六项指标 + 数据完整性三合一，已挂 pre-commit。
- `tools.py quality`：价格缺失、无档口、无标签、溯源缺口、标签覆盖分布——改数据前后各看一次。

## 7. 常见故障 → 先查这里

| 现象 | 大概率原因 | 处理 |
|---|---|---|
| `init_db.py` 报 `FOREIGN KEY constraint failed` | 审计表带了外键 | 去掉 `Rule_Review` 外键，勿级联删除日志 |
| 新菜没有标签 | 先派生标签后导入 | 用 `init_db.py`，别单独跑 `schema.py` |
| 两种体质推荐结果一样 | `constitution` 没参与判定 | 查 `rule_engine.plan()` 是否走规则，快照 diff 应为非 0 |
| 推荐全是"慎" | 默认判定退回慎 | 无命中应判 `宜` + `NEUTRAL` 证据 |
| 指标突然掉到 95% 以下 | 改了标签关键词或规则动作 | `tools.py resync` + 复核受影响金标 |
| 提交被 hook 挡下 | 指标真的回退了 | 不要 `--no-verify`，先修数据/规则 |

## 8. 不要做的事

- 不要为"架构好看"引入 FastAPI/前后端分离：六项指标没有一条需要它，且不可回退的改动是单人项目的最大风险。
- 不要让 LLM 生成穴位、剂量、病程、疗效类内容，即使加了"仅供参考"也不行——那是绕过规则层的后门。
- 不要把密码/API Key 写进源码；用 `ZY_ACCESS_PASSWORD` / `.env`（已在 `.gitignore`）。
- 不要用 `0` 表示"价格未知"，不要用 `慎` 表示"没判断"。
- 不要在未跑 `gate` 的情况下说"改好了"。
