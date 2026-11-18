from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for all domain events.

    Domain events represent something meaningful that occurred in the domain.
    They are immutable facts containing an event ID and a UTC timestamp.
    """

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    aggregate_id: UUID | None = None

    @property
    def event_name(self) -> str:
        """Name of the event, default to class name."""
        return self.__class__.__name__
