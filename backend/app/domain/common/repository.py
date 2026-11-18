from typing import Generic, Protocol, TypeVar, runtime_checkable

from backend.app.domain.common.entity import Entity

TEntity = TypeVar("TEntity", bound=Entity)
TId = TypeVar("TId")


@runtime_checkable
class BaseRepository(Protocol[TEntity, TId]):
    """Generic repository protocol defining the standard domain persistence port.

    Concrete implementations in the infrastructure layer adhere to this interface
    to maintain strict dependency inversion.
    """

    async def get_by_id(self, id_: TId) -> TEntity | None:
        """Retrieve an entity by its identifier, or None if not found."""
        ...

    async def save(self, entity: TEntity) -> None:
        """Persist a new entity or update an existing one."""
        ...

    async def delete(self, id_: TId) -> None:
        """Remove an entity by its identifier."""
        ...

    async def list_all(self) -> list[TEntity]:
        """List all entities managed by this repository."""
        ...

    async def exists(self, id_: TId) -> bool:
        """Check whether an entity with the given identifier exists."""
        ...
