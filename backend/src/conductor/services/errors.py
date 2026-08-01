"""Expected use-case failures translated at the API boundary."""


class ServiceError(Exception):
    """Base class for safe application errors."""


class JobNotFound(ServiceError):
    """Requested job does not exist."""


class IdempotencyConflict(ServiceError):
    """An idempotency key was reused for different work."""


class JobConflict(ServiceError):
    """Requested operation conflicts with the job's current state."""


class PayloadTooLarge(ServiceError):
    """Canonical job request exceeds the configured safe limit."""


class WorkerNotFound(ServiceError):
    """A requested worker has never registered."""


class WorkerConflict(ServiceError):
    """A worker operation is stale or conflicts with its current state."""


class AttemptNotFound(ServiceError):
    """A worker reported an unknown attempt."""


class ModelNotFound(ServiceError):
    """A requested model definition does not exist."""


class ModelConflict(ServiceError):
    """A model identity is already registered or cannot be changed safely."""


class RuntimeExecutionError(ServiceError):
    """A runtime could not execute a leased job; the job has been failed safely."""
