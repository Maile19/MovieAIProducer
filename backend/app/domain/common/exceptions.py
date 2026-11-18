from typing import Any


class DomainException(Exception):
    """Base exception for all domain-level errors following CDA-0005 taxonomy.

    Attributes:
        message: Safe, human-readable error description.
        code: Unique canonical error code (e.g. DOMAIN_ERROR).
        category: Taxonomy category (business_rule, resource, conflict, etc.).
        details: Additional safe context details for logging or error reporting.
    """

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        category: str = "business_rule",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.category = category
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary representation matching CDA-0005 envelope fields."""
        return {
            "code": self.code,
            "category": self.category,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class EntityNotFoundException(DomainException):
    """Raised when an aggregate root or entity cannot be found by its identity."""

    def __init__(
        self,
        message: str = "Requested resource not found.",
        code: str = "RESOURCE_NOT_FOUND",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            category="resource",
            details=details,
        )


class BusinessRuleValidationException(DomainException):
    """Raised when a business rule constraint is violated within the domain."""

    def __init__(
        self,
        message: str = "Business rule validation failed.",
        code: str = "BUSINESS_RULE_VIOLATION",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            category="business_rule",
            details=details,
        )


class InvariantViolationException(DomainException):
    """Raised when an internal invariant of an aggregate is breached."""

    def __init__(
        self,
        message: str = "Domain invariant violation detected.",
        code: str = "INVARIANT_VIOLATION",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            category="business_rule",
            details=details,
        )


class ConflictException(DomainException):
    """Raised when an operation conflicts with existing domain state (e.g. duplicate identity)."""

    def __init__(
        self,
        message: str = "Domain conflict detected.",
        code: str = "CONFLICT_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            category="conflict",
            details=details,
        )
