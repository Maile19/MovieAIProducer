import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.domain.common.entity import Entity
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.engine import (
    create_database_engine,
    dispose_database_engine,
)
from backend.app.infrastructure.database.repository import SqlAlchemyRepository
from backend.app.infrastructure.database.session import create_session_factory
from backend.app.infrastructure.database.types import GUID, UTCDateTime


class SampleEntity(Entity):
    name: str

    def __init__(
        self,
        name: str,
        id_: uuid.UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id_=id_, created_at=created_at, updated_at=updated_at)
        self.name = name


class SampleModel(Base):
    __tablename__ = "test_samples"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class SampleRepository(SqlAlchemyRepository[SampleEntity, SampleModel, uuid.UUID]):
    def __init__(self, session) -> None:
        super().__init__(session=session, model_cls=SampleModel)

    def to_domain(self, model: SampleModel) -> SampleEntity:
        return SampleEntity(
            name=model.name,
            id_=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self, entity: SampleEntity) -> SampleModel:
        return SampleModel(
            id=entity.id,
            name=entity.name,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


@pytest.fixture
async def sample_db():
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    try:
        yield session_factory
    finally:
        await dispose_database_engine(engine)


@pytest.mark.anyio
async def test_repository_save_and_get_by_id(sample_db):
    session_factory = sample_db
    test_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    entity = SampleEntity(name="Original", id_=test_id, created_at=now, updated_at=now)

    async with session_factory() as session:
        repo = SampleRepository(session)
        await repo.save(entity)
        await session.commit()

    async with session_factory() as session:
        repo = SampleRepository(session)
        fetched = await repo.get_by_id(test_id)
        assert fetched is not None
        assert fetched.id == test_id
        assert fetched.name == "Original"
        assert isinstance(fetched.id, uuid.UUID)


@pytest.mark.anyio
async def test_repository_get_by_id_not_found(sample_db):
    session_factory = sample_db
    non_existent_id = uuid.uuid4()

    async with session_factory() as session:
        repo = SampleRepository(session)
        result = await repo.get_by_id(non_existent_id)
        assert result is None


@pytest.mark.anyio
async def test_repository_save_updates_existing_entity(sample_db):
    session_factory = sample_db
    test_id = uuid.uuid4()
    entity = SampleEntity(name="Version 1", id_=test_id)

    async with session_factory() as session:
        repo = SampleRepository(session)
        await repo.save(entity)
        await session.commit()

    # Modify entity and update
    entity.name = "Version 2"
    entity.touch()

    async with session_factory() as session:
        repo = SampleRepository(session)
        await repo.save(entity)
        await session.commit()

    async with session_factory() as session:
        repo = SampleRepository(session)
        updated = await repo.get_by_id(test_id)
        assert updated is not None
        assert updated.name == "Version 2"
        assert updated.updated_at == entity.updated_at


@pytest.mark.anyio
async def test_repository_delete(sample_db):
    session_factory = sample_db
    test_id = uuid.uuid4()
    entity = SampleEntity(name="To Delete", id_=test_id)

    async with session_factory() as session:
        repo = SampleRepository(session)
        await repo.save(entity)
        await session.commit()

    async with session_factory() as session:
        repo = SampleRepository(session)
        await repo.delete(test_id)
        await session.commit()

    async with session_factory() as session:
        repo = SampleRepository(session)
        assert await repo.get_by_id(test_id) is None


@pytest.mark.anyio
async def test_repository_delete_non_existent_is_noop(sample_db):
    session_factory = sample_db
    non_existent_id = uuid.uuid4()

    async with session_factory() as session:
        repo = SampleRepository(session)
        # Deleting non-existent should not raise
        await repo.delete(non_existent_id)
        await session.commit()


@pytest.mark.anyio
async def test_repository_list_all_and_exists(sample_db):
    session_factory = sample_db
    id1, id2 = uuid.uuid4(), uuid.uuid4()
    e1 = SampleEntity(name="Item 1", id_=id1)
    e2 = SampleEntity(name="Item 2", id_=id2)

    async with session_factory() as session:
        repo = SampleRepository(session)
        assert await repo.list_all() == []
        assert await repo.exists(id1) is False

        await repo.save(e1)
        await repo.save(e2)
        await session.commit()

    async with session_factory() as session:
        repo = SampleRepository(session)
        all_items = await repo.list_all()
        assert len(all_items) == 2
        item_ids = {item.id for item in all_items}
        assert item_ids == {id1, id2}
        assert await repo.exists(id1) is True
        assert await repo.exists(id2) is True
        assert await repo.exists(uuid.uuid4()) is False
