from typing import Any


class ApplicationException(Exception):
    """Base exception for application-layer errors conforming to CDA-0005 taxonomy.

    Attributes:
        message: Human-readable error description.
        code: Canonical uppercase error code.
        category: Error category (internal, validation, authentication, authorization, etc.).
        details: Safe context details dictionary.
    """

    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
        category: str = "internal",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.category = category
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to canonical envelope dictionary representation."""
        return {
            "code": self.code,
            "category": self.category,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ValidationException(ApplicationException):
    """Raised when application input fails syntax or schema validation."""

    def __init__(
        self,
        message: str = "Validation failed for request input.",
        code: str = "VALIDATION_ERROR",
        field_errors: list[dict[str, Any]] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            category="validation",
            details=details,
        )
        self.field_errors = field_errors or []

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["field_errors"] = self.field_errors
        return data


class UnauthorizedException(ApplicationException):
    """Raised when identity authentication fails or is absent."""

    def __init__(
        self,
        message: str = "Authentication required.",
        code: str = "UNAUTHORIZED",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            category="authentication",
            details=details,
        )


class ForbiddenException(ApplicationException):
    """Raised when an authenticated actor lacks permission for an operation."""

    def __init__(
        self,
        message: str = "Action forbidden for caller.",
        code: str = "FORBIDDEN",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            category="authorization",
            details=details,
        )
