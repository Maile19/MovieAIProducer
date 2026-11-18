from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class DTO:
    """Base class for all application Data Transfer Objects.

    DTOs carry data between processes or layers without business logic.
    They are pure Python and do not depend on web or database frameworks.
    """
    pass


@dataclass(frozen=True)
class Result(Generic[T]):
    """Explicit Result envelope representing either success or failure of an operation.

    Enforces deterministic handling of operational outcomes without relying solely
    on unhandled exceptions for expected control flow.
    """

    is_success: bool
    value: T | None = None
    error: str | None = None
    error_code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_failure(self) -> bool:
        return not self.is_success

    @classmethod
    def ok(cls, value: T) -> "Result[T]":
        """Construct a successful Result containing a payload value."""
        return cls(is_success=True, value=value)

    @classmethod
    def fail(
        cls,
        error: str,
        code: str = "APPLICATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> "Result[Any]":
        """Construct a failed Result containing error message, code, and details."""
        return cls(
            is_success=False,
            value=None,
            error=error,
            error_code=code,
            details=details or {},
        )

    def unwrap(self) -> T:
        """Return the value if successful, or raise RuntimeError if failure."""
        if not self.is_success:
            raise RuntimeError(
                f"Cannot unwrap failed Result: [{self.error_code}] {self.error}"
            )
        return self.value  # type: ignore[return-value]
