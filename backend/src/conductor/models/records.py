"""SQLModel records for durable job state."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class JobRecord(SQLModel, table=True):
    """Database representation of a job aggregate."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_jobs_idempotency_key"),
        Index("ix_jobs_status_created", "status", "created_at"),
    )

    id: str = Field(primary_key=True)
    idempotency_key: str
    request_hash: str
    task: str
    model_id: str
    input_payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    parameters: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    priority: str
    max_attempts: int
    status: str
    active_attempt_id: str | None = Field(default=None, foreign_key="attempts.id")
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    version: int


class AttemptRecord(SQLModel, table=True):
    """Database representation of one execution attempt."""

    __tablename__ = "attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "ordinal", name="uq_attempts_job_ordinal"),
        Index("ix_attempts_job_id", "job_id"),
    )

    id: str = Field(primary_key=True)
    job_id: str = Field(foreign_key="jobs.id")
    ordinal: int
    worker_id: str
    worker_instance_id: str
    status: str
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    version: int


class WorkerRecord(SQLModel, table=True):
    """Durable registration for one logical worker's current process."""

    __tablename__ = "workers"
    __table_args__ = (Index("ix_workers_status", "status"),)

    id: str = Field(primary_key=True)
    instance_id: str
    supported_tasks: list[str] = Field(sa_column=Column(JSON, nullable=False))
    max_parallel_jobs: int
    status: str
    registered_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    last_heartbeat_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    version: int


class SchedulingDecisionRecord(SQLModel, table=True):
    """Immutable explanation for one job-placement evaluation."""

    __tablename__ = "scheduling_decisions"
    __table_args__ = (Index("ix_scheduling_decisions_job_created", "job_id", "created_at"),)

    id: str = Field(primary_key=True)
    job_id: str = Field(foreign_key="jobs.id")
    selected_worker_id: str | None = Field(default=None)
    outcome: str
    reason: str
    candidates: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
