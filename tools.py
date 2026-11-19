# -*- coding: utf-8 -*-
"""知源智膳 · P2 工具集（扩数据 / 扩金标 / 查质量）。

用法：
    python tools.py template                      # 生成扩菜模板 food_import_template.csv
    python tools.py import 食堂菜单.xlsx           # 校验并合并新菜品（先 dry-run，加 --write 才落盘）
    python tools.py labels                        # 生成待标注清单 labels_to_fill.csv
    python tools.py labels --validate             # 校验已回填的 labels_to_fill.csv
    python tools.py quality                       # 数据质量报告
    python tools.py review                        # 生成导师审核表
    python tools.py review --apply                # 回填审核结果，写 rules.csv + Rule_Review
    python tools.py snapshot                      # 保存当前全量判定快照
    python tools.py resync                        # 对比快照，看规则改动影响了哪些菜与金标

设计原则：
    - 任何"写"操作默认 dry-run，必须显式 --write；
    - 新菜品先校验再合并，宁可拒收也不污染主表；
    - 金标由人填，脚本只做建议与校验，不替人下医学判断。
"""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "food.db"
FOOD_CSV = BASE_DIR / "food.csv"
TEMPLATE_CSV = BASE_DIR / "food_import_template.csv"
LABELS_CSV = BASE_DIR / "labels_to_fill.csv"
GOLD_JSON = BASE_DIR / "gold_labels.json"

REQUIRED_COLS = ("name", "property", "explanation", "location", "window_name", "price")
# WPS / Excel 里常见的中文表头 → 标准列名
HEADER_ALIASES = {
    "菜品名称": "name", "菜名": "name", "名称": "name",
    "性味": "property", "属性": "property", "食性": "property",
    "说明": "explanation", "解释": "explanation", "功效说明": "explanation",
    "档口": "location", "位置": "location", "楼层": "location", "食堂": "location",
    "窗口": "window_name", "窗口名": "window_name", "售卖窗口": "window_name",
    "价格": "price", "售价": "price", "单价": "price",
    "热量": "calories", "热量(千卡)": "calories", "千卡": "calories",
    "备注": "note",
}
VALID_ACTIONS = ("禁", "慎", "宜")


# ------------------------------------------------------------------ 通用
def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        sys.exit("缺少 food.db，请先运行 python init_db.py")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _read_table(path: Path) -> tuple[list[str], list[dict]]:
    """读 CSV 或 Excel（WPS 导出的 xlsx 也能读），并归一化表头。"""
    if not path.exists():
        sys.exit(f"文件不存在：{path}")
    if path.suffix.lower() in (".xlsx", ".xls"):
        try:
            import pandas as pd
        except ImportError:
            sys.exit("读 Excel 需要 pandas：pip install pandas openpyxl；或先另存为 CSV")
        df = pd.read_excel(path, dtype=str).fillna("")
        raw_headers = [str(c).strip() for c in df.columns]
        rows = df.to_dict(orient="records")
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            raw_headers = [h.strip() for h in (reader.fieldnames or [])]
            rows = list(reader)

    mapping = {h: HEADER_ALIASES.get(h, h) for h in raw_headers}
    normalized = [
        {mapping.get(str(k).strip(), str(k).strip()): (v or "").strip() if isinstance(v, str) else v
         for k, v in row.items()}
        for row in rows
    ]
    headers = [mapping.get(h, h) for h in raw_headers]
    return headers, normalized


def _is_category(name: str) -> bool:
    from import_data import is_category_name

    return is_category_name(name)


# ------------------------------------------------------------------ 模板
def cmd_template() -> None:
    header = ["name", "property", "explanation", "location", "window_name", "price", "calories"]
    sample = [
        "番茄鸡蛋面", "平性偏温", "番茄生津、鸡蛋养胃，面条易消化，适合日常主食。",
        "沙河校区A楼风味餐厅", "面食窗口", "12", "",
    ]
    with TEMPLATE_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(sample)
    print(f"已生成 {TEMPLATE_CSV.name}")
    print("填写要点：")
    print("  1. property 写性味（如 平性/温补偏油/辛辣重油），这是规则引擎判定的依据")
    print("  2. explanation 必须写清'为什么适合/不适合某体质'，否则无法追溯")
    print("  3. price 未知就留空，不要填 0；档口查不到就留空并在 note 写“档口待核实”")
    print("  4. 一行一道菜；同一道菜在多个档口售卖就写多行（location+window_name 不同）")


