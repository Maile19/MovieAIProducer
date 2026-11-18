from datetime import datetime
from typing import Any, Iterable, Protocol, runtime_checkable

from backend.app.domain.common.event import DomainEvent


@runtime_checkable
class Clock(Protocol):
    """Port interface for providing system time.

    Enables deterministic time-mocking in tests and audits.
    """

    def now_utc(self) -> datetime:
        """Return the current datetime in UTC."""
        ...


@runtime_checkable
class EventDispatcher(Protocol):
    """Port interface for dispatching domain events to registered handlers."""

    async def dispatch(self, event: DomainEvent) -> None:
        """Dispatch a single domain event to its registered consumers."""
        ...

    async def dispatch_all(self, events: Iterable[DomainEvent]) -> None:
        """Dispatch a sequence of domain events in order."""
        ...


@runtime_checkable
class UnitOfWork(Protocol):
    """Application port interface defining the Unit of Work contract.

    Manages transaction boundaries, commit, and rollback across repositories.
    Must be used as an asynchronous context manager.
    """

    async def __aenter__(self) -> "UnitOfWork":
        """Enter the transaction context."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool | None:
        """Exit the transaction context, triggering rollback if an exception occurred."""
        ...

    async def commit(self) -> None:
        """Commit all pending changes within this unit of work."""
        ...

    async def rollback(self) -> None:
        """Roll back all pending changes within this unit of work."""
        ...
