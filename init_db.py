# -*- coding: utf-8 -*-
"""知源智膳 · 一键初始化（幂等）。

把"导入菜品 → 建表 → 判规则 → 派生标签"固定成一个顺序，避免标签在导入前派生。

用法：
    python init_db.py           # 首次部署 / 每次改完 food.csv 或 rules.csv 后
    python init_db.py --check   # 只检查状态，不写库
"""

from __future__ import annotations

import sys

import sqlite3

import schema
from import_data import import_data
from init_db_v22 import _ensure_schema as ensure_base_tables
from init_db_v22 import migrate_database as legacy_migrate
from version import RULE_VERSION, SCHEMA_VERSION, TAG_VERSION


def main() -> int:
    if "--check" in sys.argv:
        print(f"Schema v{SCHEMA_VERSION} / 规则 v{RULE_VERSION} / 标签 v{TAG_VERSION}")
        print("当前库内状态：", schema.stats())
        return 0

    # 0) 全新环境下先建基础表（Dish/Canteen/Constraint_Rule/Emotion_Rule），
    #    否则 import_data 的 ALTER TABLE 会因为表不存在而失败
    with sqlite3.connect(schema.DATABASE_PATH) as con:
        con.execute("PRAGMA foreign_keys = ON")
        ensure_base_tables(con)
        con.commit()

    # 1) 再把 CSV 里的菜品导入（幂等）
    imported, skipped = import_data()
    print(f"① 菜品导入：处理 {imported} 条档口记录，跳过分类标签 {skipped} 条")

    # 2) 建表 + 载入规则 + 从菜品文本重新派生标签
    result = schema.migrate()
    print(f"② 规则与标签：{result['tags']} 个标签、{result['rules']} 条规则、{result['aliases']} 个别名")

    # 3) 用户限制表（素食/无麸质/不吃辣/不吃苦味）——新菜必须重新派生，
    #    否则"素食"这类硬约束对新增菜品不生效（曾导致 43 条单测里素食用例失败）
    constraint_count, emotion_count = legacy_migrate()
    print(f"③ 限制与情志规则：{constraint_count} 条限制、{emotion_count} 条情志偏好")

    # 4) 校验：有没有菜一道标签都没有
    stats = schema.stats()
    print(f"④ 校验：菜品 {stats['dish']} 道，其中 {stats['tagged']} 道已打标签")

    warnings = result["warnings"]
    if warnings:
        print("⚠ 警告：")
        for w in warnings:
            print("   -", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
