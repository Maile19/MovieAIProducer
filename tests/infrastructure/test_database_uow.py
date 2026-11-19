from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.application.common.ports import UnitOfWork
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.engine import (
    create_database_engine,
    dispose_database_engine,
)
from backend.app.infrastructure.database.session import create_session_factory
from backend.app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


class MockRecord(Base):
    __tablename__ = "test_uow_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


@pytest.fixture
async def db_context(tmp_path: Path):
    db_file = tmp_path / "test_uow.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_database_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    try:
        yield engine, session_factory
    finally:
        await dispose_database_engine(engine)


@pytest.mark.anyio
async def test_uow_commit_success(db_context):
    engine, session_factory = db_context
    uow = SqlAlchemyUnitOfWork(session_factory)
    assert isinstance(uow, UnitOfWork)

    # 1. Commit transaction
    async with uow:
        assert uow.is_active is True
        assert uow.session is not None
        record = MockRecord(id="rec-1", name="Alpha Scene")
        uow.session.add(record)
        await uow.commit()
        assert uow.committed is True

    assert uow.is_active is False
    assert uow.session is None

    # Verify persistence with a fresh session
    verify_session = session_factory()
    try:
        stmt = select(MockRecord).where(MockRecord.id == "rec-1")
        result = await verify_session.execute(stmt)
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.name == "Alpha Scene"
    finally:
        await verify_session.close()


@pytest.mark.anyio
async def test_uow_explicit_rollback(db_context):
    engine, session_factory = db_context
    uow = SqlAlchemyUnitOfWork(session_factory)

    async with uow:
        record = MockRecord(id="rec-rollback", name="Discarded Scene")
        uow.session.add(record)
        await uow.rollback()
        assert uow.rolled_back is True

    # Verify record was not persisted
    verify_session = session_factory()
    try:
        stmt = select(MockRecord).where(MockRecord.id == "rec-rollback")
        result = await verify_session.execute(stmt)
        assert result.scalar_one_or_none() is None
    finally:
        await verify_session.close()


@pytest.mark.anyio
async def test_uow_exception_automatic_rollback(db_context):
    engine, session_factory = db_context
    uow = SqlAlchemyUnitOfWork(session_factory)

    with pytest.raises(ValueError):
        async with uow:
            record = MockRecord(id="rec-exc", name="Error Scene")
            uow.session.add(record)
            raise ValueError("Simulated unexpected failure during processing")

    assert uow.rolled_back is True

    # Verify record was rolled back
    verify_session = session_factory()
    try:
        stmt = select(MockRecord).where(MockRecord.id == "rec-exc")
        result = await verify_session.execute(stmt)
        assert result.scalar_one_or_none() is None
    finally:
        await verify_session.close()


@pytest.mark.anyio
async def test_uow_guard_exceptions(db_context):
    _, session_factory = db_context
    uow = SqlAlchemyUnitOfWork(session_factory)

    # 1. Calling commit/rollback outside active context raises RuntimeError
    with pytest.raises(RuntimeError, match="outside an active"):
        await uow.commit()

    with pytest.raises(RuntimeError, match="outside an active"):
        await uow.rollback()

    # 2. Double commit raises RuntimeError
    async with uow:
        await uow.commit()
        with pytest.raises(RuntimeError, match="already been committed"):
            await uow.commit()

    # 3. Rollback after commit raises RuntimeError
    uow2 = SqlAlchemyUnitOfWork(session_factory)
    async with uow2:
        await uow2.commit()
        with pytest.raises(RuntimeError, match="already been committed"):
            await uow2.rollback()

    # 4. Commit after rollback raises RuntimeError
    uow3 = SqlAlchemyUnitOfWork(session_factory)
    async with uow3:
        await uow3.rollback()
        with pytest.raises(RuntimeError, match="has been rolled back"):
            await uow3.commit()
