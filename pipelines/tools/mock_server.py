"""
Mock API server — implements the six endpoints in Section 4 of the
contract so the reporter client (and the pipeline) can be built and
tested before Owner A's real backend exists.

It does NOT persist anything meaningfully; it validates shape, prints
what it receives, and returns realistic status codes (2xx / 422) so
the reporter's retry-vs-no-retry logic can be exercised against it.

Run:
    uvicorn tools.mock_server:app --port 8001 --reload
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

app = FastAPI(title="Mock Monitoring API (local dev only)")

# In-memory store, just so repeated/duplicate calls behave sensibly.
RUNS: dict[str, dict[str, Any]] = {}

VALID_RUN_STATUS = {"running", "success", "failed"}
VALID_STAGE_STATUS = {"running", "success", "failed", "skipped"}
VALID_STAGES = {"ingestion", "transformation", "validation", "storage"}
VALID_LOG_LEVELS = {"info", "warning", "error"}


def _check_api_key(x_api_key: Optional[str]):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")


class StartRunRequest(BaseModel):
    run_id: str
    pipeline: str
    started_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class StageRequest(BaseModel):
    stage: str
    status: str
    started_at: str
    ended_at: str
    records_in: Optional[int] = None
    records_out: Optional[int] = None
    error_message: Optional[str] = None


class QualityMeasurement(BaseModel):
    metric: str
    value: float
    details: Optional[dict[str, Any]] = None


class QualityRequest(BaseModel):
    stage: str
    measurements: list[QualityMeasurement]


class EventRequest(BaseModel):
    level: str
    stage: str
    message: str
    timestamp: str


class FinishRunRequest(BaseModel):
    status: str
    ended_at: str
    records_in: Optional[int] = None
    records_out: Optional[int] = None


class InfraMetricsRequest(BaseModel):
    host: str
    timestamp: str
    cpu_percent: float
    memory_percent: float
    run_id: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/api/v1/runs")
def start_run(body: StartRunRequest, x_api_key: Optional[str] = Header(None)):
    _check_api_key(x_api_key)

    if body.run_id in RUNS:
        print(f"[mock] duplicate start_run for {body.run_id} — returning existing run")
        return RUNS[body.run_id]

    if not body.pipeline:
        raise HTTPException(status_code=422, detail="pipeline is required")

    run = {
        "run_id": body.run_id,
        "pipeline": body.pipeline,
        "status": "running",
        "started_at": body.started_at,
        "ended_at": None,
        "metadata": body.metadata,
        "stages": {},
        "quality": [],
        "events": [],
    }
    RUNS[body.run_id] = run
    print(f"[mock] run started: {body.run_id} ({body.pipeline})")
    return run


@app.post("/api/v1/runs/{run_id}/stages")
def report_stage(run_id: str, body: StageRequest, x_api_key: Optional[str] = Header(None)):
    _check_api_key(x_api_key)
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=422, detail=f"unknown run_id {run_id}")
    if body.stage not in VALID_STAGES or body.status not in VALID_STAGE_STATUS:
        raise HTTPException(status_code=422, detail="invalid stage or status value")

    run["stages"][body.stage] = body.model_dump()  # repeated report updates it
    print(f"[mock] stage report {run_id}/{body.stage}: {body.status}")
    return {"ok": True}


@app.post("/api/v1/runs/{run_id}/quality")
def report_quality(run_id: str, body: QualityRequest, x_api_key: Optional[str] = Header(None)):
    _check_api_key(x_api_key)
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=422, detail=f"unknown run_id {run_id}")

    run["quality"].append(body.model_dump())
    print(f"[mock] quality report {run_id}/{body.stage}: {[m['metric'] for m in body.model_dump()['measurements']]}")
    return {"ok": True}


@app.post("/api/v1/runs/{run_id}/events")
def log_event(run_id: str, body: EventRequest, x_api_key: Optional[str] = Header(None)):
    _check_api_key(x_api_key)
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=422, detail=f"unknown run_id {run_id}")
    if body.level not in VALID_LOG_LEVELS:
        raise HTTPException(status_code=422, detail="invalid log level")

    run["events"].append(body.model_dump())
    print(f"[mock] event {run_id} [{body.level}] {body.stage}: {body.message}")
    return {"ok": True}


@app.patch("/api/v1/runs/{run_id}")
def finish_run(run_id: str, body: FinishRunRequest, x_api_key: Optional[str] = Header(None)):
    _check_api_key(x_api_key)
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=422, detail=f"unknown run_id {run_id}")
    if body.status not in VALID_RUN_STATUS:
        raise HTTPException(status_code=422, detail="invalid run status")

    run["status"] = body.status
    run["ended_at"] = body.ended_at
    run["records_in"] = body.records_in
    run["records_out"] = body.records_out
    print(f"[mock] run finished {run_id}: {body.status}")
    return run


@app.post("/api/v1/metrics/infra")
def infra_metrics(body: InfraMetricsRequest, x_api_key: Optional[str] = Header(None)):
    _check_api_key(x_api_key)
    print(f"[mock] infra metrics {body.host}: cpu={body.cpu_percent}% mem={body.memory_percent}%")
    return {"ok": True}


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str):
    """Not in the contract, but handy for manually inspecting a run
    while testing (e.g. curl http://localhost:8001/api/v1/runs/<id>)."""
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="not found")
    return run
