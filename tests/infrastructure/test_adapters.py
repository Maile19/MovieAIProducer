from dataclasses import dataclass
from uuid import UUID, uuid4
import pytest

from backend.app.application.common.ports import EventDispatcher, UnitOfWork
from backend.app.domain.common.entity import Entity
from backend.app.domain.common.event import DomainEvent
from backend.app.domain.common.repository import BaseRepository
from backend.app.infrastructure.common.event_bus import (
    EventHandlerError,
    InMemoryEventBus,
)
from backend.app.infrastructure.common.in_memory_repository import (
    InMemoryRepository,
)
from backend.app.infrastructure.common.unit_of_work import (
    InMemoryUnitOfWork,
)


class SampleEntity(Entity):
    def __init__(self, id_: UUID | None = None, title: str = "initial") -> None:
        super().__init__(id_=id_)
        self.title = title


@dataclass(frozen=True)
class SceneCreatedEvent(DomainEvent):
    scene_number: int = 1


@pytest.mark.anyio
async def test_in_memory_repository_crud():
    repo: InMemoryRepository[SampleEntity, UUID] = InMemoryRepository()
    assert isinstance(repo, BaseRepository)

    e1 = SampleEntity(title="Scene 1")
    e2 = SampleEntity(title="Scene 2")

    # Save
    await repo.save(e1)
    await repo.save(e2)

    # Exists & Get
    assert await repo.exists(e1.id) is True
    assert await repo.exists(uuid4()) is False
    fetched = await repo.get_by_id(e1.id)
    assert fetched is not None
    assert fetched.title == "Scene 1"

    # List all
    all_items = await repo.list_all()
    assert len(all_items) == 2

    # Duplicate identity behavior (updates/replaces)
    updated_e1 = SampleEntity(id_=e1.id, title="Scene 1 - Revised")
    await repo.save(updated_e1)
    refetched = await repo.get_by_id(e1.id)
    assert refetched is not None
    assert refetched.title == "Scene 1 - Revised"
    assert len(await repo.list_all()) == 2

    # Delete
    await repo.delete(e1.id)
    assert await repo.exists(e1.id) is False
    assert await repo.get_by_id(e1.id) is None
    assert len(await repo.list_all()) == 1

    # Clear
    repo.clear()
    assert len(await repo.list_all()) == 0


@pytest.mark.anyio
async def test_in_memory_event_bus():
    bus = InMemoryEventBus()
    assert isinstance(bus, EventDispatcher)

    received_events: list[DomainEvent] = []

    async def async_handler(event: SceneCreatedEvent) -> None:
        received_events.append(event)

    def sync_handler(event: SceneCreatedEvent) -> None:
        received_events.append(event)

    bus.subscribe(SceneCreatedEvent, async_handler)
    bus.subscribe(SceneCreatedEvent, sync_handler)

    ev1 = SceneCreatedEvent(scene_number=10)
    await bus.dispatch(ev1)

    assert len(received_events) == 2
    assert received_events[0] == ev1
    assert received_events[1] == ev1

    # Dispatch sequence
    ev2 = SceneCreatedEvent(scene_number=20)
    await bus.dispatch_all([ev2])
    assert len(received_events) == 4

    # Unsubscribe
    bus.unsubscribe(SceneCreatedEvent, sync_handler)
    received_events.clear()
    await bus.dispatch(ev1)
    assert len(received_events) == 1

    # Clear
    bus.clear()
    received_events.clear()
    await bus.dispatch(ev1)
    assert len(received_events) == 0


@pytest.mark.anyio
async def test_in_memory_event_bus_failure_handling():
    bus = InMemoryEventBus()

    def faulty_handler(event: DomainEvent) -> None:
        raise ValueError("Handler crash during production job")

    bus.subscribe(SceneCreatedEvent, faulty_handler)

    ev = SceneCreatedEvent(scene_number=99)
    with pytest.raises(EventHandlerError) as exc_info:
        await bus.dispatch(ev)

    err = exc_info.value
    assert err.event == ev
    assert err.handler == faulty_handler
    assert isinstance(err.cause, ValueError)
    assert "Handler crash during production job" in str(err)


@pytest.mark.anyio
async def test_in_memory_unit_of_work_lifecycle():
    uow = InMemoryUnitOfWork()
    assert isinstance(uow, UnitOfWork)

    # Outside active context, commit/rollback must fail
    with pytest.raises(RuntimeError):
        await uow.commit()

    with pytest.raises(RuntimeError):
        await uow.rollback()

    # Normal successful transaction context
    async with uow:
        assert uow.is_active is True
        assert uow.committed is False
        assert uow.rolled_back is False
        await uow.commit()
        assert uow.committed is True

    assert uow.is_active is False
    assert uow.committed is True

    # Error inside transaction context triggers automatic rollback
    with pytest.raises(ZeroDivisionError):
        async with uow:
            assert uow.is_active is True
            assert uow.committed is False
            _ = 1 / 0

    assert uow.is_active is False
    assert uow.rolled_back is True
    assert uow.committed is False

    # Cannot commit after rollback
    async with uow:
        await uow.rollback()
        with pytest.raises(RuntimeError):
            await uow.commit()