# ------------------------------------------------------------------ 导入
def cmd_import(src: str, write: bool = False) -> None:
    headers, rows = _read_table(Path(src))
    missing = [c for c in REQUIRED_COLS if c not in headers]
    if "campus" not in headers:
        missing.append("campus")
    if missing:
        sys.exit(f"缺列：{missing}；请对照 {TEMPLATE_CSV.name}")

    existing: dict[str, dict] = {}
    with FOOD_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            existing[(row.get("name") or "").strip()] = row

    accepted, rejected = [], []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            rejected.append((i, "缺少 name"))
            continue
        if _is_category(name):
            rejected.append((i, f"{name}: 档口分类/套餐标签，不是具体菜品"))
            continue
        if not (row.get("property") or "").strip():
            rejected.append((i, f"{name}: 缺少 property（性味）"))
            continue
        if not (row.get("explanation") or "").strip():
            rejected.append((i, f"{name}: 缺少 explanation（依据）"))
            continue
        if not (row.get("campus") or "").strip():
            rejected.append((i, f"{name}: 缺少 campus（校区）"))
            continue
        price = (row.get("price") or "").strip()
        if price:
            try:
                if float(price) < 0:
                    raise ValueError
            except ValueError:
                rejected.append((i, f"{name}: price 非法 {price!r}"))
                continue
        accepted.append(row)

    new_names = [r["name"] for r in accepted if r["name"] not in existing]
    print(f"读入 {len(rows)} 行：可接收 {len(accepted)}，拒收 {len(rejected)}，其中新菜品 {len(new_names)} 道")
    for i, why in rejected[:10]:
        print(f"  ✗ 第 {i} 行：{why}")
    if len(rejected) > 10:
        print(f"  … 还有 {len(rejected) - 10} 条拒收")

    if not write:
        print("\n[dry-run] 未写入。确认无误后加 --write 合并进 food.csv")
        return

    with FOOD_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "property", "explanation", "location",
                                          "window_name", "price", "calories", "note"])
        for row in accepted:
            w.writerow({k: (row.get(k) or "") for k in w.fieldnames})
    print(f"已追加 {len(accepted)} 行到 food.csv，请执行 python init_db.py 生效")


# ------------------------------------------------------------------ 金标
def cmd_labels(validate: bool = False) -> None:
    from rule_engine import load_rules, evaluate

    con = _connect()
    dishes = [dict(r) for r in con.execute("SELECT id, name, property, explanation FROM Dish ORDER BY id")]
    con.close()

    if not validate:
        with LABELS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["name", "constitution", "expected", "note", "suggestion"])
            for c in ("气虚", "湿热"):
                rules = load_rules(c)
                for d in dishes:
                    # 用库内已有标签做建议值（只作参考，人必须自己判断）
                    with sqlite3.connect(DB_PATH) as cx:
                        tags = {r[0] for r in cx.execute("SELECT tag FROM Dish_Tag WHERE dish_id=?", (d["id"],))}
                    v = evaluate(d, c, rules=rules, tags=tags)
                    w.writerow([d["name"], c, "", "", v["verdict"]])
        print(f"已生成 {LABELS_CSV.name}（{len(dishes) * 2} 行）")
        print("填写方法：把 expected 列填成 禁 或 非禁；note 写一句依据；不用删行，留空的行会被跳过。")
        print("提示：suggestion 列是系统当前判定，只作参考——如果你只是照抄，金标就失去意义了。")
        return

    if not LABELS_CSV.exists():
        sys.exit(f"找不到 {LABELS_CSV.name}，先运行 python tools.py labels")
    filled, blank = [], 0
    with LABELS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            exp = (row.get("expected") or "").strip()
            if not exp:
                blank += 1
                continue
            if exp not in ("禁", "非禁"):
                sys.exit(f"第 {i} 行 expected 必须是 禁/非禁，实际 {exp!r}")
            filled.append({
                "name": row["name"].strip(),
                "constitution": row["constitution"].strip(),
                "expected": exp,
                "note": (row.get("note") or "").strip(),
            })

    if not filled:
        sys.exit("没有填写任何 expected，无法生成金标")
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "annotator": "",  # 请填写标注人姓名
        "source": "人工标注：对照菜品 explanation 与中医体质学判断",
        "count": len(filled),
        "labels": filled,
    }
    GOLD_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {GOLD_JSON.name}：{len(filled)} 条有效金标（跳过 {blank} 条空白）")
    print("下一步：python eval_metrics.py 会用这份金标重算准确率")


