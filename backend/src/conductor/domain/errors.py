"""Errors raised when a requested domain operation is invalid."""


class DomainError(Exception):
    """Base class for expected domain rule violations."""


class InvalidStateTransition(DomainError):
    """Raised when an entity cannot legally enter the requested state."""

    def __init__(self, entity: str, current: str, requested: str) -> None:
        super().__init__(f"{entity} cannot transition from {current} to {requested}")
