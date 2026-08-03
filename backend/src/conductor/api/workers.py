"""HTTP contract used by local worker processes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from conductor.api.jobs import JobResponse
from conductor.domain.attempt import ExecutionAttempt
from conductor.domain.benchmark import BenchmarkSummary
from conductor.domain.model import ModelResidency, ResidencyStatus
from conductor.domain.worker import Worker, WorkerStatus
from conductor.services.workers import (
    BenchmarkCommand,
    RegisterWorkerCommand,
    WorkerService,
    WorkLease,
)

router = APIRouter(prefix="/workers", tags=["workers"])


class RegisterWorkerRequest(BaseModel):
    """The small, explicit capability declaration required in M3."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$")
    worker_instance_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$")
    supported_tasks: list[str] = Field(min_length=1, max_length=20)
    max_parallel_jobs: int = Field(default=1, ge=1, le=4)


class WorkerResponse(BaseModel):
    """Safe view of the currently registered worker process."""

    id: str
    instance_id: str
    supported_tasks: list[str]
    max_parallel_jobs: int
    status: WorkerStatus
    registered_at: datetime
    last_heartbeat_at: datetime
    version: int

    @classmethod
    def from_domain(cls, worker: Worker) -> "WorkerResponse":
        return cls(
            id=worker.id,
            instance_id=worker.instance_id,
            supported_tasks=sorted(worker.supported_tasks),
            max_parallel_jobs=worker.max_parallel_jobs,
            status=worker.status,
            registered_at=worker.registered_at,
            last_heartbeat_at=worker.last_heartbeat_at,
            version=worker.version,
        )


class AttemptResponse(BaseModel):
    """The leased execution identity that workers must echo in later requests."""

    id: str
    job_id: str
    ordinal: int
    status: str

    @classmethod
    def from_domain(cls, attempt: ExecutionAttempt) -> "AttemptResponse":
        return cls(
            id=attempt.id,
            job_id=attempt.job_id,
            ordinal=attempt.ordinal,
            status=attempt.status.value,
        )


class LeaseResponse(BaseModel):
    """One job reserved for the polling worker."""

    job: JobResponse
    attempt: AttemptResponse

    @classmethod
    def from_domain(cls, lease: WorkLease) -> "LeaseResponse":
        return cls(
            job=JobResponse.from_domain(lease.job),
            attempt=AttemptResponse.from_domain(lease.attempt),
        )


class ResidencyResponse(BaseModel):
    """Public snapshot of one model currently known to a worker process."""

    id: str
    model_id: str
    model_revision: int
    worker_id: str
    worker_instance_id: str
    status: ResidencyStatus
    active_execution_count: int
    measured_memory_bytes: int | None
    loaded_at: datetime | None
    last_used_at: datetime | None
    failure_message: str | None
    version: int

    @classmethod
    def from_domain(cls, residency: ModelResidency) -> "ResidencyResponse":
        return cls(
            id=residency.id,
            model_id=residency.model_id,
            model_revision=residency.model_revision,
            worker_id=residency.worker_id,
            worker_instance_id=residency.worker_instance_id,
            status=residency.status,
            active_execution_count=residency.active_execution_count,
            measured_memory_bytes=residency.measured_memory_bytes,
            loaded_at=residency.loaded_at,
            last_used_at=residency.last_used_at,
            failure_message=residency.failure_message,
            version=residency.version,
        )


