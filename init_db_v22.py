# -*- coding: utf-8 -*-
"""幂等初始化与 P0 数据迁移，不会清空现有数据库。"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).with_name("food.db")
FORBIDDEN_WORDS_PATH = Path(__file__).with_name("forbidden_words.txt")
CATEGORY_NAMES = {"套餐", "自选套餐", "一大荤一素", "一荤一素", "两荤一素", "一大荤两素"}
CATEGORY_PATTERN = re.compile(
    r"^(?:\d+|[一二两三四五六七八九])?大?荤(?:\d+|[一二两三四五六七八九])?素$"
)
DISH_ALIASES = {"风味黄焖鸡米饭": "黄焖鸡米饭"}
MEAT_TERMS = ("鸡", "鸭", "鹅", "猪", "牛", "羊", "鱼", "虾", "蟹", "肉", "排骨", "火腿")
GLUTEN_TERMS = ("面", "馒头", "饼", "包子", "小麦", "拉面")
SEED_DISHES = (
    ("麻辣香锅", "辛辣、重油", "辛温助热，油腻生湿，湿热体质应少吃。"),
    ("山药鸡汤", "温补、清淡", "山药健脾益气，鸡汤温补，适合气虚体质适量食用。"),
    ("清炒时蔬", "清淡、少油", "蔬菜清淡易消化，可帮助减少油腻和积热。"),
)


def _load_forbidden_words() -> tuple[str, ...]:
    if not FORBIDDEN_WORDS_PATH.exists():
        raise FileNotFoundError(f"缺少硬规则配置文件：{FORBIDDEN_WORDS_PATH}")
    content = FORBIDDEN_WORDS_PATH.read_text(encoding="utf-8-sig")
    terms = [
        term.strip()
        for term in re.split(r"[,，\s]+", content)
        if term.strip()
    ]
    if not terms:
        raise ValueError("硬规则配置文件不能为空")
    return tuple(dict.fromkeys(terms))


def _is_category(name: str) -> bool:
    value = (name or "").strip()
    return value in CATEGORY_NAMES or bool(CATEGORY_PATTERN.fullmatch(value))


def _ensure_calories_column(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(Dish)")}
    if "calories" not in columns:
        connection.execute("ALTER TABLE Dish ADD COLUMN calories REAL")


def _ensure_schema(connection: sqlite3.Connection) -> None:
    for statement in (
        """
        CREATE TABLE IF NOT EXISTS Dish (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            property TEXT NOT NULL,
            explanation TEXT NOT NULL,
            calories REAL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Canteen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dish_id INTEGER NOT NULL,
            location TEXT NOT NULL,
            window_name TEXT NOT NULL,
            price REAL,
            FOREIGN KEY (dish_id) REFERENCES Dish(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Emotion_Rule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emotion TEXT NOT NULL,
            constitution TEXT NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('推荐', '禁忌')),
            dish_id INTEGER NOT NULL,
            FOREIGN KEY (dish_id) REFERENCES Dish(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Constraint_Rule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            constraint_type TEXT NOT NULL,
            dish_id INTEGER NOT NULL,
            FOREIGN KEY (dish_id) REFERENCES Dish(id)
        )
        """,
    ):
        connection.execute(statement)
    connection.executemany(
        """
        INSERT OR IGNORE INTO Dish (name, property, explanation)
        VALUES (?, ?, ?)
        """,
        SEED_DISHES,
    )


def _merge_dish_aliases(connection: sqlite3.Connection) -> int:
    merged = 0
    for old_name, canonical_name in DISH_ALIASES.items():
        old = connection.execute("SELECT id FROM Dish WHERE name=?", (old_name,)).fetchone()
        if not old:
            continue
        old_id = old[0]
        canonical = connection.execute(
            "SELECT id FROM Dish WHERE name=?", (canonical_name,)
        ).fetchone()
        if not canonical:
            connection.execute(
                "UPDATE Dish SET name=? WHERE id=?", (canonical_name, old_id)
            )
            merged += 1
            continue

        canonical_id = canonical[0]
        connection.execute(
            """
            INSERT OR IGNORE INTO Canteen (dish_id, location, window_name, price)
            SELECT ?, location, window_name, price FROM Canteen WHERE dish_id=?
            """,
            (canonical_id, old_id),
        )
        connection.execute("DELETE FROM Canteen WHERE dish_id=?", (old_id,))
        connection.execute(
            """
            INSERT OR IGNORE INTO Emotion_Rule (emotion, constitution, action, dish_id)
            SELECT emotion, constitution, action, ? FROM Emotion_Rule WHERE dish_id=?
            """,
            (canonical_id, old_id),
        )
        connection.execute("DELETE FROM Emotion_Rule WHERE dish_id=?", (old_id,))
        connection.execute(
            """
            INSERT OR IGNORE INTO Constraint_Rule (constraint_type, dish_id)
            SELECT constraint_type, ? FROM Constraint_Rule WHERE dish_id=?
            """,
            (canonical_id, old_id),
        )
        connection.execute("DELETE FROM Constraint_Rule WHERE dish_id=?", (old_id,))
        connection.execute("DELETE FROM Dish WHERE id=?", (old_id,))
        merged += 1
    return merged


def _seed_rules(connection: sqlite3.Connection) -> tuple[int, int]:
    dish_rows = connection.execute(
        "SELECT id, name, property, explanation FROM Dish"
    ).fetchall()
    constraint_rows = []
    emotion_rows = []

    for dish_id, name, property_info, explanation in dish_rows:
        name = name or ""
        combined = f"{name}{property_info or ''}{explanation or ''}"
        # 先剥离蛋奶词再判肉：'鸡蛋炒肉' 要算肉，'鸡蛋' 不能算肉
        egg_dairy = ("鸡蛋", "鸭蛋", "鹅蛋", "鹌鹑蛋", "皮蛋", "咸蛋", "蛋", "奶", "芝士", "奶酪", "黄油")
        stripped = name
        for term in egg_dairy:
            stripped = stripped.replace(term, "")
        has_meat = any(term in stripped for term in MEAT_TERMS)
        has_egg_dairy = any(term in name for term in egg_dairy)
        if has_meat:
            constraint_rows.append(("蛋奶素", dish_id))   # 只排肉，保留蛋奶
        if has_meat or has_egg_dairy:
            constraint_rows.append(("素食", dish_id))     # 纯素：肉与蛋奶都排
        if any(term in combined for term in ("辣", "麻辣", "辛辣")):
            constraint_rows.append(("不吃辣", dish_id))
        if "苦" in combined:
            constraint_rows.append(("不吃苦味", dish_id))
        if any(term in name for term in GLUTEN_TERMS):
            constraint_rows.append(("无麸质", dish_id))

        risk_signals = _load_forbidden_words()
        if not any(signal in combined for signal in risk_signals):
            for emotion, constitution, clues in (
                ("思", "气虚", ("健脾", "益气", "养胃", "易消化", "温补")),
                ("忧", "气虚", ("温润", "温补", "健脾", "易消化")),
                ("怒", "湿热", ("清淡", "凉润", "清热")),
            ):
                if any(clue in combined for clue in clues):
                    emotion_rows.append((emotion, constitution, "推荐", dish_id))

    connection.executemany(
        """
        INSERT OR IGNORE INTO Constraint_Rule (constraint_type, dish_id)
        VALUES (?, ?)
        """,
        constraint_rows,
    )
    connection.executemany(
        """
        INSERT OR IGNORE INTO Emotion_Rule (emotion, constitution, action, dish_id)
        VALUES (?, ?, ?, ?)
        """,
        emotion_rows,
    )
    constraint_count = connection.execute(
        "SELECT COUNT(*) FROM Constraint_Rule"
    ).fetchone()[0]
    emotion_count = connection.execute(
        "SELECT COUNT(*) FROM Emotion_Rule"
    ).fetchone()[0]
    return constraint_count, emotion_count


def migrate_database() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        _ensure_schema(connection)
        _ensure_calories_column(connection)
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_canteen_listing
            ON Canteen(dish_id, location, window_name)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_emotion_rule
            ON Emotion_Rule(emotion, constitution, action, dish_id)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_constraint_rule
            ON Constraint_Rule(constraint_type, dish_id)
            """
        )

        category_ids = [
            row[0]
            for row in connection.execute("SELECT id, name FROM Dish").fetchall()
            if _is_category(row[1])
        ]
        if category_ids:
            placeholders = ",".join("?" for _ in category_ids)
            for table in ("Canteen", "Emotion_Rule", "Constraint_Rule"):
                connection.execute(
                    f"DELETE FROM {table} WHERE dish_id IN ({placeholders})",
                    category_ids,
                )
            connection.execute(
                f"DELETE FROM Dish WHERE id IN ({placeholders})", category_ids
            )

        merged = _merge_dish_aliases(connection)
        constraint_count, emotion_count = _seed_rules(connection)

    print(
        f"迁移完成：清理分类菜品 {len(category_ids)} 条，"
        f"合并菜名 {merged} 项；规则表当前新增候选 "
        f"{constraint_count} 条限制规则、{emotion_count} 条情志偏好。"
    )
    return constraint_count, emotion_count


if __name__ == "__main__":
    migrate_database()
