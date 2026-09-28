"""
Metrics agent — runs as its own process, independent of any single
pipeline run, and reports host CPU/memory to /api/v1/metrics/infra on
a fixed interval (Section 5.3 of the contract).

Run:
    python -m agent.metrics_agent
    (stop with Ctrl+C, or SIGTERM in a container)
"""

from __future__ import annotations

import logging
import signal
import sys
import time

import psutil

from pipeline import config
from reporter.reporter import MonitorReporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("metrics_agent")

_running = True


def _handle_stop(signum, frame):
    global _running
    logger.info("Received signal %s, stopping after current sample", signum)
    _running = False


def sample_once(reporter: MonitorReporter, host: str) -> tuple[float, float]:
    """Reads current CPU and memory usage and reports them. Returns the
    values so callers (e.g. the overhead test) can log them independently."""
    cpu_percent = psutil.cpu_percent(interval=1)  # 1s sample window
    memory_percent = psutil.virtual_memory().percent

    try:
        reporter.report_infra_metrics(host=host, cpu_percent=cpu_percent, memory_percent=memory_percent)
    except Exception as exc:  # extra belt-and-suspenders; reporter already catches internally
        logger.warning("Failed to report infra metrics (ignored): %s", exc)

    logger.info("cpu=%.1f%% mem=%.1f%%", cpu_percent, memory_percent)
    return cpu_percent, memory_percent


def main():
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    reporter = MonitorReporter(
        base_url=config.MONITOR_API_URL,
        api_key=config.MONITOR_API_KEY,
        enabled=config.MONITORING_ENABLED,
    )
    interval = config.METRICS_INTERVAL_SECONDS
    host = config.METRICS_HOST_NAME

    logger.info(
        "Metrics agent starting: interval=%ss host=%s monitoring_enabled=%s",
        interval, host, config.MONITORING_ENABLED,
    )

    while _running:
        loop_start = time.time()
        sample_once(reporter, host)
        elapsed = time.time() - loop_start
        sleep_for = max(0.0, interval - elapsed)
        time.sleep(sleep_for)

    logger.info("Metrics agent stopped")
    sys.exit(0)


if __name__ == "__main__":
    main()
