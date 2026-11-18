import inspect
from collections import defaultdict
from typing import Any, Awaitable, Callable, Iterable, TypeVar

from backend.app.application.common.ports import EventDispatcher
from backend.app.domain.common.event import DomainEvent

TEvent = TypeVar("TEvent", bound=DomainEvent)
EventHandler = Callable[[Any], Awaitable[None] | None]


class EventHandlerError(Exception):
    """Raised when an event handler raises an unhandled exception during dispatch."""

    def __init__(
        self,
        event: DomainEvent,
        handler: EventHandler,
        cause: Exception,
    ) -> None:
        super().__init__(
            f"Event handler {getattr(handler, '__name__', str(handler))} "
            f"failed for event {event.event_name} ({event.event_id}): {cause}"
        )
        self.event = event
        self.handler = handler
        self.cause = cause


class InMemoryEventBus:
    """In-memory event bus implementing the EventDispatcher port.

    Provides synchronous or asynchronous deterministic domain event dispatching
    to registered in-process handlers. Handlers are invoked in order of registration.
    Handler failures are explicitly captured and wrapped in EventHandlerError.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(
        self,
        event_type: type[TEvent],
        handler: Callable[[TEvent], Awaitable[None] | None],
    ) -> None:
        """Register an event handler for a specific domain event type."""
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: type[TEvent],
        handler: Callable[[TEvent], Awaitable[None] | None],
    ) -> None:
        """Remove a previously registered event handler."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def dispatch(self, event: DomainEvent) -> None:
        """Dispatch a single domain event to all registered handlers for its type.

        Handlers registered for the exact type or for DomainEvent base class
        are executed in strict registration order. Any handler failure raises
        an explicit EventHandlerError.
        """
        handlers_to_run: list[EventHandler] = []

        # Handlers for exact event type
        handlers_to_run.extend(self._handlers.get(type(event), []))

        # Handlers registered for base DomainEvent (if distinct from type(event))
        if type(event) is not DomainEvent:
            for handler in self._handlers.get(DomainEvent, []):
                if handler not in handlers_to_run:
                    handlers_to_run.append(handler)

        for handler in handlers_to_run:
            try:
                res = handler(event)
                if inspect.isawaitable(res):
                    await res
            except Exception as exc:
                raise EventHandlerError(
                    event=event,
                    handler=handler,
                    cause=exc,
                ) from exc

    async def dispatch_all(self, events: Iterable[DomainEvent]) -> None:
        """Dispatch a sequence of domain events sequentially in order."""
        for event in events:
            await self.dispatch(event)

    def clear(self) -> None:
        """Reset all handler subscriptions."""
        self._handlers.clear()
