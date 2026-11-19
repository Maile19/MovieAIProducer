from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.health import router as health_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.core.middleware import RequestIDMiddleware
from backend.app.infrastructure.database import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)

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

        db_engine = create_database_engine(settings.async_database_url)
        app.state.db_engine = db_engine
        app.state.session_factory = create_session_factory(db_engine)

        # Bootstrap and verify database connectivity using active engine
        async with db_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

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

    return app

app = create_app()
