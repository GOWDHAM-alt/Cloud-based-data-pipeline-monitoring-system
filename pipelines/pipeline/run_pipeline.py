"""
Orchestrates one full pipeline run: start_run -> ingestion ->
transformation -> validation (+ quality) -> storage -> finish_run.

Run directly:
    python -m pipeline.run_pipeline
    python -m pipeline.run_pipeline --fault null_spike   # see faults/
"""

from __future__ import annotations

import argparse
import logging
import time

from pipeline import config, stages
from pipeline.instrumentation import instrumented_stage
from pipeline.quality import build_measurements
from reporter.reporter import MonitorReporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pipeline")


def run_once(reporter: MonitorReporter, fault_metadata: dict | None = None) -> str:
    metadata = {"trigger": "manual"}
    if fault_metadata:
        metadata.update(fault_metadata)

    run_id = reporter.start_run(pipeline=config.PIPELINE_NAME, metadata=metadata)
    logger.info("Started run %s", run_id)

    overall_status = "success"
    total_in = total_out = 0

    try:
        # --- ingestion ---
        with instrumented_stage(reporter, run_id, "ingestion") as ctx:
            df_raw = stages.run_ingestion(config.PIPELINE_DATA_SOURCE, config.PIPELINE_SOURCE_PATH)
            ctx.records_in = len(df_raw)
            ctx.records_out = len(df_raw)
            ctx.result = df_raw
        total_in = len(df_raw)

        # --- transformation ---
        with instrumented_stage(reporter, run_id, "transformation") as ctx:
            ctx.records_in = len(df_raw)
            df_clean = stages.run_transformation(df_raw)
            ctx.records_out = len(df_clean)
            ctx.result = df_clean

        # --- validation (+ quality measurements) ---
        with instrumented_stage(reporter, run_id, "validation") as ctx:
            ctx.records_in = len(df_clean)
            df_validated, valid_mask = stages.run_validation(df_clean)
            ctx.records_out = int(valid_mask.sum())
            ctx.result = (df_validated, valid_mask)

        measurements = build_measurements(
            df=df_validated,
            expected_columns=stages.EXPECTED_COLUMNS + ["order_total"],
            key_column="order_id",
            valid_mask=valid_mask,
            latest_event_epoch_seconds=time.time(),
        )
        reporter.report_quality(run_id, stage="validation", measurements=measurements)

        df_valid_only = df_validated[valid_mask]

        # --- storage ---
        with instrumented_stage(reporter, run_id, "storage") as ctx:
            ctx.records_in = len(df_valid_only)
            written = stages.run_storage(df_valid_only, db_path="data/warehouse.db")
            ctx.records_out = written
        total_out = written

    except Exception as exc:
        overall_status = "failed"
        logger.error("Run %s failed: %s", run_id, exc)
    finally:
        reporter.finish_run(run_id, status=overall_status, records_in=total_in, records_out=total_out)
        logger.info("Finished run %s: %s (in=%s out=%s)", run_id, overall_status, total_in, total_out)

    return run_id


def main():
    parser = argparse.ArgumentParser(description="Run the sales_daily pipeline once.")
    parser.add_argument("--fault", choices=["null_spike", "dropped_column", "delayed_source", "stage_crash"], default=None)
    args = parser.parse_args()

    reporter = MonitorReporter(
        base_url=config.MONITOR_API_URL,
        api_key=config.MONITOR_API_KEY,
        enabled=config.MONITORING_ENABLED,
    )

    fault_metadata = None
    if args.fault:
        # actual fault application happens in faults/fault_injector.py,
        # which monkeypatches stages before calling run_once(). Here we
        # just make sure the marker ends up on the run for convenience
        # when running this file directly with --fault for a dry run.
        from datetime import datetime, timezone
        fault_metadata = {
            "fault_type": args.fault,
            "fault_injected_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }

    run_once(reporter, fault_metadata=fault_metadata)


if __name__ == "__main__":
    main()
