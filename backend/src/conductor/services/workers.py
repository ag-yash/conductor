"""Worker registration, liveness, leasing, and deterministic completion use cases."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from uuid import uuid4

from conductor.domain.attempt import AttemptStatus, ExecutionAttempt
from conductor.domain.errors import InvalidStateTransition
from conductor.domain.job import Job, JobStatus
from conductor.domain.worker import Worker, WorkerStatus
from conductor.runtime.base import RuntimeAdapterError
from conductor.runtime.manager import RuntimeManager
from conductor.scheduler.policy import PlacementPolicy, RecordedSchedulingDecision, WorkerSnapshot
from conductor.services.errors import (
    AttemptNotFound,
    JobConflict,
    JobNotFound,
    RuntimeExecutionError,
    WorkerConflict,
    WorkerNotFound,
)
from conductor.services.ports import UnitOfWork
from conductor.storage.errors import ConcurrentUpdate


@dataclass(frozen=True, slots=True)
class RegisterWorkerCommand:
    """A worker process asking to become the current instance for an identity."""

    worker_id: str
    worker_instance_id: str
    supported_tasks: tuple[str, ...]
    max_parallel_jobs: int


@dataclass(frozen=True, slots=True)
class WorkLease:
    """One atomically reserved job plus its attempt identity."""

    job: Job
    attempt: ExecutionAttempt


class WorkerService:
    """Coordinate control-plane operations initiated by local workers."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        policy: PlacementPolicy | None = None,
        runtime_manager: RuntimeManager | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._policy = policy or PlacementPolicy()
        self._runtime_manager = runtime_manager or RuntimeManager.default()

    def register(self, command: RegisterWorkerCommand) -> Worker:
        with self._uow_factory() as uow:
            existing = uow.workers.get(command.worker_id)
            worker = Worker.register(
                worker_id=command.worker_id,
                instance_id=command.worker_instance_id,
                supported_tasks=command.supported_tasks,
                max_parallel_jobs=command.max_parallel_jobs,
            )
            if existing is None:
                uow.workers.add(worker)
            else:
                # The stable worker name survives restarts, but the process does not.
                # Re-registration deliberately replaces the old process instance.
                replacement = replace(worker, version=existing.version + 1)
                uow.workers.update(replacement, expected_version=existing.version)
                worker = replacement
            try:
                uow.commit()
            except ConcurrentUpdate as error:
                raise WorkerConflict("worker registration raced with another update") from error
            return worker

    def heartbeat(self, worker_id: str, instance_id: str) -> Worker:
        with self._uow_factory() as uow:
            worker = self._current_worker(uow.workers.get(worker_id), instance_id)
            renewed = worker.heartbeat(instance_id)
            try:
                uow.workers.update(renewed, expected_version=worker.version)
                uow.commit()
            except ConcurrentUpdate as error:
                raise WorkerConflict("worker changed while heartbeat was being recorded") from error
            return renewed

    def drain(self, worker_id: str, instance_id: str) -> Worker:
        with self._uow_factory() as uow:
            worker = self._current_worker(uow.workers.get(worker_id), instance_id)
            drained = worker.drain(instance_id)
            if drained is worker:
                return worker
            try:
                uow.workers.update(drained, expected_version=worker.version)
                uow.commit()
            except ConcurrentUpdate as error:
                raise WorkerConflict("worker changed while drain was being requested") from error
            return drained

    def next_lease(self, worker_id: str, instance_id: str) -> WorkLease | None:
        with self._uow_factory() as uow:
            worker = self._current_worker(uow.workers.get(worker_id), instance_id)
            if worker.status is not WorkerStatus.READY:
                return None
            queued = uow.jobs.list(status=JobStatus.QUEUED, limit=100, offset=0)
            # A polling worker only considers work it claims it can understand.
            job = next((item for item in queued if item.task in worker.supported_tasks), None)
            if job is None:
                return None

            # Take one read-only picture of every worker before deciding. The policy
            # receives this picture, not database objects, so its answer is reproducible.
            snapshots = [
                WorkerSnapshot(
                    worker=candidate,
                    active_slots=uow.attempts.count_active_for_worker(
                        candidate.id, candidate.instance_id
                    ),
                )
                for candidate in uow.workers.list()
            ]
            decision = self._policy.decide(job, snapshots)
            if decision.selected_worker_id != worker.id:
                # The caller did not win this placement. Keep the explanation so an
                # operator can see whether the job is waiting or another worker won.
                outcome = (
                    "deferred" if decision.selected_worker_id is None else "selected_other_worker"
                )
                uow.scheduling_decisions.add(
                    decision_id=str(uuid4()),
                    job_id=job.id,
                    decision=decision,
                    outcome=outcome,
                )
                uow.commit()
                return None

            attempt = ExecutionAttempt.create(
                attempt_id=str(uuid4()),
                job_id=job.id,
                ordinal=1,
                worker_id=worker.id,
                worker_instance_id=worker.instance_id,
            )
            assigned = job.assign(attempt.id)
            try:
                # These writes belong to one transaction. If any one fails, no worker
                # gets a half-created lease and the job remains safe to retry later.
                uow.attempts.add(attempt)
                uow.jobs.update(assigned, expected_version=job.version)
                uow.scheduling_decisions.add(
                    decision_id=str(uuid4()),
                    job_id=job.id,
                    decision=decision,
                    outcome="assigned",
                )
                uow.commit()
            except ConcurrentUpdate as error:
                raise WorkerConflict("job was assigned by another worker; poll again") from error
            return WorkLease(job=assigned, attempt=attempt)

    def start_attempt(self, worker_id: str, instance_id: str, attempt_id: str) -> ExecutionAttempt:
        with self._uow_factory() as uow:
            attempt = self._owned_attempt(uow, worker_id, instance_id, attempt_id)
            try:
                # The attempt and its parent job advance together. A job must never
                # look "running" while its current attempt still looks "assigned".
                started = attempt.transition(AttemptStatus.STARTING).transition(
                    AttemptStatus.RUNNING
                )
                job = self._job_for_attempt(uow, attempt)
                running = job.start()
                uow.attempts.update(started, expected_version=attempt.version)
                uow.jobs.update(running, expected_version=job.version)
                uow.commit()
            except (ConcurrentUpdate, InvalidStateTransition) as error:
                raise WorkerConflict("attempt could not be started") from error
            return started

    def complete_attempt(self, worker_id: str, instance_id: str, attempt_id: str) -> Job:
        with self._uow_factory() as uow:
            attempt = self._owned_attempt(uow, worker_id, instance_id, attempt_id)
            try:
                # Completion is guarded by the active attempt ID, so an older worker
                # process cannot finish a job after a newer attempt has taken over.
                completed = attempt.transition(AttemptStatus.SUCCEEDED)
                job = self._job_for_attempt(uow, attempt)
                succeeded = job.succeed(result={})
                uow.attempts.update(completed, expected_version=attempt.version)
                uow.jobs.update(succeeded, expected_version=job.version)
                uow.commit()
            except (ConcurrentUpdate, InvalidStateTransition) as error:
                raise WorkerConflict("attempt could not be completed") from error
            return succeeded

    def execute_attempt(self, worker_id: str, instance_id: str, attempt_id: str) -> Job:
        """Invoke the configured runtime, then atomically persist its result."""

        with self._uow_factory() as uow:
            attempt = self._owned_attempt(uow, worker_id, instance_id, attempt_id)
            job = self._job_for_attempt(uow, attempt)
            if attempt.status is not AttemptStatus.RUNNING or job.status is not JobStatus.RUNNING:
                raise WorkerConflict("attempt must be running before runtime execution")
            model = uow.model_definitions.get(job.model_id)
            if model is None:
                raise WorkerConflict(f"model {job.model_id} is not registered")

            try:
                result = self._runtime_manager.execute(
                    model=model,
                    worker_id=worker_id,
                    worker_instance_id=instance_id,
                    task=job.task,
                    input=job.input,
                    parameters=job.parameters,
                )
                completed_attempt = attempt.transition(AttemptStatus.SUCCEEDED)
                succeeded_job = job.succeed(result.output)
                uow.attempts.update(completed_attempt, expected_version=attempt.version)
                uow.jobs.update(succeeded_job, expected_version=job.version)
                uow.commit()
                return succeeded_job
            except RuntimeAdapterError as error:
                failed_attempt = attempt.transition(AttemptStatus.FAILED)
                failed_job = job.fail(str(error))
                uow.attempts.update(failed_attempt, expected_version=attempt.version)
                uow.jobs.update(failed_job, expected_version=job.version)
                uow.commit()
                raise RuntimeExecutionError(str(error)) from error

    def decisions_for_job(self, job_id: str) -> list[RecordedSchedulingDecision]:
        """Return stored scheduling explanations after confirming the job exists."""

        with self._uow_factory() as uow:
            if uow.jobs.get(job_id) is None:
                raise JobNotFound(f"job {job_id} was not found")
            return uow.scheduling_decisions.list_for_job(job_id)

    @staticmethod
    def _current_worker(worker: Worker | None, instance_id: str) -> Worker:
        if worker is None:
            raise WorkerNotFound("worker has not registered")
        if worker.instance_id != instance_id:
            raise WorkerConflict("worker_instance_id belongs to an older worker process")
        return worker

    @staticmethod
    def _job_for_attempt(uow: UnitOfWork, attempt: ExecutionAttempt) -> Job:
        job = uow.jobs.get(attempt.job_id)
        if job is None:
            raise JobConflict("attempt refers to a missing job")
        if job.active_attempt_id != attempt.id:
            raise WorkerConflict("attempt is no longer the job's active lease")
        return job

    def _owned_attempt(
        self,
        uow: UnitOfWork,
        worker_id: str,
        instance_id: str,
        attempt_id: str,
    ) -> ExecutionAttempt:
        self._current_worker(uow.workers.get(worker_id), instance_id)
        attempt = uow.attempts.get(attempt_id)
        if attempt is None:
            raise AttemptNotFound("attempt was not found")
        if attempt.worker_id != worker_id or attempt.worker_instance_id != instance_id:
            raise WorkerConflict("attempt belongs to a different worker process")
        return attempt
