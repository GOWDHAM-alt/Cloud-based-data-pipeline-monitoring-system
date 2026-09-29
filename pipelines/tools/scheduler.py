"""Runs the pipeline repeatedly so the dashboard has enough runs to chart.

Usage (from pipelines/, venv active):
    python -m tools.scheduler --every 20 --count 30
"""
import argparse
import os
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="Run the pipeline on a fixed interval.")
    parser.add_argument("--every", type=float, default=30, help="seconds between run starts")
    parser.add_argument("--count", type=int, default=20, help="number of runs")
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    for i in range(args.count):
        started = time.time()
        result = subprocess.run([sys.executable, "-m", "pipeline.run_pipeline"], env=env)
        print(f"run {i + 1}/{args.count} finished with exit code {result.returncode}")
        if i < args.count - 1:
            time.sleep(max(0, args.every - (time.time() - started)))


if __name__ == "__main__":
    main()