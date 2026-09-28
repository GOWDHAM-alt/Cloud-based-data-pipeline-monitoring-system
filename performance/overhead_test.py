"""
Phase 6 / Module 12: compares resource use with monitoring ON vs OFF.

Per the contract: measure CPU, memory and run time INDEPENDENTLY of the
monitor (the API receives nothing when MONITORING_ENABLED=false, so we
can't ask it for numbers). This script launches the pipeline as a
subprocess and samples that subprocess's own CPU/RSS with psutil while
it runs, then writes the raw numbers to a CSV so only measured values
go in the results table / paper — nothing here is estimated.

Run:
    python performance/overhead_test.py --runs 20 --interval 10
    (run from the pipelines/ directory so `python -m pipeline.run_pipeline` resolves)
"""

from __future__ import annotations

import argparse
import csv
import statistics
import subprocess
import sys
import time
from pathlib import Path

import psutil


def run_pipeline_once_and_measure(monitoring_enabled: bool, cwd: str) -> dict:
    env_overrides = {"MONITORING_ENABLED": "true" if monitoring_enabled else "false"}
    import os

    env = os.environ.copy()
    env.update(env_overrides)
    env["PYTHONPATH"] = "."

    wall_start = time.time()
    proc = subprocess.Popen(
        [sys.executable, "-m", "pipeline.run_pipeline"],
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    ps_proc = psutil.Process(proc.pid)

    cpu_samples = []
    rss_samples_mb = []

    # Prime cpu_percent (first call always returns 0.0)
    try:
        ps_proc.cpu_percent(interval=None)
    except psutil.NoSuchProcess:
        pass

    while proc.poll() is None:
        try:
            cpu_samples.append(ps_proc.cpu_percent(interval=0.2))
            rss_samples_mb.append(ps_proc.memory_info().rss / (1024 * 1024))
        except psutil.NoSuchProcess:
            break

    proc.wait()
    wall_elapsed = time.time() - wall_start

    return {
        "monitoring_enabled": monitoring_enabled,
        "wall_time_seconds": round(wall_elapsed, 4),
        "avg_cpu_percent": round(statistics.fmean(cpu_samples), 2) if cpu_samples else 0.0,
        "max_cpu_percent": round(max(cpu_samples), 2) if cpu_samples else 0.0,
        "avg_rss_mb": round(statistics.fmean(rss_samples_mb), 2) if rss_samples_mb else 0.0,
        "max_rss_mb": round(max(rss_samples_mb), 2) if rss_samples_mb else 0.0,
        "return_code": proc.returncode,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare pipeline overhead with monitoring on vs off.")
    parser.add_argument("--runs", type=int, default=10, help="Number of runs per setting")
    parser.add_argument("--cwd", type=str, default="..", help="Path to the pipelines/ directory")
    parser.add_argument("--out", type=str, default="overhead_results.csv")
    args = parser.parse_args()

    results = []
    for setting in (False, True):  # off first, then on
        label = "ON" if setting else "OFF"
        print(f"=== Monitoring {label}: {args.runs} runs ===")
        for i in range(args.runs):
            r = run_pipeline_once_and_measure(monitoring_enabled=setting, cwd=args.cwd)
            r["run_index"] = i
            results.append(r)
            print(f"  run {i+1}/{args.runs}: wall={r['wall_time_seconds']}s "
                  f"avg_cpu={r['avg_cpu_percent']}% avg_rss={r['avg_rss_mb']}MB")

    out_path = Path(args.out)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"\nRaw results written to {out_path}")
    _print_summary(results)


def _print_summary(results: list[dict]):
    for setting in (False, True):
        label = "ON" if setting else "OFF"
        subset = [r for r in results if r["monitoring_enabled"] == setting]
        if not subset:
            continue
        wall = [r["wall_time_seconds"] for r in subset]
        cpu = [r["avg_cpu_percent"] for r in subset]
        rss = [r["avg_rss_mb"] for r in subset]
        print(f"\nMonitoring {label} (n={len(subset)}):")
        print(f"  wall time:  mean={statistics.fmean(wall):.3f}s  stdev={statistics.pstdev(wall):.3f}s")
        print(f"  avg cpu%:   mean={statistics.fmean(cpu):.2f}   stdev={statistics.pstdev(cpu):.2f}")
        print(f"  avg rss MB: mean={statistics.fmean(rss):.2f}   stdev={statistics.pstdev(rss):.2f}")


if __name__ == "__main__":
    main()
