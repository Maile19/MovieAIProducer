from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from backend.app.domain.common.event import DomainEvent


class Entity:
    """Base class for domain entities.

    Entities have a distinct identity that persists over time and through
    different states. Equality is defined strictly by entity identity (ID and type),
    never by mutable attributes.
    """

    def __init__(
        self,
        id_: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self._id: UUID = id_ if id_ is not None else uuid4()
        now = datetime.now(timezone.utc)
        self._created_at: datetime = created_at if created_at is not None else now
        self._updated_at: datetime = updated_at if updated_at is not None else now

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    def touch(self) -> None:
        """Update the updated_at timestamp to current UTC time."""
        self._updated_at = datetime.now(timezone.utc)

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash((type(self), self._id))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self._id}>"


class AggregateRoot(Entity):
    """Base class for Aggregate Roots in Domain-Driven Design.

    Aggregate Roots encapsulate entities and value objects, maintaining
    invariants and explicitly managing recorded domain events.
    """

    def __init__(
        self,
        id_: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id_=id_, created_at=created_at, updated_at=updated_at)
        self._domain_events: list[DomainEvent] = []

    def record_event(self, event: DomainEvent) -> None:
        """Record a domain event to the internal buffer."""
        self._domain_events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Return a copy of all buffered domain events and clear the internal buffer."""
        events = list(self._domain_events)
        self._domain_events.clear()
        return events

    def clear_events(self) -> None:
        """Clear all buffered domain events without returning them."""
        self._domain_events.clear()

    @property
    def domain_events(self) -> tuple[DomainEvent, ...]:
        """Read-only view of currently buffered domain events."""
        return tuple(self._domain_events)