# ------------------------------------------------------------------ 质量
def cmd_quality() -> None:
    con = _connect()
    q = lambda sql: con.execute(sql).fetchone()[0]
    total = q("SELECT COUNT(*) FROM Dish")
    print(f"菜品总数：{total}")
    print(f"无档口记录：{q('SELECT COUNT(*) FROM Dish d WHERE NOT EXISTS(SELECT 1 FROM Canteen c WHERE c.dish_id=d.id)')}")
    print(f"价格为 NULL：{q('SELECT COUNT(*) FROM Canteen WHERE price IS NULL')}")
    print(f"价格为 0：{q('SELECT COUNT(*) FROM Canteen WHERE price=0')}")
    print("无属性：" + str(q("SELECT COUNT(*) FROM Dish WHERE TRIM(COALESCE(property,''))=''")))
    print("无解释：" + str(q("SELECT COUNT(*) FROM Dish WHERE TRIM(COALESCE(explanation,''))=''")))
    print(f"无标签：{q('SELECT COUNT(*) FROM Dish d WHERE NOT EXISTS(SELECT 1 FROM Dish_Tag t WHERE t.dish_id=d.id)')}")

    # 溯源：多校区的前提，"100% 可追溯"在扩校后靠这几列兜底
    print("\n数据溯源：")
    try:
        print(f"  已登记来源：{q('SELECT COUNT(*) FROM Dish_Source')} / {total}")
        print(f"  来源类型分布：{dict(con.execute('SELECT source_type, COUNT(*) FROM Dish_Source GROUP BY 1').fetchall())}")
        print(f"  校区分布：{dict(con.execute('SELECT campus, COUNT(*) FROM Dish_Source GROUP BY 1').fetchall())}")
        print("  待补充：" + str(q(
            "SELECT COUNT(*) FROM Dish_Source WHERE source_type='待补充' OR collected_by='待补充'")))
        print(f"  journal_mode：{q('PRAGMA journal_mode')}")
    except sqlite3.Error as exc:
        print(f"  ⚠ 溯源表不可用：{exc}")

    print("\n属性词分布（Top 10，值越分散说明数据越手工、越难规则化）：")
    for r in con.execute("SELECT property, COUNT(*) c FROM Dish GROUP BY 1 ORDER BY c DESC LIMIT 10"):
        print(f"  {r[0]:<12} {r[1]}")

    print("\n标签覆盖（每种标签多少道菜）：")
    for r in con.execute("SELECT tag, COUNT(*) c FROM Dish_Tag GROUP BY 1 ORDER BY c DESC"):
        print(f"  {r[0]:<12} {r[1]}")

    no_tag = [r[0] for r in con.execute(
        "SELECT d.name FROM Dish d WHERE NOT EXISTS(SELECT 1 FROM Dish_Tag t WHERE t.dish_id=d.id)")]
    if no_tag:
        print(f"\n⚠ 没有标签的菜（会走 neutral 兜底）：{no_tag}")
    con.close()


