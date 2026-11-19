# -*- coding: utf-8 -*-
"""从 food.csv 幂等导入具体菜品和档口记录。"""

from __future__ import annotations

import csv
import re
import sqlite3
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "food.db"
CSV_PATH = BASE_DIR / "food.csv"
CATEGORY_NAMES = {"套餐", "自选套餐", "一大荤一素", "一荤一素", "两荤一素", "一大荤两素"}
CATEGORY_PATTERN = re.compile(
    r"^(?:\d+|[一二两三四五六七八九])?大?荤(?:\d+|[一二两三四五六七八九])?素$"
)
DISH_ALIASES = {"风味黄焖鸡米饭": "黄焖鸡米饭"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def is_category_name(name: str) -> bool:
    value = (name or "").strip()
    return value in CATEGORY_NAMES or bool(CATEGORY_PATTERN.fullmatch(value))


def _optional_float(value: str | None, field: str, line_number: int) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"第 {line_number} 行 {field} 不是有效数字：{value}") from exc
    if number < 0:
        raise ValueError(f"第 {line_number} 行 {field} 不能为负数")
    return number


def _optional_price(value: str | None, line_number: int) -> float | None:
    """未知或非正价格统一按 NULL 入库，不用 0 冒充真实售价。"""
    value = (value or "").strip()
    if not value:
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"第 {line_number} 行 price 不是有效数字：{value}") from exc
    return number if number > 0 else None


def import_data() -> tuple[int, int]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"找不到数据文件：{CSV_PATH}")

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"name", "property", "explanation", "location", "window_name", "price"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV 必须包含字段：{', '.join(sorted(required))}")

        imported = 0
        skipped_categories = 0
        provenance_missing = 0
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(Dish)").fetchall()
            }
            if "calories" not in columns:
                connection.execute("ALTER TABLE Dish ADD COLUMN calories REAL")
            if "kind" not in columns:
                # dish=可推荐的菜品；ingredient=基础食材（只用于查询，不进方案推荐）
                connection.execute("ALTER TABLE Dish ADD COLUMN kind TEXT DEFAULT 'dish'")
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_canteen_listing
                ON Canteen(dish_id, location, window_name)
                """
            )
            connection.execute(
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
                """
            )

            for line_number, row in enumerate(reader, start=2):
                name = (row.get("name") or "").strip()
                if not name:
                    raise ValueError(f"第 {line_number} 行缺少菜品名称")
                if is_category_name(name):
                    skipped_categories += 1
                    continue

                property_info = (row.get("property") or "").strip()
                explanation = (row.get("explanation") or "").strip()
                location = (row.get("location") or "").strip()
                window_name = (row.get("window_name") or "").strip()
                note = (row.get("note") or "").strip()
                if not property_info or not explanation:
                    raise ValueError(f"第 {line_number} 行缺少 property 或 explanation")
                if bool(location) != bool(window_name):
                    raise ValueError(f"第 {line_number} 行 location/window_name 必须同时填写或同时留空")
                if not location and note != "档口待核实":
                    raise ValueError(f"第 {line_number} 行未填写档口时，note 必须为“档口待核实”")

                price = _optional_price(row.get("price"), line_number)
                calories = _optional_float(row.get("calories"), "calories", line_number)
                kind = (row.get("kind") or "dish").strip() or "dish"
                if kind not in ("dish", "ingredient"):
                    raise ValueError(f"第 {line_number} 行 kind 只能是 dish/ingredient")
                canonical_name = DISH_ALIASES.get(name, name)

                connection.execute(
                    """
                    INSERT INTO Dish (name, property, explanation, calories, kind)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        property = excluded.property,
                        explanation = excluded.explanation,
                        calories = COALESCE(excluded.calories, Dish.calories),
                        kind = excluded.kind
                    """,
                    (canonical_name, property_info, explanation, calories, kind),
                )
                dish_id = connection.execute(
                    "SELECT id FROM Dish WHERE name = ?", (canonical_name,)
                ).fetchone()[0]
                if location:
                    connection.execute(
                        """
                        INSERT INTO Canteen (dish_id, location, window_name, price)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(dish_id, location, window_name) DO UPDATE SET
                            price = excluded.price
                        """,
                        (dish_id, location, window_name, price),
                    )

                # 溯源：一条记录必须能回答"谁、什么时候、从哪里、在哪个校区采的"
                campus = (row.get("campus") or "").strip()
                if not campus:
                    raise ValueError(f"第 {line_number} 行缺少 campus（校区），多校区数据必须标明来源校区")
                src = {
                    "source_type": (row.get("source_type") or "").strip() or "待补充",
                    "source_ref": (row.get("source_ref") or "").strip(),
                    "collected_by": (row.get("collected_by") or "").strip() or "待补充",
                    "collected_at": (row.get("collected_at") or "").strip() or "待补充",
                    "campus": campus,
                }
                if src["source_type"] == "待补充":
                    provenance_missing += 1
                connection.execute(
                    """
                    INSERT INTO Dish_Source
                        (dish_id, source_type, source_ref, collected_by, collected_at, campus)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(dish_id) DO UPDATE SET
                        source_type = excluded.source_type,
                        source_ref = excluded.source_ref,
                        collected_by = excluded.collected_by,
                        collected_at = excluded.collected_at,
                        campus = excluded.campus
                    """,
                    (dish_id, src["source_type"], src["source_ref"],
                     src["collected_by"], src["collected_at"], src["campus"]),
                )
                imported += 1

    return imported, skipped_categories


if __name__ == "__main__":
    count, skipped = import_data()
    print(f"导入完成：处理 {count} 条具体菜品档口记录，拒绝 {skipped} 条分类标签。")
