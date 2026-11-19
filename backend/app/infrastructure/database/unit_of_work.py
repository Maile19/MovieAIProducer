from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession, AsyncTransaction, async_sessionmaker


class SqlAlchemyUnitOfWork:
    """SQLAlchemy implementation of the Application UnitOfWork port.

    Manages transaction boundaries and provides atomic commit and rollback guarantees
    backed by an asynchronous database session.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self._transaction: AsyncTransaction | None = None
        self.is_active: bool = False
        self.committed: bool = False
        self.rolled_back: bool = False

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        """Enter transaction context, opening session and starting explicit transaction."""
        self.session = self._session_factory()
        self._transaction = await self.session.begin()
        self.is_active = True
        self.committed = False
        self.rolled_back = False
        return self

    async def commit(self) -> None:
        """Commit pending changes within the active transaction."""
        if not self.is_active or not self.session or not self._transaction:
            raise RuntimeError("Cannot commit outside an active Unit of Work context.")
        if self.rolled_back:
            raise RuntimeError("Cannot commit a transaction that has been rolled back.")
        if self.committed:
            raise RuntimeError("Transaction has already been committed.")
        await self._transaction.commit()
        self.committed = True

    async def rollback(self) -> None:
        """Roll back pending changes within the active transaction."""
        if not self.is_active or not self.session:
            raise RuntimeError("Cannot rollback outside an active Unit of Work context.")
        if self.committed:
            raise RuntimeError("Cannot rollback a transaction that has already been committed.")
        if self.rolled_back:
            return
        if self._transaction and self._transaction.is_active:
            await self._transaction.rollback()
        self.rolled_back = True

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool | None:
        """Exit transaction context, automatically rolling back on uncaught exception."""
        try:
            if exc_type is not None and not self.committed:
                await self.rollback()
        finally:
            self.is_active = False
            if self.session:
                await self.session.close()
                self.session = None
                self._transaction = None
        return None