# ------------------------------------------------------------------ 数据审核
def cmd_data_review(src: str, write: bool = False, reviewer: str = "") -> int:
    """回填人工审核表：应用「改性味/改依据」，并把结论写入 Dish_Review。

    审核表由 `python tools.py labels` 之外的数据流程生成（见
    docs/待审核_*.csv），列名固定：菜名 / 认可(Y/N) / 改性味 / 改依据 / 备注。
    """
    import pandas as pd

    path = Path(src)
    if not path.exists():
        sys.exit(f"文件不存在：{path}")
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str).fillna("")
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            df = pd.DataFrame(list(csv.DictReader(f)))
    if "菜名" not in df.columns:
        sys.exit("审核表缺少「菜名」列")

    col = lambda row, key: str(row.get(key, "") or "").strip()
    reviewer = reviewer or os.getenv("ZY_REVIEWER", "维护者")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    src_csv = BASE_DIR / "food.csv"
    rows = list(csv.DictReader(src_csv.open("r", encoding="utf-8-sig", newline="")))
    by_name: dict[str, list[dict]] = {}
    for r in rows:
        by_name.setdefault(r["name"].strip(), []).append(r)

    passed, rejected, modified, unknown = [], [], [], []
    for _, row in df.iterrows():
        name = col(row, "菜名")
        if not name:
            continue
        if name not in by_name:
            unknown.append(name)
            continue
        decision_raw = col(row, "认可(Y/N)") or col(row, "认可")
        if decision_raw in ("Y", "y", "是", "通过"):
            decision = "通过"
        elif decision_raw in ("N", "n", "否", "驳回"):
            decision = "驳回"
        else:
            sys.exit(f"{name}: 认可列必须填 Y 或 N，实际 {decision_raw!r}")

        new_prop, new_expl = col(row, "改性味"), col(row, "改依据")
        comment = col(row, "备注")
        if decision == "通过" and (new_prop or new_expl):
            for r in by_name[name]:
                if new_prop:
                    r["property"] = new_prop
                if new_expl:
                    r["explanation"] = new_expl
            modified.append(name)
            comment = (comment + f"｜改为：{new_prop or '性味不变'}／{new_expl or '依据不变'}").strip("｜")
        (passed if decision == "通过" else rejected).append(name)

    print(f"读到 {len(df)} 行：通过 {len(passed)}、驳回 {len(rejected)}、修改 {len(modified)}")
    if modified:
        print("  修改:", "、".join(modified))
    if rejected:
        print("  驳回（数据保持原样，需人工处理）:", "、".join(rejected))
    if unknown:
        print("  库内不存在（已跳过）:", "、".join(unknown))

    if not write:
        print("\n[dry-run] 未写入。加 --write 才会更新 food.csv 并记录审核。")
        return 0

    with src_csv.open("w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    import schema

    con = _connect()
    schema._ensure_tables(con)  # 首次使用时自动建 Dish_Review
    for name in passed:
        con.execute(
            "INSERT INTO Dish_Review (dish_name, decision, reviewer, reviewed_at, comment) VALUES (?,?,?,?,?)",
            (name, "通过", reviewer, now, ""),
        )
    for name in rejected:
        con.execute(
            "INSERT INTO Dish_Review (dish_name, decision, reviewer, reviewed_at, comment) VALUES (?,?,?,?,?)",
            (name, "驳回", reviewer, now, ""),
        )
    con.commit()
    con.close()

    print(f"已写入 {len(passed) + len(rejected)} 条审核记录，审核人：{reviewer}")
    print("下一步：python init_db.py 让修改生效，然后 python tools.py gate")
    return 0



# ------------------------------------------------------------------ 标签复核
TAG_REVIEW_DIR = BASE_DIR / "docs"


def cmd_tag_review(n: int = 30, apply_file: str = "", reviewer: str = "") -> int:
    """标签抽样复核：生成抽样表，或回收修正并记录到 Tag_Review。

    标签是判定的真正根因：标签错 → 判定错，但它在 UI 上是隐式的。
    本命令把"隐式"变成"可抽查"。
    """
    import random

    import rule_engine as engine

    reviewer = reviewer or os.getenv("ZY_REVIEWER", "维护者")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if apply_file:
        path = Path(apply_file)
        if not path.exists():
            sys.exit(f"文件不存在：{path}")
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        con = _connect()
        from schema import _ensure_tables

        _ensure_tables(con)
        recorded = 0
        remove_counter: dict[str, int] = {}
        add_counter: dict[str, int] = {}
        for r in rows:
            name = (r.get("菜名") or "").strip()
            verdict = (r.get("标签是否合理(Y/N)") or "").strip()
            if not name or not verdict:
                continue
            if verdict not in ("Y", "N", "合理", "不合理"):
                sys.exit(f"{name}: 标签是否合理列必须填 Y/N")
            rm = [x for x in (r.get("应删标签") or "").replace("，", ",").split(",") if x.strip()]
            ad = [x for x in (r.get("应加标签") or "").replace("，", ",").split(",") if x.strip()]
            for x in rm:
                remove_counter[x.strip()] = remove_counter.get(x.strip(), 0) + 1
            for x in ad:
                add_counter[x.strip()] = add_counter.get(x.strip(), 0) + 1
            con.execute(
                "INSERT INTO Tag_Review (dish_name, verdict, remove_tags, add_tags, reviewer, reviewed_at, comment) "
                "VALUES (?,?,?,?,?,?,?)",
                (name, "合理" if verdict in ("Y", "合理") else "不合理",
                 ",".join(x.strip() for x in rm), ",".join(x.strip() for x in ad),
                 reviewer, now, (r.get("备注") or "").strip()),
            )
            recorded += 1
        con.commit()
        con.close()
        print(f"已记录 {recorded} 条标签复核，审核人：{reviewer}")
        if remove_counter:
            print("应删标签 Top：", sorted(remove_counter.items(), key=lambda x: -x[1])[:5])
        if add_counter:
            print("应加标签 Top：", sorted(add_counter.items(), key=lambda x: -x[1])[:5])
        if remove_counter or add_counter:
            print("下一步：按统计调整 tags.py 关键词，升 TAG_VERSION，重跑 eval_metrics.py")
        return 0

    # 生成抽样
    import sqlite3 as _sqlite

    con = _connect()
    con.row_factory = _sqlite.Row
    dishes = [dict(r) for r in con.execute(
        "SELECT d.id, d.name, d.kind, d.property, d.explanation, "
        "(SELECT GROUP_CONCAT(tag, ' ') FROM Dish_Tag t WHERE t.dish_id = d.id) tags "
        "FROM Dish d ORDER BY d.id"
    )]
    rules = {c: engine.load_rules(c) for c in engine.SUPPORTED_CONSTITUTIONS}
    tag_map: dict[int, set[str]] = {}
    for r in con.execute("SELECT dish_id, tag FROM Dish_Tag"):
        tag_map.setdefault(r["dish_id"], set()).add(r["tag"])
    con.close()

    rng = random.Random(20261118)
    sample = rng.sample(dishes, min(n, len(dishes)))
    out = TAG_REVIEW_DIR / f"标签复核_{datetime.now():%Y%m%d}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["菜名", "类型", "性味", "依据", "当前标签", "气虚", "湿热",
                    "标签是否合理(Y/N)", "应删标签", "应加标签", "备注"])
        for d in sample:
            tags = tag_map.get(d["id"], set())
            verdicts = []
            for c in engine.SUPPORTED_CONSTITUTIONS:
                v = engine.evaluate({"id": d["id"], "name": d["name"]}, c,
                                    rules=rules[c], tags=tags)
                verdicts.append(v["verdict"])
            w.writerow([d["name"], d["kind"] or "dish", d["property"], d["explanation"],
                        " ".join(sorted(tags)), verdicts[0], verdicts[1], "", "", "", ""])
    print(f"已生成 {out}（{len(sample)} 条，seed=20261118 可复现）")
    print("复核要点：标签是否命中了文本里没有的属性；文本里明显的属性是否漏标。")
    print("回填后：python tools.py tag-review --apply 文件.csv")
    return 0



