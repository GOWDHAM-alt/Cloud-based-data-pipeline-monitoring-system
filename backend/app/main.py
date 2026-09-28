import uuid
import os
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models, schemas
from .database import get_db, init_db
from .auth import verify_api_key
from .rules import evaluate_run, evaluate_metric

app = FastAPI(title="Pipeline Monitoring API")

origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/runs", response_model=schemas.RunResponse, status_code=201, dependencies=[Depends(verify_api_key)])
def create_run(run: schemas.RunCreate, db: Session = Depends(get_db)):
    existing = db.get(models.Run, run.run_id)
    if existing:
        return existing

    db_run = models.Run(
        run_id=run.run_id,
        pipeline=run.pipeline,
        status="running",
        started_at=run.started_at,
        run_metadata=run.metadata,
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run


@app.post("/api/v1/runs/{run_id}/stages", response_model=schemas.StageResponse, status_code=201, dependencies=[Depends(verify_api_key)])
def report_stage(run_id: uuid.UUID, stage: schemas.StageCreate, db: Session = Depends(get_db)):
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    db_stage = (
        db.query(models.Stage)
        .filter(models.Stage.run_id == run_id, models.Stage.stage == stage.stage)
        .first()
    )
    if db_stage:
        for field, value in stage.model_dump(exclude_unset=True).items():
            setattr(db_stage, field, value)
    else:
        db_stage = models.Stage(run_id=run_id, **stage.model_dump())
        db.add(db_stage)

    db.commit()
    evaluate_run(db, run_id)
    db.commit()
    db.refresh(db_stage)
    return db_stage


@app.post("/api/v1/runs/{run_id}/quality", response_model=schemas.QualityResponse, status_code=201, dependencies=[Depends(verify_api_key)])
def report_quality(run_id: uuid.UUID, payload: schemas.QualityCreate, db: Session = Depends(get_db)):
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    for m in payload.measurements:
        db_measurement = models.QualityMeasurement(
            run_id=run_id,
            stage=payload.stage,
            metric=m.metric,
            value=str(m.value),
            details=m.details,
        )
        db.add(db_measurement)

    db.commit()
    evaluate_run(db, run_id)
    db.commit()
    return {"stage": payload.stage, "count": len(payload.measurements)}


@app.post("/api/v1/runs/{run_id}/events", response_model=schemas.EventResponse, status_code=201, dependencies=[Depends(verify_api_key)])
def log_event(run_id: uuid.UUID, event: schemas.EventCreate, db: Session = Depends(get_db)):
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    db_event = models.Event(run_id=run_id, **event.model_dump())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@app.patch("/api/v1/runs/{run_id}", response_model=schemas.RunResponse, dependencies=[Depends(verify_api_key)])
def finish_run(run_id: uuid.UUID, update: schemas.RunUpdate, db: Session = Depends(get_db)):
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(run, field, value)

    db.commit()
    evaluate_run(db, run_id)
    db.commit()
    db.refresh(run)
    return run


@app.post("/api/v1/metrics/infra", response_model=schemas.InfraMetricResponse, status_code=201, dependencies=[Depends(verify_api_key)])
def report_infra_metric(metric: schemas.InfraMetricCreate, db: Session = Depends(get_db)):
    db_metric = models.InfraMetric(
        host=metric.host,
        timestamp=metric.timestamp,
        cpu_percent=str(metric.cpu_percent),
        memory_percent=str(metric.memory_percent),
        run_id=metric.run_id,
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    evaluate_metric(db, db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

@app.get("/api/v1/runs", response_model=list[schemas.RunSummary])
def list_runs(
    limit: int = 50,
    status: Optional[str] = None,
    pipeline: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Run)
    if status:
        q = q.filter(models.Run.status == status)
    if pipeline:
        q = q.filter(models.Run.pipeline == pipeline)
    return q.order_by(models.Run.started_at.desc()).limit(limit).all()


@app.get("/api/v1/runs/{run_id}", response_model=schemas.RunDetail)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    stages = (
        db.query(models.Stage)
        .filter(models.Stage.run_id == run_id)
        .order_by(models.Stage.started_at)
        .all()
    )
    quality = db.query(models.QualityMeasurement).filter(models.QualityMeasurement.run_id == run_id).all()
    events = (
        db.query(models.Event)
        .filter(models.Event.run_id == run_id)
        .order_by(models.Event.timestamp)
        .all()
    )
    return {"run": run, "stages": stages, "quality": quality, "events": events}


@app.get("/api/v1/summary")
def get_summary(db: Session = Depends(get_db)):
    rows = db.query(models.Run.status, func.count()).group_by(models.Run.status).all()
    counts = {status: n for status, n in rows}
    return {
        "total_runs": sum(counts.values()),
        "success": counts.get("success", 0),
        "failed": counts.get("failed", 0),
        "running": counts.get("running", 0),
    }


@app.get("/api/v1/metrics/infra", response_model=list[schemas.InfraMetricOut])
def list_infra_metrics(limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(models.InfraMetric)
        .order_by(models.InfraMetric.timestamp.desc())
        .limit(limit)
        .all()
    )

@app.get("/api/v1/alerts", response_model=list[schemas.AlertOut])
def list_alerts(limit: int = 50, run_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)):
    q = db.query(models.Alert)
    if run_id:
        q = q.filter(models.Alert.run_id == run_id)
    return q.order_by(models.Alert.created_at.desc()).limit(limit).all()


@app.post("/api/v1/alerts/reevaluate", dependencies=[Depends(verify_api_key)])
def reevaluate_all(db: Session = Depends(get_db)):
    runs = db.query(models.Run).order_by(models.Run.started_at).all()
    for r in runs:
        evaluate_run(db, r.run_id)
    db.commit()
    return {"runs_evaluated": len(runs), "alerts": db.query(models.Alert).count()}