# 知源智膳

面向沙河校区食堂的中医食养辅助系统：用户填写体质问卷与当日状态，系统在本地规则库中给出"禁 / 慎 / 宜"结论，再由大模型把结论解释成人话。目标是在"今天食堂吃什么"这一高频场景里，把中医食养原则变成可执行、可审计的每日方案。技术栈为 Python 3.14 + Streamlit 1.66 + SQLite，规则全部为草案，**未经执业中医师审核，不构成医疗建议**。

## 核心设计：双层防御

```text
问卷（体质 · 情志 · 忌口）
        │
        ▼
[第 1 层] 本地规则引擎 —— 纯 Python + SQLite，确定性判定
   菜品文本 → 属性标签 → 规则 → 禁 / 慎 / 宜
        │  命中“禁”直接拦截，不可协商
        ▼  只把放行结果交给下一层
[第 2 层] 大模型解释 —— OpenAI 兼容接口（默认校内网关
   https://myai.bupt.edu.cn/llm-gw/v1，模型 qwen3.8-27b）
   只解释“为什么”，不能推翻规则、不能新增推荐
        │
        ▼
   方案卡片 / TXT 导出（每条带规则编号与出处）
```

判定只发生在第 1 层；第 2 层失败或超时（15 s）时自动降级为本地结果。

## 目录结构

| 文件 | 作用 |
| --- | --- |
| `food.csv` | 菜品 + 基础食材 + 档口，唯一真源，可幂等导入（`kind` 区分 dish/ingredient） |
| `rules.csv` | 19 条体质规则，唯一真源，**已由导师审核通过**（v1.1.0） |
| `aliases.csv` | 口语别名 → 标准菜名 |
| `food.db` | SQLite 库（WAL 模式），可由脚本重建 |
| `Dish_Source` 表 | 每条菜品的来源类型、采集人、日期、校区 |
| `init_db.py` | **一键初始化**：导入 → 建表 → 规则 → 标签 |
| `schema.py` | 建表/迁移、同步规则与别名、派生标签 |
| `import_data.py` | 导入 food.csv 到 Dish / Canteen |
| `tags.py` | 菜品文本 → 属性标签（15 类，正则 + 否定语境） |
| `rule_engine.py` | 确定性判定：禁/慎/宜 + 规则证据 + 菜名检索 |
| `shafe_mvp.py` | 方案生成、AI 解释与失败降级 |
| `app.py` | Streamlit 前端（方案 / 单菜查询 / 规则与合规） |
| `eval_metrics.py` | 跑考核指标，写 eval_report.md |
| `tests/` | 43 条单元测试（标签、规则、检索、AI 边界、溯源） |
| `docs/导师规则审核包.md` | 给导师的规则审核材料（签字版即 v1.0.0） |
| `version.py` | 规则 / 标签 / Schema 版本与免责声明 |

数据库表：Dish、Canteen、Constraint_Rule、Emotion_Rule、Dish_Tag、Dish_Alias、Rules、Rule_Review。

## 快速开始

```powershell
pip install -r requirements.txt
python init_db.py          # 一条命令完成导入 + 建表 + 规则 + 标签
streamlit run app.py       # 浏览器打开 http://localhost:8501
```

验证与评测：

```powershell
python -m unittest discover -s tests -v   # 26 条单测
python eval_metrics.py                    # 生成 eval_report.md / .json
python eval_metrics.py --check            # 只校验金标菜品是否都在库
python stress_test.py --minutes 30 --workers 4   # 稳定性压测（立项指标：30 分钟无崩溃）
```

## 启动与常用工具

```powershell
.\run.ps1                 # 默认密码 change-me，等价于设置 ZY_ACCESS_PASSWORD 后启动
.\run.ps1 -Password 'xxx' # 自定义密码
```

密码三种给法（任选其一，优先级从高到低）：命令行环境变量 > `.env` 文件 > `run.ps1` 参数。
`.env` 从 `.env.example` 复制，已在 `.gitignore` 中，不会进仓库。

```powershell
python tools.py template                 # 生成扩菜模板
python tools.py import 食堂菜单.csv       # 校验新菜品（默认 dry-run，加 --write 才合并）
python tools.py labels                   # 生成待标注清单 labels_to_fill.csv
python tools.py labels --validate        # 把填好的清单校验成 gold_labels.json
python tools.py quality                  # 数据质量报告（价格缺失/无档口/标签覆盖）
python tools.py review                   # 生成导师审核表
python tools.py review --apply           # 回填审核结果，写 rules.csv + Rule_Review
python tools.py snapshot                 # 保存当前全量判定快照
python tools.py resync                   # 对比快照：规则改动影响了哪些菜与金标
python tools.py gate                     # 验收门禁：单测 + 六项指标 + 数据完整性
python tools.py hook --install           # 把门禁挂到 git pre-commit
```

