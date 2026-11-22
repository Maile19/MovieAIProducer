from fastapi import APIRouter, Query

from backend.app.domain.catalog import (
    ACTING_MATRIX,
    CAMERA_MATRIX,
    COMPOSITION_MATRIX,
    LENS_MATRIX,
    LIGHTING_MATRIX,
    SPEED_MATRIX,
    STYLE_CATALOG,
    get_full_matrix_catalog,
)

router = APIRouter(prefix="/catalog", tags=["Matrix Catalog"])


@router.get("/matrix")
async def get_matrix_catalog(
    category: str | None = Query(
        default=None,
        description="Filter matrix: styles, lighting, acting, cameras, lenses, compositions, speeds",
    ),
):
    """Retrieve Hollywood prompt engineering and cinematography matrix catalog."""
    full = get_full_matrix_catalog()

    if category:
        cat_key = category.lower().strip()
        if cat_key in ("style", "styles"):
            return {"data": {"styles": STYLE_CATALOG}}
        if cat_key in ("light", "lighting"):
            return {"data": {"lighting": LIGHTING_MATRIX}}
        if cat_key in ("act", "acting", "performance"):
            return {"data": {"acting": ACTING_MATRIX}}
        if cat_key in ("cam", "camera", "cameras"):
            return {"data": {"cameras": CAMERA_MATRIX}}
        if cat_key in ("lens", "lenses"):
            return {"data": {"lenses": LENS_MATRIX}}
        if cat_key in ("comp", "composition", "compositions"):
            return {"data": {"compositions": COMPOSITION_MATRIX}}
        if cat_key in ("speed", "speeds", "motion"):
            return {"data": {"speeds": SPEED_MATRIX}}

    return {"data": full}
