from typing import Any
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def configure_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
    """Enforce strict SQLite concurrency, foreign keys, and WAL settings on connection checkout."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.close()


def create_database_engine(
    url: str,
    echo: bool = False,
    pool_pre_ping: bool = True,
) -> AsyncEngine:
    """Create and configure an asynchronous SQLAlchemy engine.

    Automatically attaches SQLite PRAGMA listeners if using a SQLite URL.
    """
    engine = create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=pool_pre_ping,
    )

    if "sqlite" in url:
        event.listen(engine.sync_engine, "connect", configure_sqlite_pragmas)

    return engine


async def dispose_database_engine(engine: AsyncEngine) -> None:
    """Safely dispose of an asynchronous database engine and release pool connections."""
    await engine.dispose()
