# -*- coding: utf-8 -*-
"""知源智膳 · 稳定性压测（对应立项指标：系统连续 30 分钟无崩溃）。

用法：
    python stress_test.py                        # 默认 30 分钟、4 线程
    python stress_test.py --minutes 2 --workers 4  # 快速验证脚本本身
    python stress_test.py --minutes 30 --workers 8

测什么：
    1. 方案生成（不同体质/忌口/校区，随机种子）
    2. 单菜查询（正常名 / 口语 / 歧义 / 未收录 / 注入式输入）
    3. 模板解释（不联网路径）
    4. 并发：多线程同时读写同一 SQLite（WAL）

产出：控制台摘要 + docs/压测报告_<时间>.md + JSON。
判定：0 异常 + 结束时数据库完整性 OK + 数据行数不变 = 通过。
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import rule_engine as engine  # noqa: E402
import shafe_mvp as service  # noqa: E402

CONSTITUTIONS = list(engine.SUPPORTED_CONSTITUTIONS)
CONSTRAINTS = ["素食", "蛋奶素", "无麸质", "不吃苦味", "不吃辣"]
QUERY_POOL = [
    "黄焖鸡", "香锅", "拉面", "甜的", "炸的", "肉", "饭", "清蒸鱼",
    "燕麦拿铁", "'; DROP TABLE Rules; --", "麻辣香锅", "绿豆",
]


def _rss_mb() -> float:
    """进程常驻内存（MB）。无 psutil 时走 Windows PSAPI；失败返回 -1。"""
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return -1.0
        return pmc.WorkingSetSize / 1024 / 1024
    except Exception:
        return -1.0


def _db_snapshot() -> dict:
    with sqlite3.connect(engine.DATABASE_PATH) as con:
        return {
            "dish": con.execute("SELECT COUNT(*) FROM Dish").fetchone()[0],
            "canteen": con.execute("SELECT COUNT(*) FROM Canteen").fetchone()[0],
            "rules": con.execute("SELECT COUNT(*) FROM Rules").fetchone()[0],
            "tags": con.execute("SELECT COUNT(*) FROM Dish_Tag").fetchone()[0],
        }


def _one_round(rng: random.Random) -> tuple[float, str]:
    """跑一次随机操作，返回 (耗时ms, 操作名)。异常向上抛。"""
    t0 = time.perf_counter()
    op = rng.choices(
        ["plan", "plan_constrained", "query", "template"], weights=[5, 2, 3, 1]
    )[0]

    if op == "plan":
        engine.plan(rng.choice(CONSTITUTIONS), limit=3, seed=rng.randrange(10**6))
    elif op == "plan_constrained":
        engine.plan(
            rng.choice(CONSTITUTIONS),
            constraints=set(rng.sample(CONSTRAINTS, rng.randint(1, 2))),
            limit=3, seed=rng.randrange(10**6),
            campus=rng.choice([None, "沙河", "通用"]),
        )
    elif op == "query":
        service.check_food(rng.choice(CONSTITUTIONS), rng.choice(QUERY_POOL), has_ai_access=False)
    else:
        r = service.generate_diet_plan(rng.choice(CONSTITUTIONS), "平和", [], False)
        service.template_explanation(r)

    return (time.perf_counter() - t0) * 1000, op


def run(minutes: float, workers: int, quiet: bool = False) -> dict:
    stop_at = time.time() + minutes * 60
    stop = threading.Event()
    lat: list[float] = []
    errors: list[dict] = []
    counts: dict[str, int] = {}
    slow: list[dict] = []
    lock = threading.Lock()
    rss_start = _rss_mb()
    db_before = _db_snapshot()
    started = datetime.now()
    interrupted = False
    t_begin = time.time()

    def worker(wid: int) -> None:
        rng = random.Random(20261118 + wid)
        while not stop.is_set() and time.time() < stop_at:
            try:
                ms, op = _one_round(rng)
                with lock:
                    lat.append(ms)
                    counts[op] = counts.get(op, 0) + 1
                if ms > 5000:  # 正常 p99 约 50ms，超过 5s 一定是环境问题
                    with lock:
                        slow.append({
                            "ms": round(ms, 1), "op": op,
                            "at": datetime.now().isoformat(timespec="seconds"),
                        })
            except Exception as exc:
                with lock:
                    errors.append({"worker": wid, "error": repr(exc)[:200]})

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(workers)]
    for th in threads:
        th.start()

    next_beat = t_begin + 30
    try:
        while time.time() < stop_at and any(th.is_alive() for th in threads):
            time.sleep(0.5)
            if not quiet and time.time() >= next_beat:
                next_beat += 30
                elapsed = (time.time() - t_begin) / 60
                with lock:
                    n, e = len(lat), len(errors)
                    p95 = sorted(lat)[int(n * 0.95)] if n > 20 else 0
                print(f"  [{elapsed:5.1f}/{minutes:g} 分钟] 请求 {n}　异常 {e}　"
                      f"p95≈{p95:.1f}ms　内存 {_rss_mb():.0f}MB", flush=True)
    except KeyboardInterrupt:
        interrupted = True
        print("\n收到中断，生成部分报告…", flush=True)
    finally:
        stop.set()
        for th in threads:
            th.join(timeout=5)

    rss_end = _rss_mb()
    db_after = _db_snapshot()
    with sqlite3.connect(engine.DATABASE_PATH) as con:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]

    lat.sort()

    def pct(p: float) -> float:
        return lat[min(len(lat) - 1, int(len(lat) * p))] if lat else 0.0

    return {
        "started": started.isoformat(timespec="seconds"),
        "minutes": minutes,
        "workers": workers,
        "interrupted": interrupted,
        "requests": len(lat),
        "errors": len(errors),
        "error_samples": errors[:5],
        "slow_requests": sorted(slow, key=lambda x: -x["ms"])[:5],
        "suspend_suspected": bool(slow),
        "ops": counts,
        "latency_ms": {
            "p50": round(pct(0.50), 2), "p95": round(pct(0.95), 2),
            "p99": round(pct(0.99), 2), "max": round(lat[-1], 2) if lat else 0,
            "mean": round(statistics.mean(lat), 2) if lat else 0,
        },
        "throughput_per_sec": round(len(lat) / max(1.0, time.time() - t_begin), 2),
        "rss_mb": {"start": round(rss_start, 1), "end": round(rss_end, 1),
                    "growth": round(rss_end - rss_start, 1)},
        "db": {"before": db_before, "after": db_after, "integrity": integrity},
        "passed": (len(errors) == 0 and integrity == "ok" and db_before == db_after
                   and not interrupted),
    }


def write_report(result: dict) -> Path:
    out = BASE / "docs" / f"压测报告_{datetime.now():%Y%m%d_%H%M}.md"
    lat = result["latency_ms"]
    db = result["db"]
    lines = [
        "# 稳定性压测报告",
        "",
        f"- 开始时间：{result['started']}",
        f"- 时长：{result['minutes']} 分钟　｜　并发线程：{result['workers']}",
        f"- 总请求：{result['requests']}（{result['throughput_per_sec']} 次/秒）",
        f"- 异常：{result['errors']}",
        "",
        "## 延迟（毫秒）",
        "",
        "| p50 | p95 | p99 | max | mean |",
        "|---|---|---|---|---|",
        f"| {lat['p50']} | {lat['p95']} | {lat['p99']} | {lat['max']} | {lat['mean']} |",
        "",
        "## 操作分布",
        "",
    ]
    for k, v in sorted(result["ops"].items(), key=lambda x: -x[1]):
        lines.append(f"- {k}：{v}")
    lines += [
        "",
        "## 资源与数据",
        "",
        f"- 内存：{result['rss_mb']['start']} → {result['rss_mb']['end']} MB"
        f"（增长 {result['rss_mb']['growth']}）",
        f"- 数据库完整性：{db['integrity']}",
        f"- 行数：{db['before']} → {db['after']}",
        "",
        f"## 结论：{'通过' if result['passed'] else '未通过'}",
        "",
        "- 判定标准：0 异常 + 完整性 ok + 行数不变（压测只读，不应增删数据）",
    ]
    if result["slow_requests"]:
        lines += [
            "",
            "## ⚠ 慢请求（>5 秒）",
            "",
            "正常 p99 约 50ms。出现数秒级慢请求通常是**机器进入待机/休眠**、杀毒扫描或磁盘卡顿，",
            "不是代码卡死。压测前建议临时关闭自动睡眠。",
            "",
            "| 耗时(ms) | 操作 | 发生时间 |",
            "|---|---|---|",
        ]
        for s in result["slow_requests"]:
            lines.append(f"| {s['ms']} | {s['op']} | {s['at']} |")
    if result["interrupted"]:
        lines += ["", "> 本次为 Ctrl+C 中断后的部分结果，不代表完整 30 分钟。"]
    if result["error_samples"]:
        lines += ["", "## 异常样例", ""] + [f"- {e}" for e in result["error_samples"]]
    out.write_text("\n".join(lines), encoding="utf-8")
    out.with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--quiet", action="store_true", help="不打印每 30 秒的进度")
    args = ap.parse_args()

    if not engine.DATABASE_PATH.exists():
        sys.exit("缺少 food.db，请先运行 python init_db.py")

    print(f"压测开始：{args.minutes} 分钟，{args.workers} 线程，库 {engine.DATABASE_PATH.name}")
    print(f"预计结束 {datetime.fromtimestamp(time.time() + args.minutes * 60):%H:%M:%S}，"
          f"每 30 秒打印一次进度（Ctrl+C 可提前结束并出报告）", flush=True)
    result = run(args.minutes, args.workers, quiet=args.quiet)
    path = write_report(result)

    print()
    print(f"请求 {result['requests']}　异常 {result['errors']}")
    print(f"延迟 p50 {result['latency_ms']['p50']} / p95 {result['latency_ms']['p95']} / "
          f"max {result['latency_ms']['max']} ms")
    print(f"内存 {result['rss_mb']['start']} → {result['rss_mb']['end']} MB")
    print(f"完整性 {result['db']['integrity']}　行数变化 {result['db']['before'] == result['db']['after']}")
    print(f"报告：{path}")
    print("结论：", "通过" if result["passed"] else "未通过")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