# ------------------------------------------------------------------ 候选池
def cmd_candidate(action: str = "list", cid: int = 0, reviewer: str = "",
                  reason: str = "") -> int:
    """候选池：用户反馈先进这里，审核通过才写入 food.csv。

    这是立项书承诺的"新增来源 → 抽取 → 审核 → 入库"链路的最小实现。
    """
    from schema import _ensure_tables

    con = _connect()
    _ensure_tables(con)
    reviewer = reviewer or os.getenv("ZY_REVIEWER", "维护者")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if action == "list":
        rows = [dict(r) for r in con.execute(
            "SELECT id, kind, name, status, submitted_by, submitted_at, note "
            "FROM Candidate ORDER BY status='待审' DESC, id DESC LIMIT 50"
        )]
        if not rows:
            print("候选池为空。可在前端「反馈纠错」提交，或用 tools.py candidate add。")
        for r in rows:
            print(f"  #{r['id']} [{r['status']}] {r['name']}（{r['kind']}）"
                  f" by {r['submitted_by'] or '-'} {r['submitted_at']} {r['note'] or ''}")
        con.close()
        return 0

    if action in ("approve", "reject"):
        row = con.execute("SELECT * FROM Candidate WHERE id=?", (cid,)).fetchone()
        if not row:
            sys.exit(f"候选 #{cid} 不存在")
        row = dict(row)
        if row["status"] != "待审":
            sys.exit(f"候选 #{cid} 状态为 {row['status']}，不能重复处理")

        if action == "reject":
            con.execute(
                "UPDATE Candidate SET status='已驳回', reviewer=?, reviewed_at=?, review_comment=? WHERE id=?",
                (reviewer, now, reason or "未说明原因", cid),
            )
            con.commit()
            con.close()
            print(f"已驳回 #{cid} {row['name']}：{reason or '未说明原因'}")
            return 0

        # 采纳：写入 food.csv（唯一真源），再标记状态
        src = BASE_DIR / "food.csv"
        rows = list(csv.DictReader(src.open("r", encoding="utf-8-sig", newline="")))
        fields = list(rows[0].keys())
        exists = any(r["name"] == row["name"] for r in rows)

        if row["kind"] == "new" and exists:
            sys.exit(f"{row['name']} 已存在，请改用 kind=fix 提交修正")
        if row["kind"] == "fix" and not exists:
            sys.exit(f"{row['name']} 不在库中，请改用 kind=new 提交新菜")

        base = next((r for r in rows if r["name"] == row["name"]), None)
        if row["kind"] == "fix" and base:
            if row.get("property"):
                base["property"] = row["property"]
            if row.get("explanation"):
                base["explanation"] = row["explanation"]
        else:
            rows.append({
                "name": row["name"], "property": row["property"] or "",
                "explanation": row["explanation"] or "",
                "location": row["location"] or "", "window_name": row["window_name"] or "",
                "price": "" if row["price"] is None else f"{row['price']:g}",
                "calories": "", "note": row["note"] or "",
                "source_type": "用户反馈", "source_ref": f"候选 #{cid}",
                "collected_by": row["submitted_by"] or "匿名",
                "collected_at": now[:7], "campus": row["campus"] or "沙河",
                "kind": "dish",
            })

        with src.open("w", encoding="utf-8", newline="\n") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

        con.execute(
            "UPDATE Candidate SET status='已采纳', reviewer=?, reviewed_at=?, review_comment=? WHERE id=?",
            (reviewer, now, reason or "审核通过", cid),
        )
        con.execute(
            "INSERT INTO Dish_Review (dish_name, decision, reviewer, reviewed_at, comment) VALUES (?,?,?,?,?)",
            (row["name"], "通过", reviewer, now, f"来自候选 #{cid}"),
        )
        con.commit()
        con.close()
        print(f"已采纳 #{cid} {row['name']}，写入 food.csv")
        print("下一步：python init_db.py 让修改生效，然后 python tools.py gate")
        return 0

    if action == "add":
        sys.exit("请在网页端「反馈纠错」提交，或用 candidate add 的参数式提交（暂未实现）")

    sys.exit(f"未知动作 {action}")

