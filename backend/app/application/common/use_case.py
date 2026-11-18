from abc import ABC, abstractmethod
from typing import Generic, Protocol, TypeVar, runtime_checkable

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


@runtime_checkable
class UseCase(Protocol[TRequest, TResponse]):
    """Protocol defining an application use case (interactor) contract.

    Encapsulates a specific business scenario orchestrating domain entities
    and application ports with strict input and output boundaries.
    """

    async def execute(self, request: TRequest) -> TResponse:
        """Execute the use case logic asynchronously given a request payload."""
        ...


class BaseUseCase(ABC, Generic[TRequest, TResponse]):
    """Abstract base class implementation of UseCase for convenient subclassing."""

    @abstractmethod
    async def execute(self, request: TRequest) -> TResponse:
        """Subclasses must implement the primary use case workflow."""
        pass
