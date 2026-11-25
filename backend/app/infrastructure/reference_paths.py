import os
from pathlib import Path
from typing import Any, List, Optional
import structlog

from backend.app.core.config import get_settings

logger = structlog.get_logger(__name__)


def resolve_url_to_local_path(url: Optional[str]) -> Optional[str]:
    """Resolve an API/web preview URL or relative storage path to an absolute filesystem path.
    Returns the path if and only if it exists on the local filesystem and is a file.
    """
    if not url or not isinstance(url, str):
        return None
    clean = url.split("?")[0].strip()
    if not clean:
        return None

    settings = get_settings()

    # 1. Previews storage
    for prefix in ("/api/v1/assets/previews/", "/assets/previews/"):
        if clean.startswith(prefix):
            fn = clean[len(prefix):]
            p = settings.effective_preview_storage_path / fn
            if p.exists() and p.is_file():
                return str(p.resolve())
            rel_p = Path("./data/assets/previews") / fn
            if rel_p.exists() and rel_p.is_file():
                return str(rel_p.resolve())

    # 2. Temporary previews storage
    for prefix in (
        "/api/v1/assets/temp-previews/",
        "/api/v1/assets/temp_previews/",
        "/assets/temp-previews/",
        "/assets/temp_previews/",
    ):
        if clean.startswith(prefix):
            fn = clean[len(prefix):]
            p = settings.effective_preview_storage_path.parent / "temp_previews" / fn
            if p.exists() and p.is_file():
                return str(p.resolve())
            rel_p = Path("./data/assets/temp_previews") / fn
            if rel_p.exists() and rel_p.is_file():
                return str(rel_p.resolve())

    # 3. Direct filesystem path
    try:
        direct_p = Path(clean)
        if direct_p.exists() and direct_p.is_file():
            return str(direct_p.resolve())
    except Exception:
        pass

    return None


def validate_reference_image_paths(
    background_path: Optional[str] = None,
    char_face_path: Optional[str] = None,
    char_front_path: Optional[str] = None,
    additional_paths: Optional[List[str]] = None,
) -> List[str]:
    """Validates existence of reference images in strict canonical order:
    [background_path, char_face_path, char_front_path, ...additional_paths].
    
    Any file that does not exist or has 0 bytes is cleanly omitted to prevent worker crashes.
    """
    candidates: list[Optional[str]] = [background_path, char_face_path, char_front_path]
    if additional_paths:
        candidates.extend(additional_paths)

    validated: List[str] = []
    for cand in candidates:
        if not cand or not isinstance(cand, str):
            continue
        cand_str = cand.strip()
        if not cand_str:
            continue

        local_path = resolve_url_to_local_path(cand_str)
        if local_path and os.path.exists(local_path) and os.path.isfile(local_path) and os.path.getsize(local_path) > 0:
            validated.append(local_path)
        else:
            logger.debug("omitted_invalid_or_missing_reference_image", candidate=cand_str)

    return validated
