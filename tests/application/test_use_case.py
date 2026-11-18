from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
import pytest

from backend.app.application.common.dtos import DTO, Result
from backend.app.application.common.exceptions import (
    ApplicationException,
    ForbiddenException,
    UnauthorizedException,
    ValidationException,
)
from backend.app.application.common.ports import Clock, EventDispatcher, UnitOfWork
from backend.app.application.common.use_case import BaseUseCase, UseCase
from backend.app.domain.common.event import DomainEvent


@dataclass(frozen=True)
class CreateProjectRequest(DTO):
    name: str


@dataclass(frozen=True)
class CreateProjectResponse(DTO):
    project_id: str
    status: str


class CreateProjectUseCase(BaseUseCase[CreateProjectRequest, Result[CreateProjectResponse]]):
    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    async def execute(self, request: CreateProjectRequest) -> Result[CreateProjectResponse]:
        if not request.name.strip():
            return Result.fail("Project name cannot be empty.", code="VALIDATION_ERROR")
        _now = self.clock.now_utc()
        return Result.ok(
            CreateProjectResponse(
                project_id="proj-123",
                status="created",
            )
        )


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


class DummyDispatcher:
    async def dispatch(self, event: DomainEvent) -> None:
        pass

    async def dispatch_all(self, events: Iterable[DomainEvent]) -> None:
        pass


class DummyUoW:
    async def __aenter__(self) -> "DummyUoW":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool | None:
        return None

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


@pytest.mark.anyio
async def test_use_case_execution():
    clock = SystemClock()
    use_case = CreateProjectUseCase(clock=clock)

    # Verify protocol conformance
    assert isinstance(use_case, UseCase)

    # Successful execution
    res = await use_case.execute(CreateProjectRequest(name="Movie AI"))
    assert res.is_success is True
    assert res.is_failure is False
    assert res.value is not None
    assert res.value.project_id == "proj-123"
    assert res.unwrap().status == "created"

    # Failed execution
    fail_res = await use_case.execute(CreateProjectRequest(name="  "))
    assert fail_res.is_success is False
    assert fail_res.is_failure is True
    assert fail_res.error == "Project name cannot be empty."
    assert fail_res.error_code == "VALIDATION_ERROR"
    with pytest.raises(RuntimeError):
        fail_res.unwrap()


def test_result_envelope_unwrap_with_none():
    """Verify FINDING-001 remediation: Result.ok(None).unwrap() returns None without error."""
    res_none: Result[None] = Result.ok(None)
    assert res_none.is_success is True
    assert res_none.is_failure is False
    assert res_none.unwrap() is None

    # Failed result still raises on unwrap
    res_failed = Result.fail("Execution rejected", code="REJECTED")
    assert res_failed.is_success is False
    assert res_failed.is_failure is True
    with pytest.raises(RuntimeError) as exc_info:
        res_failed.unwrap()
    assert "Cannot unwrap failed Result: [REJECTED] Execution rejected" in str(exc_info.value)


def test_ports_runtime_checkability():
    clock = SystemClock()
    assert isinstance(clock, Clock)

    dispatcher = DummyDispatcher()
    assert isinstance(dispatcher, EventDispatcher)

    uow = DummyUoW()
    assert isinstance(uow, UnitOfWork)


def test_application_exceptions():
    base_app_exc = ApplicationException("Internal fault", code="SYSTEM_FAULT", details={"service": "prod"})
    assert str(base_app_exc) == "[SYSTEM_FAULT] Internal fault"
    assert base_app_exc.category == "internal"
    assert base_app_exc.to_dict()["code"] == "SYSTEM_FAULT"

    val_exc = ValidationException(
        "Invalid schema",
        field_errors=[{"field": "name", "issue": "required"}],
    )
    assert val_exc.category == "validation"
    assert val_exc.to_dict()["field_errors"] == [{"field": "name", "issue": "required"}]

    unauth = UnauthorizedException()
    assert unauth.category == "authentication"
    assert unauth.code == "UNAUTHORIZED"

    forbidden = ForbiddenException()
    assert forbidden.category == "authorization"
    assert forbidden.code == "FORBIDDEN"
