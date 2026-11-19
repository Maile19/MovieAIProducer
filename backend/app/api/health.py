from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["Health"])

@router.get("/health")
async def liveness():
    return {"status": "alive"}

@router.get("/ready")
async def readiness(request: Request):
    settings = request.app.state.settings
    db_engine = getattr(request.app.state, "db_engine", None)

    checks = {
        "database": False,
        "asset_storage": False,
    }

    if db_engine is not None:
        try:
            async with db_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            checks["database"] = True
        except (SQLAlchemyError, OSError, Exception):
            checks["database"] = False

    try:
        checks["asset_storage"] = (
            settings.asset_storage_path.is_dir()
            and settings.asset_storage_path.exists()
        )
    except OSError:
        pass

    ready = all(checks.values())

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": checks,
        },
    )
