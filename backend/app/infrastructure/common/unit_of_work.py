from typing import Any


class InMemoryUnitOfWork:
    """In-memory Unit of Work implementation satisfying the Application UnitOfWork port.

    Provides transaction lifecycle tracking (active, committed, rolled_back) for
    in-memory workflows and testing.

    LIMITATION DISCLOSURE:
    This in-memory implementation does not provide true ACID guarantees or
    database-level isolation/rollback across external storage engines.
    True atomic database transaction management will be implemented with SQLite
    and SQLAlchemy in TASK-006.
    """

    def __init__(self) -> None:
        self.committed: bool = False
        self.rolled_back: bool = False
        self.is_active: bool = False

    async def __aenter__(self) -> "InMemoryUnitOfWork":
        """Enter the transaction boundary."""
        self.is_active = True
        self.committed = False
        self.rolled_back = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool | None:
        """Exit the transaction boundary, triggering rollback if an unhandled error occurred."""
        try:
            if exc_type is not None and not self.committed:
                await self.rollback()
        finally:
            self.is_active = False
        return None

    async def commit(self) -> None:
        """Commit pending changes within the active transaction."""
        if not self.is_active:
            raise RuntimeError("Cannot commit outside an active Unit of Work context.")
        if self.rolled_back:
            raise RuntimeError("Cannot commit a transaction that has been rolled back.")
        self.committed = True

    async def rollback(self) -> None:
        """Roll back pending changes within the active transaction."""
        if not self.is_active:
            raise RuntimeError("Cannot rollback outside an active Unit of Work context.")
        self.rolled_back = True
