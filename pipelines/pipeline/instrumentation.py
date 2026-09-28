"""
instrumented_stage() wraps a single pipeline stage so it always reports
its outcome to the backend, whether it succeeds or raises. The stage's
real behavior (including exceptions propagating to the caller) is
never changed by monitoring — this is the core design rule in Section
5.1 of the contract.

Usage:
    with instrumented_stage(reporter, run_id, "ingestion") as ctx:
        df = read_source(...)
        ctx.records_out = len(df)
        ctx.result = df
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

from reporter.reporter import MonitorReporter, now_iso


@dataclass
class StageContext:
    records_in: Optional[int] = None
    records_out: Optional[int] = None
    result: Any = None
    extra_metadata: dict = field(default_factory=dict)


@contextmanager
def instrumented_stage(reporter: MonitorReporter, run_id: str, stage: str):
    ctx = StageContext()
    started_at = now_iso()
    t0 = time.time()
    try:
        yield ctx
    except Exception as exc:
        ended_at = now_iso()
        reporter.report_stage(
            run_id=run_id,
            stage=stage,
            status="failed",
            started_at=started_at,
            ended_at=ended_at,
            records_in=ctx.records_in,
            records_out=ctx.records_out,
            error_message=str(exc),
        )
        reporter.log_event(
            run_id=run_id,
            level="error",
            stage=stage,
            message=f"{stage} failed after {time.time() - t0:.2f}s: {exc}",
        )
        raise  # the pipeline must still behave as if monitoring weren't there
    else:
        ended_at = now_iso()
        reporter.report_stage(
            run_id=run_id,
            stage=stage,
            status="success",
            started_at=started_at,
            ended_at=ended_at,
            records_in=ctx.records_in,
            records_out=ctx.records_out,
        )
