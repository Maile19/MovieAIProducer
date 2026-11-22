from fastapi import APIRouter

from backend.app.api.flow import router as flow_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.bible import router as bible_router
from backend.app.api.v1.catalog import router as catalog_router
from backend.app.api.v1.export import router as export_router
from backend.app.api.v1.presets import router as presets_router
from backend.app.api.v1.previews import router as previews_router
from backend.app.api.v1.projects import router as projects_router
from backend.app.api.v1.qc import router as qc_router
from backend.app.api.v1.scenes import router as scenes_router
from backend.app.api.v1.shots import router as shots_router
from backend.app.api.v1.transpile import router as transpile_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(auth_router)
v1_router.include_router(projects_router)
v1_router.include_router(presets_router)
v1_router.include_router(bible_router)
v1_router.include_router(scenes_router)
v1_router.include_router(shots_router)
v1_router.include_router(catalog_router)
v1_router.include_router(transpile_router)
v1_router.include_router(qc_router)
v1_router.include_router(export_router)
v1_router.include_router(previews_router)
v1_router.include_router(flow_router)

__all__ = ["v1_router"]
