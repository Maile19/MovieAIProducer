from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.common.entity import Entity
from backend.app.infrastructure.database.base import Base

TEntity = TypeVar("TEntity", bound=Entity)
TModel = TypeVar("TModel", bound=Base)
TId = TypeVar("TId")


class SqlAlchemyRepository(ABC, Generic[TEntity, TModel, TId]):
    """Generic SQLAlchemy repository implementing the Domain BaseRepository port.

    Maintains Clean Architecture boundary separation by explicitly translating
    between Domain Entities and Infrastructure ORM Models.

    Mapping Scope & Aggregate Relationship Constraints:
    - This base class provides standard CRUD semantics for entity root models.
    - Default attribute synchronization is intentionally restricted to scalar table
      columns (`model.__table__.columns`).
    - Aggregate Relationships: Nested child entities, value object collections,
      and 1:N or M:N relationships are deliberately NOT managed automatically
      by this generic implementation to avoid implicit cascade mutations or
      performance regressions.
    - Subclass Override Requirements: When concrete repositories implement
      aggregate roots with nested child entities (e.g., Screenplays with Scenes),
      the concrete repository MUST override `to_domain`, `to_model`, and/or
      `update_model` to explicitly orchestrate child collection reconciliation,
      cascade persistence, and orphan deletion within the transaction boundary.
    """

    def __init__(self, session: AsyncSession, model_cls: type[TModel]) -> None:
        self._session = session
        self._model_cls = model_cls

    @abstractmethod
    def to_domain(self, model: TModel) -> TEntity:
        """Map a database ORM model to a pure domain entity."""
        pass

    @abstractmethod
    def to_model(self, entity: TEntity) -> TModel:
        """Map a pure domain entity to an ORM database model."""
        pass

    def update_model(self, model: TModel, entity: TEntity) -> None:
        """Update existing ORM model attributes from entity state.

        Default Implementation:
        - Copies all scalar column values defined in `model.__table__.columns`
          (excluding primary key 'id') from a newly constructed model representation.

        Override Requirements:
        - Subclasses managing aggregate roots with child collections MUST override
          this method to explicitly diff, add, update, and remove child records.
        """
        new_model = self.to_model(entity)
        for column in model.__table__.columns:
            key = column.key
            if key != "id":
                setattr(model, key, getattr(new_model, key))

    async def get_by_id(self, id_: TId) -> TEntity | None:
        """Retrieve a domain entity by its unique identifier."""
        stmt = select(self._model_cls).where(getattr(self._model_cls, "id") == id_)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self.to_domain(model) if model else None

    async def save(self, entity: TEntity) -> None:
        """Persist or update an entity in the current session."""
        stmt = select(self._model_cls).where(getattr(self._model_cls, "id") == entity.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            self.update_model(existing, entity)
        else:
            model = self.to_model(entity)
            self._session.add(model)

    async def delete(self, id_: TId) -> None:
        """Delete an entity by its identifier."""
        stmt = select(self._model_cls).where(getattr(self._model_cls, "id") == id_)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            await self._session.delete(model)

    async def list_all(self) -> list[TEntity]:
        """List all entities represented in the table."""
        stmt = select(self._model_cls)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self.to_domain(m) for m in models]

    async def exists(self, id_: TId) -> bool:
        """Check existence of an entity by its identifier."""
        stmt = (
            select(func.count())
            .select_from(self._model_cls)
            .where(getattr(self._model_cls, "id") == id_)
        )
        count = await self._session.scalar(stmt)
        return bool(count and count > 0)
