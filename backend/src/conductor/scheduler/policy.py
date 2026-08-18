"""Deterministic, explainable placement policy for M4."""

from dataclasses import dataclass
from datetime import datetime

from conductor.domain.job import Job
from conductor.domain.resource import WorkerResourceSnapshot
from conductor.domain.worker import Worker, WorkerStatus

DEFAULT_MEMORY_SAFETY_RESERVE_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class WorkerSnapshot:
    """The small, immutable worker view used for one scheduling decision."""

    worker: Worker
    active_slots: int
    resource_snapshot: WorkerResourceSnapshot | None = None


@dataclass(frozen=True, slots=True)
class CandidateExplanation:
    """One worker's eligibility result, safe to show in an operator view."""

    worker_id: str
    eligible: bool
    reason: str
    active_slots: int
    max_parallel_jobs: int
    available_memory_bytes: int | None
    required_memory_bytes: int | None


@dataclass(frozen=True, slots=True)
class PlacementDecision:
    """The deterministic outcome of evaluating one queued job."""

    selected_worker_id: str | None
    reason: str
    candidates: tuple[CandidateExplanation, ...]


@dataclass(frozen=True, slots=True)
class RecordedSchedulingDecision:
    """A persisted placement explanation with operator-facing metadata."""

    id: str
    job_id: str
    selected_worker_id: str | None
    outcome: str
    reason: str
    candidates: tuple[CandidateExplanation, ...]
    created_at: datetime


class PlacementPolicy:
    """Prefer the least-busy eligible worker, then break ties by worker ID."""

    def __init__(
        self, memory_safety_reserve_bytes: int = DEFAULT_MEMORY_SAFETY_RESERVE_BYTES
    ) -> None:
        if memory_safety_reserve_bytes < 0:
            raise ValueError("memory_safety_reserve_bytes cannot be negative")
        self._memory_safety_reserve_bytes = memory_safety_reserve_bytes

    def decide(
        self,
        job: Job,
        snapshots: list[WorkerSnapshot],
        *,
        expected_memory_bytes: int | None = None,
    ) -> PlacementDecision:
        explanations: list[CandidateExplanation] = []
        eligible: list[WorkerSnapshot] = []

        # Sort first so that identical inputs always produce identical explanations.
        for snapshot in sorted(snapshots, key=lambda item: item.worker.id):
            worker = snapshot.worker
            reason = self._ineligibility_reason(job, snapshot, expected_memory_bytes)
            resource = snapshot.resource_snapshot
            explanations.append(
                CandidateExplanation(
                    worker_id=worker.id,
                    eligible=reason is None,
                    reason=reason or "eligible",
                    active_slots=snapshot.active_slots,
                    max_parallel_jobs=worker.max_parallel_jobs,
                    available_memory_bytes=(
                        resource.host_available_memory_bytes if resource is not None else None
                    ),
                    required_memory_bytes=expected_memory_bytes,
                )
            )
            if reason is None:
                eligible.append(snapshot)

        if not eligible:
            return PlacementDecision(
                selected_worker_id=None,
                reason="no_eligible_worker",
                candidates=tuple(explanations),
            )

        # Hard constraints ran above. Only now do we score eligible workers. The
        # worker ID is a stable tie-breaker when their load ratios are equal.
        selected = min(
            eligible,
            key=lambda item: (
                item.active_slots / item.worker.max_parallel_jobs,
                item.worker.id,
            ),
        )
        return PlacementDecision(
            selected_worker_id=selected.worker.id,
            reason="least_loaded_eligible_worker",
            candidates=tuple(explanations),
        )

    def _ineligibility_reason(
        self,
        job: Job,
        snapshot: WorkerSnapshot,
        expected_memory_bytes: int | None,
    ) -> str | None:
        worker = snapshot.worker
        if worker.status is not WorkerStatus.READY:
            return "worker_not_ready"
        if job.task not in worker.supported_tasks:
            return "task_not_supported"
        if snapshot.active_slots >= worker.max_parallel_jobs:
            # A full worker is healthy; it simply cannot accept one more lease now.
            return "no_free_slots"
        resource = snapshot.resource_snapshot
        # The reserve protects the operating system and unrelated local tools.
        # A model must fit in *headroom*, not merely in currently free memory.
        if (
            resource is not None
            and expected_memory_bytes is not None
            and resource.safe_memory_headroom_bytes(self._memory_safety_reserve_bytes)
            < expected_memory_bytes
        ):
            return "insufficient_memory_headroom"
        return None