class BenchmarkRequest(BaseModel):
    """Bounded request for a repeatable, warm-runtime benchmark."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1, max_length=100)
    task: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    input: dict[str, JsonValue] = Field(default_factory=dict)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    warmup_iterations: int = Field(default=1, ge=0, le=5)
    measurement_iterations: int = Field(default=3, ge=1, le=20)


class BenchmarkSummaryResponse(BaseModel):
    """Stable, persisted timing summary returned to an operator."""

    id: str
    model_id: str
    model_revision: int
    worker_id: str
    worker_instance_id: str
    task: str
    warmup_iterations: int
    measurement_iterations: int
    total_wall_time_ms: float
    mean_wall_time_ms: float
    min_wall_time_ms: float
    max_wall_time_ms: float
    mean_runtime_metrics: dict[str, float]
    created_at: datetime

    @classmethod
    def from_domain(cls, summary: BenchmarkSummary) -> "BenchmarkSummaryResponse":
        return cls(
            id=summary.id,
            model_id=summary.model_id,
            model_revision=summary.model_revision,
            worker_id=summary.worker_id,
            worker_instance_id=summary.worker_instance_id,
            task=summary.task,
            warmup_iterations=summary.warmup_iterations,
            measurement_iterations=summary.measurement_iterations,
            total_wall_time_ms=summary.total_wall_time_ms,
            mean_wall_time_ms=summary.mean_wall_time_ms,
            min_wall_time_ms=summary.min_wall_time_ms,
            max_wall_time_ms=summary.max_wall_time_ms,
            mean_runtime_metrics=dict(summary.mean_runtime_metrics),
            created_at=summary.created_at,
        )


def _service(request: Request) -> WorkerService:
    service: WorkerService = request.app.state.worker_service
    return service


@router.post("/register", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
def register_worker(payload: RegisterWorkerRequest, request: Request) -> WorkerResponse:
    worker = _service(request).register(
        RegisterWorkerCommand(
            worker_id=payload.worker_id,
            worker_instance_id=payload.worker_instance_id,
            supported_tasks=tuple(payload.supported_tasks),
            max_parallel_jobs=payload.max_parallel_jobs,
        )
    )
    return WorkerResponse.from_domain(worker)


@router.post("/{worker_id}/heartbeat", response_model=WorkerResponse)
def heartbeat_worker(
    worker_id: str,
    request: Request,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
) -> WorkerResponse:
    return WorkerResponse.from_domain(_service(request).heartbeat(worker_id, worker_instance_id))


@router.post("/{worker_id}/drain", response_model=WorkerResponse)
def drain_worker(
    worker_id: str,
    request: Request,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
) -> WorkerResponse:
    return WorkerResponse.from_domain(_service(request).drain(worker_id, worker_instance_id))


@router.post("/{worker_id}/leases/next", response_model=LeaseResponse | None)
def next_lease(
    worker_id: str,
    request: Request,
    response: Response,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
) -> LeaseResponse | None:
    lease = _service(request).next_lease(worker_id, worker_instance_id)
    if lease is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
    return LeaseResponse.from_domain(lease)


@router.post("/{worker_id}/attempts/{attempt_id}/start", response_model=AttemptResponse)
def start_attempt(
    worker_id: str,
    attempt_id: str,
    request: Request,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
) -> AttemptResponse:
    return AttemptResponse.from_domain(
        _service(request).start_attempt(worker_id, worker_instance_id, attempt_id)
    )


@router.post("/{worker_id}/attempts/{attempt_id}/complete", response_model=JobResponse)
def complete_attempt(
    worker_id: str,
    attempt_id: str,
    request: Request,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
) -> JobResponse:
    return JobResponse.from_domain(
        _service(request).complete_attempt(worker_id, worker_instance_id, attempt_id)
    )


@router.post("/{worker_id}/attempts/{attempt_id}/execute", response_model=JobResponse)
def execute_attempt(
    worker_id: str,
    attempt_id: str,
    request: Request,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
) -> JobResponse:
    """Run a leased job through its configured runtime and persist the result."""

    return JobResponse.from_domain(
        _service(request).execute_attempt(worker_id, worker_instance_id, attempt_id)
    )


@router.get("/{worker_id}/residencies", response_model=list[ResidencyResponse])
def list_residencies(
    worker_id: str,
    request: Request,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
) -> list[ResidencyResponse]:
    return [
        ResidencyResponse.from_domain(item)
        for item in _service(request).residencies(worker_id, worker_instance_id)
    ]


@router.post("/{worker_id}/evict-idle", response_model=list[ResidencyResponse])
def evict_idle(
    worker_id: str,
    request: Request,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
) -> list[ResidencyResponse]:
    return [
        ResidencyResponse.from_domain(item)
        for item in _service(request).evict_idle(worker_id, worker_instance_id)
    ]


@router.post("/{worker_id}/benchmarks", response_model=BenchmarkSummaryResponse)
def benchmark_runtime(
    worker_id: str,
    payload: BenchmarkRequest,
    request: Request,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
) -> BenchmarkSummaryResponse:
    """Measure one trusted model repeatedly on a current worker process."""

    summary = _service(request).benchmark(
        worker_id,
        worker_instance_id,
        BenchmarkCommand(
            model_id=payload.model_id,
            task=payload.task,
            input=dict(payload.input),
            parameters=dict(payload.parameters),
            warmup_iterations=payload.warmup_iterations,
            measurement_iterations=payload.measurement_iterations,
        ),
    )
    return BenchmarkSummaryResponse.from_domain(summary)


@router.get("/{worker_id}/benchmarks", response_model=list[BenchmarkSummaryResponse])
def list_benchmarks(
    worker_id: str,
    request: Request,
    worker_instance_id: Annotated[str, Header(alias="Worker-Instance-ID", min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[BenchmarkSummaryResponse]:
    return [
        BenchmarkSummaryResponse.from_domain(item)
        for item in _service(request).benchmarks(worker_id, worker_instance_id, limit)
    ]
