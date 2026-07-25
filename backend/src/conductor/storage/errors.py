"""Expected persistence failures translated by application services."""


class PersistenceError(Exception):
    """Base class for expected storage failures."""


class ConcurrentUpdate(PersistenceError):
    """Raised when optimistic locking detects a stale aggregate."""


class DuplicateIdempotencyKey(PersistenceError):
    """Raised when a concurrent submission already stored the key."""
