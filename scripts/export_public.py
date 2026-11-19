# -*- coding: utf-8 -*-
"""导出一个可公开的干净仓库（不含 .git 历史、照片、数据库、浏览器配置）。

用法：
    python scripts/export_public.py
    # 输出到 .export/zhishan-public，随后 git init / commit / push

只复制 `git ls-files` 列出的文件——也就是说，未经跟踪的东西不会被带出去。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "zhishan-public"

# 额外保险：即使被跟踪也排除
BLOCK = ("docs/sources/", "food.db", ".export/", ".git/", "design/.edge/", "design/.chrome/")
BLOCK_EXACT = (".env",)


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
        cwd=ROOT, capture_output=True,
    )
    if out.returncode != 0:
        raise SystemExit("不是 git 仓库，或 git 不可用")
    return [p.decode("utf-8") for p in out.stdout.split(b"\0") if p]


def main() -> None:
    files = tracked_files()
    kept, skipped = [], []
    for rel in files:
        if rel in BLOCK_EXACT or any(rel.startswith(b) for b in BLOCK):
            skipped.append(rel)
            continue
        kept.append(rel)

    if OUT.exists():
        shutil.rmtree(OUT, ignore_errors=True)
        if OUT.exists():
            raise SystemExit(f"{OUT} 无法删除（可能被占用），请先关闭占用它的程序")
    OUT.mkdir(parents=True)

    for rel in kept:
        src = ROOT / rel
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    total = sum((OUT / f).stat().st_size for f in kept)
    print(f"导出 {len(kept)} 个文件，{total / 1024 / 1024:.1f} MB → {OUT}")
    if skipped:
        print("排除：", skipped)

    # 自检：不该出现的名字与照片
    bad = []
    for rel in kept:
        if rel.lower().endswith((".jpg", ".jpeg")):
            bad.append(f"图片：{rel}")
            continue
        try:
            text = (OUT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError):
            continue
        for word in ("C:" + chr(92) + "Users",):
            if word in text:
                bad.append(f"{rel} 含 {word}")

    print("自检：", "通过" if not bad else f"发现 {len(bad)} 处问题")
    for b in bad[:10]:
        print("  -", b)


if __name__ == "__main__":
    main()
