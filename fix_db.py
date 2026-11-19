# -*- coding: utf-8 -*-
"""兼容旧入口：执行非破坏式数据库迁移和幂等数据导入。"""

from import_data import import_data
from init_db_v22 import migrate_database


if __name__ == "__main__":
    migrate_database()
    imported, skipped = import_data()
    print(f"数据库维护完成：处理 {imported} 条档口记录，拒绝 {skipped} 条分类标签。")
