"""Durable, comparable summaries of repeated runtime execution."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Self

from conductor.domain.job import utc_now


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    """One completed benchmark for one model on one worker process."""

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
    mean_runtime_metrics: Mapping[str, float]
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        benchmark_id: str,
        model_id: str,
        model_revision: int,
        worker_id: str,
        worker_instance_id: str,
        task: str,
        warmup_iterations: int,
        samples_ms: tuple[float, ...],
        mean_runtime_metrics: Mapping[str, float],
        now: datetime | None = None,
    ) -> Self:
        """Create a summary after at least one measured invocation completes."""

        if not samples_ms:
            raise ValueError("a benchmark requires at least one measured invocation")
        return cls(
            id=benchmark_id,
            model_id=model_id,
            model_revision=model_revision,
            worker_id=worker_id,
            worker_instance_id=worker_instance_id,
            task=task,
            warmup_iterations=warmup_iterations,
            measurement_iterations=len(samples_ms),
            total_wall_time_ms=sum(samples_ms),
            mean_wall_time_ms=sum(samples_ms) / len(samples_ms),
            min_wall_time_ms=min(samples_ms),
            max_wall_time_ms=max(samples_ms),
            mean_runtime_metrics=MappingProxyType(dict(mean_runtime_metrics)),
            created_at=now or utc_now(),
        )
