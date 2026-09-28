import uuid
from sqlalchemy import Column, String, DateTime, Integer, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from .database import Base
from datetime import datetime, timezone

class Run(Base):
    __tablename__ = "runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline = Column(String, nullable=False)
    status = Column(String, nullable=False, default="running")
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    records_in = Column(Integer, nullable=True)
    records_out = Column(Integer, nullable=True)
    run_metadata = Column(JSON, nullable=True)

class Stage(Base):
    __tablename__ = "stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=False)
    stage = Column(String, nullable=False)
    status = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    records_in = Column(Integer, nullable=True)
    records_out = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)

class QualityMeasurement(Base):
    __tablename__ = "quality_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=False)
    stage = Column(String, nullable=False)
    metric = Column(String, nullable=False)
    value = Column(String, nullable=False)  # stored as string to allow numbers or flags uniformly
    details = Column(JSON, nullable=True)

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=False)
    level = Column(String, nullable=False)
    stage = Column(String, nullable=True)
    message = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)

class InfraMetric(Base):
    __tablename__ = "infra_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    host = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    cpu_percent = Column(String, nullable=False)
    memory_percent = Column(String, nullable=False)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=True)

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=True)
    rule = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    stage = Column(String, nullable=True)
    message = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )