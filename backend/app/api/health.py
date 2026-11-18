import sqlite3

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])

@router.get("/health")
async def liveness():
    return {"status": "alive"}

@router.get("/ready")
async def readiness(request: Request):
    settings = request.app.state.settings

    checks = {
        "database": False,
        "asset_storage": False,
    }

    try:
        with sqlite3.connect(
            str(settings.database_path),
            timeout=2,
        ) as connection:
            connection.execute("SELECT 1")
        checks["database"] = True
    except (sqlite3.Error, OSError):
        pass

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
