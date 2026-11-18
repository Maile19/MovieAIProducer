from dataclasses import FrozenInstanceError, dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4
import pytest

from backend.app.domain.common.entity import AggregateRoot, Entity
from backend.app.domain.common.event import DomainEvent
from backend.app.domain.common.exceptions import (
    BusinessRuleValidationException,
    ConflictException,
    DomainException,
    EntityNotFoundException,
    InvariantViolationException,
)
from backend.app.domain.common.repository import BaseRepository
from backend.app.domain.common.value_object import ValueObject


class DummyEntity(Entity):
    def __init__(self, id_: UUID | None = None, name: str = "test") -> None:
        super().__init__(id_=id_)
        self.name = name


class OtherEntity(Entity):
    pass


class ParentEntity(Entity):
    pass


class ChildEntity(ParentEntity):
    pass


@dataclass(frozen=True)
class RequiredPayloadEvent(DomainEvent):
    title: str
    duration_frames: int


class DummyAggregate(AggregateRoot):
    def __init__(self, id_: UUID | None = None, title: str = "demo") -> None:
        super().__init__(id_=id_)
        self.title = title

    def perform_action(self) -> None:
        self.record_event(DummyEvent(aggregate_id=self.id, payload="action_performed"))


@dataclass(frozen=True)
class DummyEvent(DomainEvent):
    payload: str = ""


@dataclass(frozen=True)
class CoordinateVO(ValueObject):
    x: int
    y: int


def test_entity_identity_equality():
    shared_id = uuid4()
    e1 = DummyEntity(id_=shared_id, name="alpha")
    e2 = DummyEntity(id_=shared_id, name="beta")  # different name, same ID
    diff_id = uuid4()
    e3 = DummyEntity(id_=diff_id, name="alpha")
    other_type = OtherEntity(id_=shared_id)

    # Same class and same ID must be equal
    assert e1 == e2
    assert hash(e1) == hash(e2)

    # Different ID must not be equal
    assert e1 != e3

    # Different class with same ID must not be equal
    assert e1 != other_type

    # Non-entity equality check
    assert e1 != "some_string"

    # Default ID is valid UUID
    assert isinstance(e1.id, UUID)
    assert isinstance(e1.created_at, datetime)
    assert isinstance(e1.updated_at, datetime)


def test_entity_touch():
    entity = DummyEntity()
    initial_updated = entity.updated_at
    entity.touch()
    assert entity.updated_at >= initial_updated


def test_entity_inheritance_equality_symmetry():
    """Verify FINDING-002 remediation: Entity equality is symmetric across inheritance."""
    shared_id = uuid4()
    p1 = ParentEntity(id_=shared_id)
    p2 = ParentEntity(id_=shared_id)
    c1 = ChildEntity(id_=shared_id)
    c2 = ChildEntity(id_=shared_id)

    # Parent-Parent
    assert p1 == p2
    assert hash(p1) == hash(p2)

    # Child-Child
    assert c1 == c2
    assert hash(c1) == hash(c2)

    # Parent-Child and Child-Parent must both be False (symmetric)
    assert p1 != c1
    assert c1 != p1
    assert (p1 == c1) is False
    assert (c1 == p1) is False


def test_domain_event_subclass_with_required_fields():
    """Verify FINDING-003 remediation: DomainEvent subclass can have required non-default fields."""
    ev = RequiredPayloadEvent(title="Intro Sequence", duration_frames=240)
    assert ev.title == "Intro Sequence"
    assert ev.duration_frames == 240
    assert isinstance(ev.event_id, UUID)
    assert isinstance(ev.occurred_at, datetime)
    assert ev.occurred_at.tzinfo == timezone.utc
    assert ev.event_name == "RequiredPayloadEvent"
    assert ev.aggregate_id is None


def test_aggregate_root_event_collection_and_clearing():
    agg = DummyAggregate()
    assert len(agg.domain_events) == 0

    agg.perform_action()
    agg.perform_action()

    # Read-only domain_events property returns tuple
    assert isinstance(agg.domain_events, tuple)
    assert len(agg.domain_events) == 2
    assert all(isinstance(e, DummyEvent) for e in agg.domain_events)

    # pull_events returns copy and clears buffer
    pulled = agg.pull_events()
    assert len(pulled) == 2
    assert len(agg.domain_events) == 0

    # clear_events clears buffer
    agg.perform_action()
    assert len(agg.domain_events) == 1
    agg.clear_events()
    assert len(agg.domain_events) == 0


def test_value_object_immutability_and_equality():
    c1 = CoordinateVO(x=10, y=20)
    c2 = CoordinateVO(x=10, y=20)
    c3 = CoordinateVO(x=10, y=99)

    # Equality by structural value
    assert c1 == c2
    assert hash(c1) == hash(c2)
    assert c1 != c3

    # Immutability: attribute assignment raises FrozenInstanceError
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        c1.x = 50  # type: ignore[misc]


def test_domain_event_metadata():
    event = DummyEvent(payload="test_payload")
    assert isinstance(event.event_id, UUID)
    assert isinstance(event.occurred_at, datetime)
    assert event.occurred_at.tzinfo == timezone.utc
    assert event.event_name == "DummyEvent"
    assert event.payload == "test_payload"

    # Domain events are immutable
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        event.payload = "new_payload"  # type: ignore[misc]


def test_domain_exception_hierarchy():
    exc = DomainException("Base domain error", code="CUSTOM_CODE", details={"k": "v"})
    assert str(exc) == "[CUSTOM_CODE] Base domain error"
    assert exc.to_dict() == {
        "code": "CUSTOM_CODE",
        "category": "business_rule",
        "message": "Base domain error",
        "details": {"k": "v"},
    }

    not_found = EntityNotFoundException("Scene not found", details={"scene_id": "123"})
    assert not_found.category == "resource"
    assert not_found.code == "RESOURCE_NOT_FOUND"

    rule_fail = BusinessRuleValidationException("DNA locked", details={"status": "locked"})
    assert rule_fail.category == "business_rule"
    assert rule_fail.code == "BUSINESS_RULE_VIOLATION"

    invariant_fail = InvariantViolationException("Aggregate state invalid")
    assert invariant_fail.category == "business_rule"
    assert invariant_fail.code == "INVARIANT_VIOLATION"

    conflict = ConflictException("Duplicate slug", details={"slug": "scene-1"})
    assert conflict.category == "conflict"
    assert conflict.code == "CONFLICT_ERROR"


def test_repository_protocol_compatibility():
    class ValidRepo:
        async def get_by_id(self, id_: UUID) -> DummyEntity | None:
            return None

        async def save(self, entity: DummyEntity) -> None:
            pass

        async def delete(self, id_: UUID) -> None:
            pass

        async def list_all(self) -> list[DummyEntity]:
            return []

        async def exists(self, id_: UUID) -> bool:
            return False

    repo = ValidRepo()
    assert isinstance(repo, BaseRepository)
