"""Framework-independent job and attempt lifecycle tests."""

from datetime import UTC, datetime

import pytest

from conductor.domain.attempt import AttemptStatus, ExecutionAttempt
from conductor.domain.errors import InvalidStateTransition
from conductor.domain.job import Job, JobPriority, JobStatus

NOW = datetime(2026, 7, 19, tzinfo=UTC)


def _job() -> Job:
    return Job.create(
        job_id="job-1",
        idempotency_key="request-1",
        request_hash="hash",
        task="text.generate",
        model_id="demo-model",
        input={"prompt": "hello"},
        parameters={},
        priority=JobPriority.NORMAL,
        max_attempts=3,
        now=NOW,
    )


def test_job_assignment_and_start_are_guarded() -> None:
    assigned = _job().assign("attempt-1", now=NOW)
    running = assigned.start(now=NOW)

    assert assigned.status is JobStatus.ASSIGNED
    assert assigned.active_attempt_id == "attempt-1"
    assert running.status is JobStatus.RUNNING
    assert running.version == 2


def test_queued_job_can_be_cancelled_idempotently() -> None:
    cancelled = _job().cancel(now=NOW)

    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.cancel(now=NOW) is cancelled


def test_running_job_cannot_use_queued_cancellation() -> None:
    running = _job().assign("attempt-1", now=NOW).start(now=NOW)

    with pytest.raises(InvalidStateTransition):
        running.cancel(now=NOW)


def test_attempt_rejects_skipping_starting_state() -> None:
    attempt = ExecutionAttempt.create(
        attempt_id="attempt-1",
        job_id="job-1",
        ordinal=1,
        worker_id="worker-1",
        worker_instance_id="process-run-1",
        now=NOW,
    )

    with pytest.raises(InvalidStateTransition):
        attempt.transition(AttemptStatus.SUCCEEDED, now=NOW)

    running = attempt.transition(AttemptStatus.STARTING, now=NOW).transition(
        AttemptStatus.RUNNING, now=NOW
    )
    assert running.status is AttemptStatus.RUNNING
    assert running.version == 2
