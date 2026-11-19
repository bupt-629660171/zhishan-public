# -*- coding: utf-8 -*-
"""知源智膳 · Schema 迁移（幂等、非破坏、带版本）。

设计原则：
    1. 只增不删：老表结构保留，避免把已跑通的 MVP 弄坏；
    2. 所有新表都从 CSV 重建（rules.csv / aliases.csv 是唯一真源）；
    3. Dish_Tag 由 tags.derive_tags() 派生，可随时重算；
    4. 每次迁移把结果写到 schema_migrations 表，方便回溯。
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import tags as tagkit
import version


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "food.db"
RULES_PATH = BASE_DIR / "rules.csv"
ALIASES_PATH = BASE_DIR / "aliases.csv"

VALID_ACTIONS = ("禁", "慎", "宜")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DATABASE_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _ensure_tables(con: sqlite3.Connection) -> None:
    for statement in (
        """
        CREATE TABLE IF NOT EXISTS Dish_Tag (
            dish_id INTEGER NOT NULL,
            tag     TEXT NOT NULL,
            evidence TEXT,
            tag_version TEXT NOT NULL,
            PRIMARY KEY (dish_id, tag),
            FOREIGN KEY (dish_id) REFERENCES Dish(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Dish_Alias (
            alias      TEXT PRIMARY KEY,
            dish_name  TEXT NOT NULL,
            alias_type TEXT,
            note       TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL UNIQUE,
            constitution TEXT NOT NULL,
            action      TEXT NOT NULL CHECK (action IN ('禁','慎','宜')),
            tag         TEXT NOT NULL,
            rationale   TEXT NOT NULL,
            source_ref  TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT '草案',
            version     TEXT NOT NULL,
            reviewer    TEXT,
            reviewed_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Rule_Review (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_code   TEXT NOT NULL,
            action      TEXT NOT NULL,
            reviewer    TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            comment     TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Tag_Review (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            dish_name   TEXT NOT NULL,
            verdict     TEXT NOT NULL,
            remove_tags TEXT,
            add_tags    TEXT,
            reviewer    TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            comment     TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Candidate (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            kind          TEXT NOT NULL,              -- fix | new
            name          TEXT NOT NULL,
            property      TEXT,
            explanation   TEXT,
            location      TEXT,
            window_name   TEXT,
            price         REAL,
            campus        TEXT,
            note          TEXT,
            status        TEXT NOT NULL DEFAULT '待审',
            submitted_by  TEXT,
            submitted_at  TEXT NOT NULL,
            reviewer      TEXT,
            reviewed_at   TEXT,
            review_comment TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Checkin (
            day        TEXT PRIMARY KEY,
            bloating   INTEGER,
            stool_ok   INTEGER,
            tired      INTEGER,
            note       TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Dish_Review (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            dish_name   TEXT NOT NULL,
            decision    TEXT NOT NULL,
            reviewer    TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            comment     TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Dish_Source (
            dish_id      INTEGER PRIMARY KEY,
            source_type  TEXT NOT NULL,
            source_ref   TEXT,
            collected_by TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            campus       TEXT NOT NULL,
            FOREIGN KEY (dish_id) REFERENCES Dish(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            schema_version TEXT NOT NULL,
            rule_version   TEXT NOT NULL,
            tag_version    TEXT NOT NULL,
            applied_at     TEXT NOT NULL,
            detail         TEXT
        )
        """,
    ):
        con.execute(statement)


def _ensure_rule_review_without_fk(con: sqlite3.Connection) -> int:
    """审计记录必须独立于 Rules 表。

    早期版本给 Rule_Review 加了外键，导致 load_rules() 全量重建 Rules 时
    触发 FOREIGN KEY constraint failed。审核历史是只增不改的审计日志，
    应当比当前规则表活得更久，因此这里去掉外键并保留已有记录。
    """
    fks = con.execute("PRAGMA foreign_key_list(Rule_Review)").fetchall()
    if not fks:
        return 0
    rows = con.execute(
        "SELECT rule_code, action, reviewer, reviewed_at, comment FROM Rule_Review"
    ).fetchall()
    con.execute("ALTER TABLE Rule_Review RENAME TO Rule_Review_old")
    con.execute(
        """
        CREATE TABLE Rule_Review (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_code   TEXT NOT NULL,
            action      TEXT NOT NULL,
            reviewer    TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            comment     TEXT
        )
        """
    )
    con.executemany(
        "INSERT INTO Rule_Review (rule_code, action, reviewer, reviewed_at, comment) VALUES (?,?,?,?,?)",
        rows,
    )
    con.execute("DROP TABLE Rule_Review_old")
    return len(rows)


def rebuild_tags(con: sqlite3.Connection) -> int:
    """从菜品文本重新派生标签，写入 Dish_Tag（先清后建，保证幂等）。"""
    rows = con.execute("SELECT id, name, property, explanation FROM Dish").fetchall()
    con.execute("DELETE FROM Dish_Tag")
    count = 0
    for dish_id, name, prop, expl in rows:
        derived = tagkit.derive_tags(name, prop, expl)
        for tag in sorted(derived):
            con.execute(
                "INSERT OR REPLACE INTO Dish_Tag (dish_id, tag, evidence, tag_version) VALUES (?,?,?,?)",
                (dish_id, tag, (prop or "")[:30], version.TAG_VERSION),
            )
            count += 1
    return count


def load_rules(con: sqlite3.Connection) -> tuple[int, list[str]]:
    """把 rules.csv 全量同步进 Rules 表，返回 (规则数, 警告)。"""
    if not RULES_PATH.exists():
        raise FileNotFoundError(f"缺少规则文件：{RULES_PATH}")

    warnings: list[str] = []
    rows: list[dict] = []
    with RULES_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "code", "constitution", "action", "tags", "rationale",
            "source_ref", "status", "version",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"rules.csv 缺字段：{sorted(required - set(reader.fieldnames or []))}")
        for line, row in enumerate(reader, start=2):
            code = (row.get("code") or "").strip()
            action = (row.get("action") or "").strip()
            tag = (row.get("tags") or "").strip()
            if not code:
                raise ValueError(f"第 {line} 行缺少 code")
            if action not in VALID_ACTIONS:
                raise ValueError(f"第 {line} 行 action 必须是 禁/慎/宜，实际 {action!r}")
            known = {d.tag for d in tagkit.TAG_DEFS}
            if tag not in known:
                raise ValueError(f"第 {line} 行 tags 未知标签 {tag!r}，可选：{sorted(known)}")
            if not (row.get("source_ref") or "").strip():
                warnings.append(f"{code}: 缺少 source_ref，影响可追溯性")
            rows.append(row)

    con.execute("DELETE FROM Rules")
    for row in rows:
        con.execute(
            """
            INSERT INTO Rules
                (code, constitution, action, tag, rationale, source_ref,
                 status, version, reviewer, reviewed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["code"].strip(),
                row["constitution"].strip(),
                row["action"].strip(),
                row["tags"].strip(),
                row["rationale"].strip(),
                row["source_ref"].strip(),
                (row.get("status") or "草案").strip(),
                (row.get("version") or version.RULE_VERSION).strip(),
                (row.get("reviewer") or "").strip() or None,
                (row.get("reviewed_at") or "").strip() or None,
            ),
        )
    return len(rows), warnings


def load_aliases(con: sqlite3.Connection) -> tuple[int, list[str]]:
    """载入别名表；指向库外菜品的别名允许存在，但会给出警告。"""
    con.execute("DELETE FROM Dish_Alias")
    if not ALIASES_PATH.exists():
        return 0, [f"缺少别名文件：{ALIASES_PATH}"]
    names = {r[0] for r in con.execute("SELECT name FROM Dish")}
    count = 0
    warnings: list[str] = []
    with ALIASES_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            alias = (row.get("alias") or "").strip()
            dish = (row.get("dish_name") or "").strip()
            if not alias or not dish:
                raise ValueError(f"aliases.csv 第 {line} 行 alias/dish_name 为空")
            if alias == dish:  # 仅登记标准名，不做自映射
                continue
            if dish not in names:
                warnings.append(f"别名 {alias!r} → {dish!r}：库内暂无此菜品")
            con.execute(
                "INSERT OR REPLACE INTO Dish_Alias (alias, dish_name, alias_type, note) VALUES (?,?,?,?)",
                (alias, dish, (row.get("alias_type") or "").strip(), (row.get("note") or "").strip()),
            )
            count += 1
    return count, warnings


def migrate() -> dict[str, object]:
    from datetime import datetime

    con = _connect()
    try:
        # WAL：读不阻塞写，为后续"前端收反馈 + 后台合并"做准备
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("BEGIN")
        _ensure_tables(con)
        review_rows = _ensure_rule_review_without_fk(con)
        tag_count = rebuild_tags(con)
        rule_count, rule_warnings = load_rules(con)
        alias_count, alias_warnings = load_aliases(con)
        applied_at = datetime.now().isoformat(timespec="seconds")
        con.execute(
            """
            INSERT INTO schema_migrations
                (schema_version, rule_version, tag_version, applied_at, detail)
            VALUES (?,?,?,?,?)
            """,
            (
                version.SCHEMA_VERSION,
                version.RULE_VERSION,
                version.TAG_VERSION,
                applied_at,
                f"tags={tag_count} rules={rule_count} aliases={alias_count}",
            ),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    return {
        "tags": tag_count,
        "rules": rule_count,
        "aliases": alias_count,
        "warnings": rule_warnings + alias_warnings,
    }


def stats() -> dict[str, int]:
    con = _connect()
    try:
        return {
            "dish": con.execute("SELECT COUNT(*) FROM Dish").fetchone()[0],
            "tagged": con.execute("SELECT COUNT(DISTINCT dish_id) FROM Dish_Tag").fetchone()[0],
            "rules": con.execute("SELECT COUNT(*) FROM Rules").fetchone()[0],
            "aliases": con.execute("SELECT COUNT(*) FROM Dish_Alias").fetchone()[0],
        }
    finally:
        con.close()


if __name__ == "__main__":
    result = migrate()
    print(f"Schema v{version.SCHEMA_VERSION} 迁移完成：{result}")
    for w in result["warnings"]:
        print("  ⚠", w)