# ------------------------------------------------------------------ 门禁
def cmd_hook(install: bool = False) -> int:
    """把门禁挂到 git pre-commit，防止指标回退被提交。"""
    hook_path = BASE_DIR / ".git" / "hooks" / "pre-commit"
    if not install:
        print(f"用法：python tools.py hook --install\n将写入 {hook_path}")
        return 0
    if not (BASE_DIR / ".git").exists():
        sys.exit("不是 git 仓库，无法安装 hook")
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(
        "#!/bin/sh\n"
        "# 由 python tools.py hook --install 生成：提交前跑验收门禁\n"
        "cd \"$(git rev-parse --show-toplevel)\" || exit 1\n"
        "python tools.py gate || { echo '门禁未通过，提交已阻止'; exit 1; }\n",
        encoding="utf-8",
    )
    print(f"已安装 pre-commit hook：{hook_path}")
    print("跳过门禁（不推荐）：git commit --no-verify")
    return 0


def cmd_gate() -> int:
    """一条命令跑完所有"证明"：单测 + 六项指标 + 数据完整性。

    任何一项不达标即返回非零退出码，可直接挂到 git pre-commit 或 CI。
    """
    import subprocess

    checks: list[tuple[str, bool, str]] = []

    def run(args: list[str]) -> tuple[bool, str]:
        p = subprocess.run(
            [sys.executable, *args], cwd=BASE_DIR,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")

    ok, out = run(["-m", "unittest", "discover", "-s", "tests"])
    total = next((l for l in out.splitlines() if l.startswith("Ran ")), "")
    checks.append(("单元测试", ok, total or "未取到结果"))

    ok, out = run(["eval_metrics.py", "--gate"])
    checks.append(("六项考核指标", ok,
                   "全部 PASS" if ok else "、".join(
                       l.split()[0] for l in out.splitlines() if l.rstrip().endswith("FAIL")) or "FAIL"))

    # 数据完整性：直接查库，不依赖外部脚本
    try:
        con = _connect()
        q = lambda sql: con.execute(sql).fetchone()[0]
        problems = []
        if q("SELECT COUNT(*) FROM Dish d WHERE NOT EXISTS(SELECT 1 FROM Dish_Tag t WHERE t.dish_id=d.id)"):
            problems.append("有菜无标签")
        if q("SELECT COUNT(*) FROM Dish d WHERE NOT EXISTS(SELECT 1 FROM Dish_Source s WHERE s.dish_id=d.id)"):
            problems.append("有菜无来源")
        if q("SELECT COUNT(*) FROM Dish d WHERE NOT EXISTS(SELECT 1 FROM Canteen x WHERE x.dish_id=d.id)"):
            problems.append("有菜无档口")
        if q("SELECT COUNT(*) FROM Dish_Source WHERE source_type='待补充' OR collected_by='待补充'"):
            problems.append("来源待补充")
        if q("SELECT COUNT(*) FROM Canteen WHERE price=0"):
            problems.append("价格为0")
        if q("SELECT COUNT(*) FROM Rules WHERE status<>'已审核'"):
            problems.append("有规则未审核")
        con.close()
        checks.append(("数据完整性", not problems, "、".join(problems) or "全部满足"))
    except sqlite3.Error as exc:
        checks.append(("数据完整性", False, f"数据库不可用：{exc}"))

    # 文案与判定是否自相矛盾（如"判禁却写可以适量"）
    try:
        import consistency

        bad = consistency.find_mismatches()
        checks.append(("文案一致性", not bad,
                       "、".join(x["dish"] for x in bad[:5]) if bad else "全部一致"))
    except Exception as exc:  # 检查本身出错也算不通过
        checks.append(("文案一致性", False, f"检查失败：{exc}"))

    print("\n" + "=" * 62)
    print("知源智膳 · 验收门禁")
    print("=" * 62)
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<12} {detail}")
    print("=" * 62)

    failed = [name for name, ok, _ in checks if not ok]
    if failed:
        print(f"门禁未通过：{'、'.join(failed)}")
        return 1
    print("门禁通过：可以提交 / 发布")
    return 0


