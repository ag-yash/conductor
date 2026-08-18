"""Immutable measurements reported by one current worker process."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WorkerResourceSnapshot:
    """One honest observation, not a prediction or a scheduler decision.

    The worker measures its own machine and reports the numbers. The control
    plane records when it accepted the report so operators can distinguish a
    current measurement from an old one later.
    """

    id: str
    worker_id: str
    worker_instance_id: str
    host_cpu_percent: float
    host_total_memory_bytes: int
    host_available_memory_bytes: int
    process_cpu_percent: float
    process_memory_bytes: int
    observed_at: datetime

    def __post_init__(self) -> None:
        if not 0 <= self.host_cpu_percent <= 100:
            raise ValueError("host_cpu_percent must be between 0 and 100")
        if self.host_total_memory_bytes <= 0:
            raise ValueError("host_total_memory_bytes must be positive")
        if not 0 <= self.host_available_memory_bytes <= self.host_total_memory_bytes:
            raise ValueError("host_available_memory_bytes must fit within total memory")
        if self.process_cpu_percent < 0 or self.process_memory_bytes < 0:
            raise ValueError("process resource measurements cannot be negative")

    def safe_memory_headroom_bytes(self, reserve_bytes: int) -> int:
        """Return memory left after keeping the scheduler's safety reserve."""

        if reserve_bytes < 0:
            raise ValueError("reserve_bytes cannot be negative")
        return max(0, self.host_available_memory_bytes - reserve_bytes)
