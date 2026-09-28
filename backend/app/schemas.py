import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class RunCreate(BaseModel):
    run_id: uuid.UUID
    pipeline: str
    started_at: datetime
    metadata: Optional[dict] = Field(default=None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)

class RunResponse(BaseModel):
    run_id: uuid.UUID
    status: str

    model_config = ConfigDict(from_attributes=True)

class StageCreate(BaseModel):
    stage: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    records_in: Optional[int] = None
    records_out: Optional[int] = None
    error_message: Optional[str] = None

class StageResponse(BaseModel):
    id: int
    run_id: uuid.UUID
    stage: str
    status: str

    model_config = ConfigDict(from_attributes=True)

class QualityMeasurementItem(BaseModel):
    metric: str
    value: float
    details: Optional[dict] = None

class QualityCreate(BaseModel):
    stage: str
    measurements: list[QualityMeasurementItem]

class QualityResponse(BaseModel):
    stage: str
    count: int

class EventCreate(BaseModel):
    level: str
    stage: Optional[str] = None
    message: str
    timestamp: datetime

class EventResponse(BaseModel):
    id: int
    level: str
    message: str

    model_config = ConfigDict(from_attributes=True)

class RunUpdate(BaseModel):
    status: str
    ended_at: Optional[datetime] = None
    records_in: Optional[int] = None
    records_out: Optional[int] = None

class InfraMetricCreate(BaseModel):
    host: str
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    run_id: Optional[uuid.UUID] = None

class InfraMetricResponse(BaseModel):
    id: int
    host: str

    model_config = ConfigDict(from_attributes=True)

class StageOut(BaseModel):
    stage: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    records_in: Optional[int] = None
    records_out: Optional[int] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class QualityOut(BaseModel):
    stage: str
    metric: str
    value: float
    details: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class EventOut(BaseModel):
    level: str
    stage: Optional[str] = None
    message: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class RunSummary(BaseModel):
    run_id: uuid.UUID
    pipeline: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    records_in: Optional[int] = None
    records_out: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RunDetail(BaseModel):
    run: RunSummary
    stages: list[StageOut]
    quality: list[QualityOut]
    events: list[EventOut]


class InfraMetricOut(BaseModel):
    host: str
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    run_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)

class AlertOut(BaseModel):
    id: int
    run_id: Optional[uuid.UUID] = None
    rule: str
    severity: str
    stage: Optional[str] = None
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)