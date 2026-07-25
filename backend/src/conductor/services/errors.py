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
