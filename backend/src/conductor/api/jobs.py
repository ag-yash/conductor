"""HTTP contract for durable job operations."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from conductor.domain.job import Job, JobPriority, JobStatus
from conductor.services.jobs import JobService, SubmitJobCommand
from conductor.services.workers import WorkerService

router = APIRouter(prefix="/jobs", tags=["jobs"])


class SubmitJobRequest(BaseModel):
    """Bounded runtime-neutral job submission."""

    model_config = ConfigDict(extra="forbid")

    task: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    model_id: str = Field(min_length=1, max_length=200)
    input: dict[str, JsonValue] = Field(default_factory=dict)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    priority: JobPriority = JobPriority.NORMAL
    max_attempts: int = Field(default=3, ge=1, le=10)


class JobResponse(BaseModel):
    """Public representation of a durable job."""

    id: str
    task: str
    model_id: str
    input: dict[str, Any]
    parameters: dict[str, Any]
    priority: JobPriority
    max_attempts: int
    status: JobStatus
    active_attempt_id: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def from_domain(cls, job: Job) -> "JobResponse":
        return cls(
            id=job.id,
            task=job.task,
            model_id=job.model_id,
            input=dict(job.input),
            parameters=dict(job.parameters),
            priority=job.priority,
            max_attempts=job.max_attempts,
            status=job.status,
            active_attempt_id=job.active_attempt_id,
            created_at=job.created_at,
            updated_at=job.updated_at,
            version=job.version,
        )


class JobListResponse(BaseModel):
    """A bounded page of jobs."""

    items: list[JobResponse]
    limit: int
    offset: int


class CandidateExplanationResponse(BaseModel):
    """One human-readable reason a worker was or was not eligible."""

    worker_id: str
    eligible: bool
    reason: str
    active_slots: int
    max_parallel_jobs: int


class SchedulingDecisionResponse(BaseModel):
    """An immutable explanation of one scheduling evaluation."""

    id: str
    selected_worker_id: str | None
    outcome: str
    reason: str
    candidates: list[CandidateExplanationResponse]
    created_at: datetime


def _service(request: Request) -> JobService:
    service: JobService = request.app.state.job_service
    return service


def _worker_service(request: Request) -> WorkerService:
    service: WorkerService = request.app.state.worker_service
    return service


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def submit_job(
    payload: SubmitJobRequest,
    response: Response,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9._-]+$",
        ),
    ],
) -> JobResponse:
    result = _service(request).submit(
        SubmitJobCommand(
            idempotency_key=idempotency_key,
            task=payload.task,
            model_id=payload.model_id,
            input=payload.input,
            parameters=payload.parameters,
            priority=payload.priority,
            max_attempts=payload.max_attempts,
        )
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return JobResponse.from_domain(result.job)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, request: Request) -> JobResponse:
    return JobResponse.from_domain(_service(request).get(job_id))


@router.get("/{job_id}/scheduling-decisions", response_model=list[SchedulingDecisionResponse])
def list_scheduling_decisions(job_id: str, request: Request) -> list[SchedulingDecisionResponse]:
    decisions = _worker_service(request).decisions_for_job(job_id)
    return [
        SchedulingDecisionResponse(
            id=decision.id,
            selected_worker_id=decision.selected_worker_id,
            outcome=decision.outcome,
            reason=decision.reason,
            candidates=[
                CandidateExplanationResponse(
                    worker_id=candidate.worker_id,
                    eligible=candidate.eligible,
                    reason=candidate.reason,
                    active_slots=candidate.active_slots,
                    max_parallel_jobs=candidate.max_parallel_jobs,
                )
                for candidate in decision.candidates
            ],
            created_at=decision.created_at,
        )
        for decision in decisions
    ]


@router.get("", response_model=JobListResponse)
def list_jobs(
    request: Request,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobListResponse:
    jobs = _service(request).list(status=job_status, limit=limit, offset=offset)
    return JobListResponse(
        items=[JobResponse.from_domain(job) for job in jobs],
        limit=limit,
        offset=offset,
    )


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, request: Request) -> JobResponse:
    return JobResponse.from_domain(_service(request).cancel(job_id))
