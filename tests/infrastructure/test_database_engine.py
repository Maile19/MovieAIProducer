import asyncio
from pathlib import Path
import pytest
from sqlalchemy import ForeignKey, Integer, String, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.app.infrastructure.database.engine import (
    create_database_engine,
    dispose_database_engine,
)
from backend.app.infrastructure.database.session import create_session_factory


class FKTestBase(DeclarativeBase):
    pass


class ParentModel(FKTestBase):
    __tablename__ = "fk_parents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class ChildModel(FKTestBase):
    __tablename__ = "fk_children"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fk_parents.id"),
        nullable=False,
    )


@pytest.mark.anyio
async def test_engine_creation_pragmas_and_disposal(tmp_path: Path):
    db_file = tmp_path / "test_engine.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_database_engine(db_url)
    try:
        async with engine.connect() as conn:
            fk = await conn.scalar(text("PRAGMA foreign_keys;"))
            jm = await conn.scalar(text("PRAGMA journal_mode;"))
            sync = await conn.scalar(text("PRAGMA synchronous;"))
            bt = await conn.scalar(text("PRAGMA busy_timeout;"))

            # 1. Foreign keys must be strictly ON (1)
            assert fk == 1
            # 2. Journal mode must be WAL
            assert str(jm).lower() == "wal"
            # 3. Synchronous must be NORMAL (1)
            assert sync == 1
            # 4. Busy timeout must be 5000 ms
            assert bt == 5000
    finally:
        await dispose_database_engine(engine)


@pytest.mark.anyio
async def test_session_lifecycle(tmp_path: Path):
    db_file = tmp_path / "test_session.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_database_engine(db_url)
    session_factory = create_session_factory(engine)

    try:
        session: AsyncSession = session_factory()
        assert session.is_active is True
        res = await session.execute(text("SELECT 42;"))
        assert res.scalar() == 42
        await session.close()
    finally:
        await dispose_database_engine(engine)


@pytest.mark.anyio
async def test_sqlite_foreign_key_enforcement(tmp_path: Path):
    """Verify that SQLite actively enforces foreign key constraints and rolls back safely."""
    db_file = tmp_path / "test_fk.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_database_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(FKTestBase.metadata.create_all)

    session_factory = create_session_factory(engine)
    try:
        # 1. Valid parent and child insert
        async with session_factory() as session:
            parent = ParentModel(id=1, name="Valid Parent")
            session.add(parent)
            await session.flush()
            child = ChildModel(id=1, parent_id=1)
            session.add(child)
            await session.commit()

        # 2. Invalid child insert (referencing non-existent parent_id 999)
        async with session_factory() as session:
            invalid_child = ChildModel(id=2, parent_id=999)
            session.add(invalid_child)
            with pytest.raises(IntegrityError):
                await session.commit()

        # 3. Verify database state remains clean and valid
        async with session_factory() as session:
            res = await session.execute(select(ChildModel))
            children = res.scalars().all()
            assert len(children) == 1
            assert children[0].id == 1
            assert children[0].parent_id == 1
    finally:
        await dispose_database_engine(engine)


@pytest.mark.anyio
async def test_sqlite_concurrent_write_busy_timeout(tmp_path: Path):
    """Verify that WAL mode and busy_timeout=5000 queue concurrent writes without lock failure."""
    db_file = tmp_path / "test_concurrency.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_database_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(FKTestBase.metadata.create_all)

    session_factory = create_session_factory(engine)
    t1_started = asyncio.Event()

    async def writer_1():
        async with session_factory() as session:
            session.add(ParentModel(id=101, name="Writer 1"))
            await session.flush()
            t1_started.set()
            # Hold lock briefly to ensure writer_2 contends for write lock
            await asyncio.sleep(0.05)
            await session.commit()

    async def writer_2():
        await t1_started.wait()
        async with session_factory() as session:
            # Does not fail with database is locked because busy_timeout allows queueing
            session.add(ParentModel(id=102, name="Writer 2"))
            await session.commit()

    try:
        await asyncio.gather(writer_1(), writer_2())

        async with session_factory() as session:
            res = await session.execute(
                select(ParentModel).where(ParentModel.id.in_([101, 102]))
            )
            parents = res.scalars().all()
            assert len(parents) == 2
            assert {p.id for p in parents} == {101, 102}
    finally:
        await dispose_database_engine(engine)
