import os
from sqlalchemy.orm import Session

from . import models

STAGE_DURATION_MAX = float(os.getenv("STAGE_DURATION_MAX_SECONDS", "120"))
COMPLETENESS_MIN = float(os.getenv("COMPLETENESS_MIN", "0.95"))
RECORD_CHANGE_MAX = float(os.getenv("RECORD_COUNT_CHANGE_MAX", "0.2"))
REPEATED_FAILURES = int(os.getenv("REPEATED_FAILURE_COUNT", "3"))
CPU_MAX = float(os.getenv("CPU_PERCENT_MAX", "90"))
MEMORY_MAX = float(os.getenv("MEMORY_PERCENT_MAX", "90"))


def _raise(db: Session, run_id, rule, severity, message, stage=None):
    exists = (
        db.query(models.Alert)
        .filter(
            models.Alert.run_id == run_id,
            models.Alert.rule == rule,
            models.Alert.stage == stage,
        )
        .first()
    )
    if exists:
        return
    db.add(
        models.Alert(
            run_id=run_id, rule=rule, severity=severity, stage=stage, message=message
        )
    )
    db.flush()


def evaluate_run(db: Session, run_id):
    run = db.get(models.Run, run_id)
    if not run:
        return

    stages = db.query(models.Stage).filter(models.Stage.run_id == run_id).all()

    for s in stages:
        if s.status == "failed":
            _raise(db, run_id, "stage_failure", "high",
                   f"Stage '{s.stage}' failed: {s.error_message or 'no error message'}", s.stage)

            recent = (
                db.query(models.Stage.status)
                .join(models.Run, models.Run.run_id == models.Stage.run_id)
                .filter(
                    models.Run.pipeline == run.pipeline,
                    models.Stage.stage == s.stage,
                    models.Run.started_at <= run.started_at,
                )
                .order_by(models.Run.started_at.desc())
                .limit(REPEATED_FAILURES)
                .all()
            )
            if len(recent) == REPEATED_FAILURES and all(r[0] == "failed" for r in recent):
                _raise(db, run_id, "repeated_failure", "high",
                       f"Stage '{s.stage}' failed in the last {REPEATED_FAILURES} runs", s.stage)

        if s.started_at and s.ended_at:
            duration = (s.ended_at - s.started_at).total_seconds()
            if duration > STAGE_DURATION_MAX:
                _raise(db, run_id, "slow_stage", "medium",
                       f"Stage '{s.stage}' took {duration:.0f}s (limit {STAGE_DURATION_MAX:.0f}s)", s.stage)

        if s.status == "success" and s.records_out == 0:
            _raise(db, run_id, "missing_output", "high",
                   f"Stage '{s.stage}' succeeded but produced no records", s.stage)

    for q in db.query(models.QualityMeasurement).filter(models.QualityMeasurement.run_id == run_id):
        value = float(q.value)
        if q.metric == "schema_consistency" and value == 0:
            _raise(db, run_id, "schema_mismatch", "high",
                   f"Schema mismatch detected in stage '{q.stage}'", q.stage)
        if q.metric == "completeness" and value < COMPLETENESS_MIN:
            _raise(db, run_id, "low_completeness", "medium",
                   f"Completeness {value:.3f} is below {COMPLETENESS_MIN}", q.stage)

    if run.status == "success" and run.records_out is not None:
        if run.records_out == 0:
            _raise(db, run_id, "missing_output", "high", "Run succeeded but produced no records")
        else:
            previous = (
                db.query(models.Run.records_out)
                .filter(
                    models.Run.pipeline == run.pipeline,
                    models.Run.status == "success",
                    models.Run.records_out.isnot(None),
                    models.Run.started_at < run.started_at,
                )
                .order_by(models.Run.started_at.desc())
                .limit(5)
                .all()
            )
            values = [p[0] for p in previous]
            if len(values) >= 3:
                avg = sum(values) / len(values)
                if avg > 0 and abs(run.records_out - avg) / avg > RECORD_CHANGE_MAX:
                    _raise(db, run_id, "record_count_change", "medium",
                           f"Output of {run.records_out} records differs from recent average of {avg:.0f}")

    for m in db.query(models.InfraMetric).filter(models.InfraMetric.run_id == run_id):
        if float(m.cpu_percent) > CPU_MAX:
            _raise(db, run_id, "high_cpu", "medium",
                   f"CPU at {m.cpu_percent}% on {m.host} (limit {CPU_MAX:.0f}%)")
        if float(m.memory_percent) > MEMORY_MAX:
            _raise(db, run_id, "high_memory", "medium",
                   f"Memory at {m.memory_percent}% on {m.host} (limit {MEMORY_MAX:.0f}%)")