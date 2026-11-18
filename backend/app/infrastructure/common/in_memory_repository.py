from typing import Generic, TypeVar

from backend.app.domain.common.entity import Entity
from backend.app.domain.common.repository import BaseRepository

TEntity = TypeVar("TEntity", bound=Entity)
TId = TypeVar("TId")


class InMemoryRepository(Generic[TEntity, TId]):
    """Generic in-memory repository implementing the BaseRepository port.

    Provides fast, isolated persistence for domain unit tests and use case execution
    without requiring a database engine. Entities are indexed by their unique identity.
    """

    def __init__(self) -> None:
        self._storage: dict[TId, TEntity] = {}

    async def get_by_id(self, id_: TId) -> TEntity | None:
        """Retrieve an entity by its identifier, or None if not found."""
        return self._storage.get(id_)

    async def save(self, entity: TEntity) -> None:
        """Persist or update an entity indexed by its identity."""
        # Using entity.id as key; if entity.id is compatible with TId
        key = entity.id  # type: ignore[assignment]
        self._storage[key] = entity

    async def delete(self, id_: TId) -> None:
        """Remove an entity by its identifier if present."""
        self._storage.pop(id_, None)

    async def list_all(self) -> list[TEntity]:
        """Return a snapshot list of all entities in storage."""
        return list(self._storage.values())

    async def exists(self, id_: TId) -> bool:
        """Check whether an entity exists with the specified identifier."""
        return id_ in self._storage

    def clear(self) -> None:
        """Helper method to reset internal storage state between tests."""
        self._storage.clear()