## 数据维护

- **新增菜品**：在 `food.csv` 追加一行（name、property、explanation、location、window_name、price，calories 可选），执行 `python init_db.py`。
- **新增规则**：在 `rules.csv` 追加一行，code 唯一，action 只能为 禁/慎/宜，tags 必须是 `tags.py` 里已有的标签，`source_ref` 必填（可追溯性），然后执行 `python init_db.py`。
- **新增别名**：在 `aliases.csv` 追加 dish_name、alias、alias_type、note，执行 `python init_db.py`。
- **接入新校区**：用 `data/templates/校区导入模板.csv`，`python tools.py import 文件.csv` 校验，
  `--write` 合并，`campus` 为必填字段。详见 `data/templates/校区接入说明.md`。
- 每次改完规则或数据，都要重跑 `eval_metrics.py`；指标只许变好，不许悄悄变差。

## 考核指标与复现

`python eval_metrics.py` 对照 99 条人工金标计算并写入 `eval_report.md`。六项指标（前五项对应立项书，第六项为根因检测）：

| 指标 | 当前基线 | 目标 |
| --- | --- | --- |
| 体质硬过滤准确率 | 100%（99/99） | ≥95% |
| 体质敏感度（判定不同菜数） | 仅气虚禁 21 / 仅湿热禁 17 | >0 且方向正确 |
| 测试集禁忌违规率 | 0% | 0% |
| 方案条目可追溯率 | 100%（带规则ID+出处+版本） | 100% |
| 单次方案生成延迟（本地） | p50 2 ms | <100 ms |
| 免责声明与依据完整性 | 通过 | 每份导出含声明 |

## 安全与合规边界

- 19 条规则已由指导教师指导教师审核通过（2026-11-15，v1.1.0），审核记录见 `Rule_Review` 表与 `rules_review_template.csv`；仍**不构成医疗建议**。
- 仅做日常食养辅助与教学展示，不替代诊断与治疗；症状持续请就医。
- 大模型不参与"能不能吃"的判定，只解释已通过规则筛选的菜品，不得推翻结论。
- BYOK：API Key 只在本次 Streamlit 会话内存中使用，不写入源码、数据库或日志。
- 前端密码从环境变量 `ZY_ACCESS_PASSWORD` 读取，**源码里不留明文密码**。

## 已知限制

- 体质只覆盖气虚、湿热两种，其余体质无规则。
- 菜品 203 道、基础食材 117 种（合计 320 条）；食材只用于查询，不进推荐方案。
- 基础食材性味为教材级通行说法，热量为《中国食物成分表》参考值，均待逐条核对。
- 麻辣香锅、山药鸡汤、清炒时蔬已纳入菜品库，但公开资料无法核实具体档口与价格，CSV 中标记为“档口待核实”。
- 兰州拉面等常见档口菜尚未收录，别名表只覆盖部分口语说法（会明确返回"未收录"）。
- 标签靠关键词正则派生，否定语境覆盖有限，可能误判；这是当前最大的已知误差来源。
- 金标由 `explanation` 反推，属库内一致性检验，不等于中医上正确。

## 版本与许可

MIT License。规则、标签、Schema 版本分别见 `version.py` 的 `RULE_VERSION`（1.0.0）、`TAG_VERSION`（1.1.0）、`SCHEMA_VERSION`（3）；改动规则、标签或表结构须同步升版本，评测报告与方案文本据此定位。


## 开源与贡献

- 许可：[MIT](LICENSE)（数据部分见 LICENSE 末尾的数据声明）
- 参与方式见 [CONTRIBUTING.md](CONTRIBUTING.md)：**最容易的贡献是给本校食堂补数据**
- 设计稿：`design/zhishan-ui-v2.html`（桌面/移动预览图见 `design/preview-v3-*.png`）
- 路线：先把多校区数据与贡献流程跑通，再做 B 端嵌入；不做诊断、不做健康评分

## 已知边界

- 只覆盖两种体质（气虚 / 湿热），其余返回「暂不支持」；
- 规则虽经指导教师审核，仍不构成医疗建议；
- 性味为教材级证据，热量为成分表参考值，均未逐条标注页码。
