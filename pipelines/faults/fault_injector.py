"""
Fault injection scripts (Section 5.4). Each scenario runs the real
pipeline but corrupts something first, and tags the run with
metadata.fault_type / metadata.fault_injected_at so the backend can
compute detection latency.

Every injected fault is also appended to faults/injected_faults.log so
Owner A can compute alert precision/recall against a ground truth list.

Run one scenario:
    python -m faults.fault_injector null_spike
    python -m faults.fault_injector dropped_column
    python -m faults.fault_injector delayed_source
    python -m faults.fault_injector stage_crash

Run all four back to back:
    python -m faults.fault_injector all
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from pipeline import config, stages
from pipeline.run_pipeline import run_once
from reporter.reporter import MonitorReporter

LOG_PATH = Path(__file__).parent / "injected_faults.log"


def _log_fault(fault_type: str, injected_at: str, run_id: str):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"fault_type": fault_type, "injected_at": injected_at, "run_id": run_id}) + "\n")


def _fault_metadata(fault_type: str) -> dict:
    return {
        "fault_type": fault_type,
        "fault_injected_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }


def scenario_dropped_column(reporter: MonitorReporter) -> str:
    """Removes a required column from the source data before ingestion.
    Expected: schema_consistency measurement = 0."""
    metadata = _fault_metadata("dropped_column")
    original_ingestion = stages.run_ingestion

    def broken_ingestion(source_kind, source_path):
        df = original_ingestion(source_kind, source_path)
        return df.drop(columns=["price"], errors="ignore")

    with mock.patch("pipeline.stages.run_ingestion", side_effect=broken_ingestion):
        run_id = run_once(reporter, fault_metadata=metadata)
    _log_fault("dropped_column", metadata["fault_injected_at"], run_id)
    return run_id


def scenario_delayed_source(reporter: MonitorReporter, delay_seconds: float = 5.0) -> str:
    """Adds latency in ingestion. Expected: long ingestion stage
    duration and a high 'timeliness' quality value."""
    metadata = _fault_metadata("delayed_source")
    original_ingestion = stages.run_ingestion

    def slow_ingestion(source_kind, source_path):
        time.sleep(delay_seconds)
        return original_ingestion(source_kind, source_path)

    with mock.patch("pipeline.stages.run_ingestion", side_effect=slow_ingestion):
        run_id = run_once(reporter, fault_metadata=metadata)
    _log_fault("delayed_source", metadata["fault_injected_at"], run_id)
    return run_id


def scenario_null_spike(reporter: MonitorReporter, null_fraction: float = 0.5) -> str:
    """Blanks out a large share of one column. Expected: low
    'completeness' quality value."""
    metadata = _fault_metadata("null_spike")
    original_transformation = stages.run_transformation

    def dirty_transformation(df):
        df = df.copy()
        n = int(len(df) * null_fraction)
        if n > 0 and "product" in df.columns:
            idx = df.sample(n=n, random_state=1).index
            df.loc[idx, "product"] = None
        return original_transformation(df)

    with mock.patch("pipeline.stages.run_transformation", side_effect=dirty_transformation):
        run_id = run_once(reporter, fault_metadata=metadata)
    _log_fault("null_spike", metadata["fault_injected_at"], run_id)
    return run_id


def scenario_stage_crash(reporter: MonitorReporter, stage: str = "storage") -> str:
    """Forces an exception inside a chosen stage. Expected: that
    stage reports status='failed' with an error_message."""
    metadata = _fault_metadata("stage_crash")

    def crashing_stage(*args, **kwargs):
        raise RuntimeError(f"Injected fault: forced crash in {stage} stage")

    target = {
        "ingestion": "pipeline.stages.run_ingestion",
        "transformation": "pipeline.stages.run_transformation",
        "validation": "pipeline.stages.run_validation",
        "storage": "pipeline.stages.run_storage",
    }[stage]

    with mock.patch(target, side_effect=crashing_stage):
        run_id = run_once(reporter, fault_metadata=metadata)
    _log_fault("stage_crash", metadata["fault_injected_at"], run_id)
    return run_id


SCENARIOS = {
    "dropped_column": scenario_dropped_column,
    "delayed_source": scenario_delayed_source,
    "null_spike": scenario_null_spike,
    "stage_crash": scenario_stage_crash,
}


def main():
    parser = argparse.ArgumentParser(description="Run a fault injection scenario against the real pipeline.")
    parser.add_argument("scenario", choices=[*SCENARIOS.keys(), "all"])
    args = parser.parse_args()

    reporter = MonitorReporter(
        base_url=config.MONITOR_API_URL,
        api_key=config.MONITOR_API_KEY,
        enabled=config.MONITORING_ENABLED,
    )

    if args.scenario == "all":
        for name, fn in SCENARIOS.items():
            print(f"--- running {name} ---")
            fn(reporter)
    else:
        SCENARIOS[args.scenario](reporter)


if __name__ == "__main__":
    main()