# ------------------------------------------------------------------ 入口


# ------------------------------------------------------------------ 规则治理
REVIEW_TEMPLATE = BASE_DIR / "rules_review_template.csv"
SNAPSHOT_DIR = BASE_DIR / "snapshots"


def cmd_review(apply: bool = False) -> None:
    """导师审核留痕：生成审核表 → 回填 → 写回 rules.csv 与 Rule_Review。"""
    import csv as _csv

    from version import RULE_VERSION

    if not apply:
        rows = []
        with open(BASE_DIR / "rules.csv", "r", encoding="utf-8-sig", newline="") as f:
            for r in _csv.DictReader(f):
                rows.append({
                    "code": r["code"], "constitution": r["constitution"],
                    "action": r["action"], "tag": r["tags"],
                    "decision": "", "new_action": "", "new_tags": "",
                    "comment": "",
                })
        with open(REVIEW_TEMPLATE, "w", encoding="utf-8-sig", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"已生成 {REVIEW_TEMPLATE.name}（{len(rows)} 条）")
        print("填写方法：decision 填 通过 / 修改 / 删除；修改时填 new_action、new_tags；comment 写意见。")
        print("回填后执行：python tools.py review --apply")
        return

    if not REVIEW_TEMPLATE.exists():
        sys.exit(f"找不到 {REVIEW_TEMPLATE.name}，先运行 python tools.py review")
    review_rows = list(_csv.DictReader(open(REVIEW_TEMPLATE, encoding="utf-8-sig", newline="")))
    decisions = {(r.get("code") or "").strip(): r for r in review_rows}

    src = BASE_DIR / "rules.csv"
    rules = list(_csv.DictReader(open(src, encoding="utf-8-sig", newline="")))
    applied, skipped = [], []
    reviewer = ""
    reviewed_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    for r in rules:
        code = r["code"]
        d = decisions.get(code)
        if not d or not (d.get("decision") or "").strip():
            skipped.append(code)
            continue
        decision = d["decision"].strip()
        if decision not in ("通过", "修改", "删除"):
            sys.exit(f"{code}: decision 必须是 通过/修改/删除，实际 {decision!r}")
        if decision == "删除":
            sys.exit(f"{code}: 暂不支持删除规则（会改变判定），请改 new_action 或人工处理")
        if decision == "修改":
            if d.get("new_action"):
                r["action"] = d["new_action"].strip()
            if d.get("new_tags"):
                r["tags"] = d["new_tags"].strip()
        r["status"] = "已审核"
        r["reviewer"] = (d.get("reviewer") or reviewer or "指导教师").strip()
        r["reviewed_at"] = reviewed_at
        reviewer = r["reviewer"]
        applied.append((code, decision, d.get("comment") or ""))

    if not applied:
        sys.exit("审核表里没有任何 decision，未做修改")

    with open(src, "w", encoding="utf-8", newline="\n") as f:
        w = _csv.DictWriter(f, fieldnames=list(rules[0].keys()))
        w.writeheader()
        w.writerows(rules)

    con = _connect()
    for code, decision, comment in applied:
        con.execute(
            "INSERT INTO Rule_Review (rule_code, action, reviewer, reviewed_at, comment) VALUES (?,?,?,?,?)",
            (code, decision, reviewer, reviewed_at, comment),
        )
    con.commit()
    con.close()

    print(f"已写入 {len(applied)} 条审核记录，审阅人：{reviewer}")
    if skipped:
        print(f"未填 decision 而跳过的规则：{skipped}")
    print(f"下一步：确认 version.py 的 RULE_VERSION（当前 {RULE_VERSION}），然后 python init_db.py")


