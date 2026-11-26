from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.deps import delete_session_cookie
from backend.app.api.flow import router as flow_router
from backend.app.api.health import router as health_router
from backend.app.api.v1 import v1_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.core.middleware import RequestIDMiddleware
from backend.app.infrastructure.database import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from backend.app.infrastructure.database.base import Base
import backend.app.infrastructure.database.models  # noqa: F401  (register ORM metadata)


def _seed_flow_pool_if_empty(connection) -> None:
    """Idempotently seed Google Flow 6-account registry & default worker settings if empty."""
    inspector = sa_inspect(connection)
    tables = set(inspector.get_table_names())
    if "flow_accounts" in tables:
        acc_count = connection.execute(text("SELECT COUNT(*) FROM flow_accounts")).scalar() or 0
        if acc_count == 0:
            now_dt = datetime.now(timezone.utc)
            today_str = now_dt.strftime("%Y-%m-%d")
            profiles_root = Path("/opt/flow-profiles")
            has_profiles_root = profiles_root.exists() and profiles_root.is_dir()
            for acc_id in range(1, 7):
                profile_dir = f"/opt/flow-profiles/akun_{acc_id}"
                cookies_path = Path(profile_dir) / "Default" / "Cookies"
                if has_profiles_root:
                    acc_status = "active" if (cookies_path.exists() and cookies_path.stat().st_size > 0) else "need_relogin"
                    last_err = (
                        None
                        if acc_status == "active"
                        else f"Profil belum login Google Flow. Jalankan ./scripts/login_flow_profile.sh {acc_id} untuk login."
                    )
                else:
                    acc_status = "active"
                    last_err = None
                connection.execute(
                    text(
                        "INSERT INTO flow_accounts "
                        "(id, label, profile_dir, status, daily_count, last_reset_date, total_count, consecutive_failures, last_error, updated_at) "
                        "VALUES (:id, :label, :profile_dir, :status, 0, :last_reset_date, 0, 0, :last_error, :updated_at)"
                    ),
                    {
                        "id": acc_id,
                        "label": f"Akun Pro {acc_id}",
                        "profile_dir": profile_dir,
                        "status": acc_status,
                        "last_reset_date": today_str,
                        "last_error": last_err,
                        "updated_at": now_dt,
                    },
                )

    if "flow_settings" in tables:
        defaults = {
            "socks5_proxy": "socks5://127.0.0.1:10808",
            "batch_size_per_account": "4",
            "min_delay_sec": "5",
            "max_delay_sec": "12",
            "cooldown_minutes": "15",
            "worker_enabled": "true",
        }
        for k, v in defaults.items():
            connection.execute(
                text("INSERT OR IGNORE INTO flow_settings (key, value) VALUES (:k, :v)"),
                {"k": k, "v": v},
            )


def _ensure_sqlite_schema_sync(connection) -> None:
    """Create missing tables and idempotently add late-added columns on existing SQLite DBs.

    This guard is strictly additive: it never drops or truncates tables/data. It protects
    older production databases from ORM failures when a new mapped column (e.g.
    ``CharacterModel.sheet_overrides``) was added without a prior migration.
    """
    Base.metadata.create_all(connection)

    inspector = sa_inspect(connection)
    if "characters" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("characters")}
        if "sheet_overrides" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE characters "
                    "ADD COLUMN sheet_overrides JSON NOT NULL DEFAULT '{}'"
                )
            )

    _seed_flow_pool_if_empty(connection)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    logger = structlog.get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if "sqlite" in settings.async_database_url:
            settings.database_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
        settings.asset_storage_path.mkdir(
            parents=True,
            exist_ok=True,
        )
        settings.preview_storage_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        db_engine = create_database_engine(settings.async_database_url)
        app.state.db_engine = db_engine
        app.state.session_factory = create_session_factory(db_engine)

        # Bootstrap and verify database connectivity using active engine
        async with db_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        # Additive schema guard for existing SQLite databases (never wipes data).
        if "sqlite" in settings.async_database_url:
            async with db_engine.begin() as connection:
                await connection.run_sync(_ensure_sqlite_schema_sync)

        logger.info(
            "application_started",
            service=settings.service_name,
            environment=settings.app_env,
        )

        yield

        await dispose_database_engine(db_engine)
        logger.info("application_stopped")

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.state.settings = settings

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_host_list,
    )

    app.add_middleware(RequestIDMiddleware)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ):
        request_id = getattr(request.state, "request_id", None)
        headers = dict(exc.headers or {})
        if request_id:
            headers["X-Request-ID"] = request_id

        if isinstance(exc.detail, dict):
            error_code = (
                exc.detail.get("error_code")
                or exc.detail.get("code")
                or ("unauthorized" if exc.status_code == 401 else "http_error")
            )
            raw_msg = exc.detail.get("message") or exc.detail.get("detail")
            if isinstance(raw_msg, str):
                message = raw_msg
            elif isinstance(raw_msg, dict):
                message = raw_msg.get("message") or raw_msg.get("detail") or str(raw_msg)
            elif raw_msg is not None:
                message = str(raw_msg)
            else:
                message = str(exc.detail)

            error_payload = {
                "code": error_code,
                "message": message,
                "request_id": request_id,
            }
            for k, v in exc.detail.items():
                if k not in ("message", "code"):
                    error_payload[k] = v
        else:
            error_payload = {
                "code": "unauthorized" if exc.status_code == 401 else "http_error",
                "message": str(exc.detail) if exc.detail is not None else "An error occurred",
                "request_id": request_id,
            }

        response = JSONResponse(
            status_code=exc.status_code,
            content={"error": error_payload},
            headers=headers,
        )

        # Anti-loop guarantee: automatically clear session cookie on any 401 response
        if exc.status_code == 401:
            delete_session_cookie(response, settings)

        return response

    @app.exception_handler(Exception)
    async def unexpected_exception(
        request: Request,
        exc: Exception,
    ):
        request_id = getattr(request.state, "request_id", None)

        logger.error(
            "unhandled_exception",
            exception_type=type(exc).__name__,
            path=request.url.path,
            request_id=request_id,
        )

        headers = {}
        if request_id:
            headers["X-Request-ID"] = request_id

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred.",
                }
            },
            headers=headers,
        )

    app.include_router(health_router)
    app.include_router(v1_router)
    app.include_router(flow_router)

    return app

app = create_app()