def _current_verdicts() -> dict:
    from rule_engine import evaluate, load_rules, SUPPORTED_CONSTITUTIONS

    con = _connect()
    dishes = [dict(r) for r in con.execute("SELECT id, name FROM Dish")]
    tags = {}
    for r in con.execute("SELECT dish_id, tag FROM Dish_Tag"):
        tags.setdefault(r["dish_id"], set()).add(r["tag"])
    con.close()

    out = {}
    for c in SUPPORTED_CONSTITUTIONS:
        rules = load_rules(c)
        out[c] = {
            d["name"]: evaluate(d, c, rules=rules, tags=tags.get(d["id"], set()))["verdict"]
            for d in dishes
        }
    return out


def cmd_snapshot() -> None:
    """把当前全量判定存成快照，供后续 resync 对比。"""
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    from version import RULE_VERSION

    payload = {
        "taken_at": datetime.now().isoformat(timespec="seconds"),
        "rule_version": RULE_VERSION,
        "verdicts": _current_verdicts(),
    }
    path = SNAPSHOT_DIR / f"verdicts_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存快照 {path.name}（规则版本 {RULE_VERSION}）")


def cmd_resync() -> None:
    """对比最近一次快照与当前判定：哪些菜翻盘、哪些金标受影响。"""
    if not SNAPSHOT_DIR.exists() or not list(SNAPSHOT_DIR.glob("verdicts_*.json")):
        sys.exit("没有快照，先运行 python tools.py snapshot")
    latest = max(SNAPSHOT_DIR.glob("verdicts_*.json"), key=lambda p: p.stat().st_mtime)
    old = json.loads(latest.read_text(encoding="utf-8"))["verdicts"]
    new = _current_verdicts()

    flips = []
    for c in new:
        for name, v_now in new[c].items():
            v_old = old.get(c, {}).get(name)
            if v_old and v_old != v_now:
                flips.append((c, name, v_old, v_now))

    print(f"对比基准：{latest.name}")
    print(f"判定翻盘：{len(flips)} 条")
    for c, name, a, b in flips[:20]:
        print(f"  {c} × {name}: {a} → {b}")

    if GOLD_JSON.exists():
        gold = json.loads(GOLD_JSON.read_text(encoding="utf-8")).get("labels", [])
        affected = [
            g for g in gold
            if any(f[0] == g["constitution"] and f[1] == g["name"] for f in flips)
        ]
        print(f"受影响金标：{len(affected)} 条（需要复核标注是否仍然成立）")
        for g in affected[:10]:
            print(f"  {g['constitution']} × {g['name']}（原标注 {g['expected']}）")


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "template":
        cmd_template()
    elif cmd == "import":
        if len(argv) < 2:
            sys.exit("用法：python tools.py import 文件.csv --write")
        cmd_import(argv[1], write="--write" in argv)
    elif cmd == "labels":
        cmd_labels(validate="--validate" in argv)
    elif cmd == "quality":
        cmd_quality()
    elif cmd == "gate":
        return cmd_gate()
    elif cmd == "hook":
        return cmd_hook(install="--install" in argv)
    elif cmd == "candidate":
        sub = argv[1] if len(argv) > 1 else "list"
        if sub in ("approve", "reject"):
            if len(argv) < 3:
                sys.exit(f"用法：python tools.py candidate {sub} <编号>")
            reviewer = ""
            for i, a in enumerate(argv):
                if a == "--reviewer" and i + 1 < len(argv):
                    reviewer = argv[i + 1]
            reason = ""
            for i, a in enumerate(argv):
                if a == "--reason" and i + 1 < len(argv):
                    reason = argv[i + 1]
            return cmd_candidate(sub, int(argv[2]), reviewer, reason)
        return cmd_candidate("list")
    elif cmd == "tag-review":
        if "--apply" in argv:
            target = argv[argv.index("--apply") + 1] if argv.index("--apply") + 1 < len(argv) else ""
            if not target:
                sys.exit("用法：python tools.py tag-review --apply 文件.csv")
            return cmd_tag_review(apply_file=target)
        n = 30
        if "--n" in argv:
            i = argv.index("--n")
            n = int(argv[i + 1]) if i + 1 < len(argv) else 30
        return cmd_tag_review(n=n)
    elif cmd == "data-review":
        if len(argv) < 2:
            sys.exit("用法：python tools.py data-review 审核表.xlsx --write [--reviewer 姓名]")
        reviewer = ""
        for i, a in enumerate(argv):
            if a == "--reviewer" and i + 1 < len(argv):
                reviewer = argv[i + 1]
        return cmd_data_review(argv[1], write="--write" in argv, reviewer=reviewer)
    elif cmd == "review":
        cmd_review(apply="--apply" in argv)
    elif cmd == "snapshot":
        cmd_snapshot()
    elif cmd == "resync":
        cmd_resync()
    else:
        sys.exit(f"未知命令 {cmd!r}，可用：template / import / labels / quality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
