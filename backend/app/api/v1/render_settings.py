import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import structlog

from backend.app.core.config import get_settings
from backend.app.infrastructure.universal_image_adapter import (
    UniversalImageAdapter,
    UniversalImageRequest,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["Render Settings"])


def _get_db_path() -> Path:
    settings = get_settings()
    if settings.database_path.is_absolute():
        return settings.database_path
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    candidate = project_root / settings.database_path
    if candidate.parent.exists():
        return candidate
    return Path("movieai_producer.db")


def get_db():
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_render_settings (
            project_id TEXT PRIMARY KEY,
            active_provider_id TEXT NOT NULL,
            apply_to_all_scenes INTEGER NOT NULL DEFAULT 1,
            provider_configs_json TEXT NOT NULL,
            free_portals_json TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def _get_fernet() -> Fernet:
    settings = get_settings()
    secret = (settings.jwt_secret_key or "default-secret-key-32-chars-long!").encode("utf-8")
    derived = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(derived)


def encrypt_key(plain_key: str) -> str:
    if not plain_key or not plain_key.strip():
        return ""
    clean = plain_key.strip()
    if clean.startswith("enc:"):
        return clean
    f = _get_fernet()
    cipher = f.encrypt(clean.encode("utf-8")).decode("utf-8")
    return f"enc:{cipher}"


def decrypt_key(stored_key: str) -> str:
    if not stored_key or not stored_key.strip():
        return ""
    clean = stored_key.strip()
    if not clean.startswith("enc:"):
        return clean
    f = _get_fernet()
    try:
        raw_cipher = clean[4:]
        return f.decrypt(raw_cipher.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("invalid_fernet_token_cannot_decrypt_key", detail="Fernet token invalid or key changed")
        return ""
    except Exception as e:
        logger.warning("failed_decrypting_api_key", error=str(e))
        return ""


def get_project_render_config(project_id: str) -> Optional[dict]:
    """Retrieve project render configuration with active provider, decrypted API key, and settings."""
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM project_render_settings WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        conn.close()
        if not row:
            return None
        raw_configs = {}
        try:
            raw_configs = json.loads(row["provider_configs_json"])
        except Exception:
            raw_configs = {}

        active_prov = row["active_provider_id"]
        cfg = raw_configs.get(active_prov, {})
        stored_key = cfg.get("apiKey", "")
        decrypted_key = decrypt_key(stored_key) if stored_key else ""
        return {
            "project_id": row["project_id"],
            "active_provider_id": active_prov,
            "apply_to_all_scenes": bool(row["apply_to_all_scenes"]),
            "base_url": cfg.get("baseUrl"),
            "api_key": decrypted_key,
            "model_id": cfg.get("modelId"),
            "custom_model_id": cfg.get("customModelId"),
            "configs": raw_configs,
        }
    except Exception as e:
        logger.warning("failed_reading_project_render_config", project_id=project_id, error=str(e))
        return None


def mask_key(key: str) -> str:
    if not key or len(key) < 6:
        return ""
    return f"{key[:4]}••••{key[-4:]}"


class ProviderConfig(BaseModel):
    baseUrl: str
    apiKey: str = ""
    modelId: str
    customModelId: Optional[str] = None


class FreePortal(BaseModel):
    id: str
    name: str
    url: str
    note: Optional[str] = None


class RenderSettingsPayload(BaseModel):
    activeProviderId: str
    applyToAllScenes: bool = True
    configs: Dict[str, ProviderConfig]
    freePortals: List[FreePortal] = []


class TestKeyPayload(BaseModel):
    providerId: str
    baseUrl: str
    apiKey: Optional[str] = ""
    modelId: Optional[str] = None


class UniversalGeneratePayload(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    aspect_ratio: str = "16:9"
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = None
    reference_image_paths: Optional[List[str]] = None
    provider_id_override: Optional[str] = None
    model_id_override: Optional[str] = None


@router.put("/{project_id}/render-provider", status_code=status.HTTP_200_OK)
def save_render_settings(project_id: str, payload: RenderSettingsPayload):
    """Save global AI render provider settings with Fernet key encryption and mask preservation."""
    conn = get_db()
    row = conn.execute(
        "SELECT provider_configs_json FROM project_render_settings WHERE project_id = ?",
        (project_id,),
    ).fetchone()

    existing_configs: Dict[str, Any] = {}
    if row and row["provider_configs_json"]:
        try:
            existing_configs = json.loads(row["provider_configs_json"])
        except Exception:
            existing_configs = {}

    merged_configs: Dict[str, Any] = {}
    for pid, cfg in payload.configs.items():
        cfg_dict = cfg.model_dump()
        input_key = cfg_dict.get("apiKey", "").strip()

        # Preserve existing encrypted key if user passed back a masked string
        if "••••" in input_key and pid in existing_configs:
            cfg_dict["apiKey"] = existing_configs[pid].get("apiKey", "")
        elif input_key:
            # Encrypt new API key
            cfg_dict["apiKey"] = encrypt_key(input_key)
        else:
            cfg_dict["apiKey"] = ""

        merged_configs[pid] = cfg_dict

    conn.execute(
        """
        INSERT INTO project_render_settings
            (project_id, active_provider_id, apply_to_all_scenes, provider_configs_json, free_portals_json, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(project_id) DO UPDATE SET
            active_provider_id = excluded.active_provider_id,
            apply_to_all_scenes = excluded.apply_to_all_scenes,
            provider_configs_json = excluded.provider_configs_json,
            free_portals_json = excluded.free_portals_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            project_id,
            payload.activeProviderId,
            int(payload.applyToAllScenes),
            json.dumps(merged_configs),
            json.dumps([p.model_dump() for p in payload.freePortals]),
        ),
    )
    conn.commit()
    conn.close()

    return {
        "status": "saved",
        "projectId": project_id,
        "activeProviderId": payload.activeProviderId,
        "applyToAllScenes": payload.applyToAllScenes,
    }


@router.get("/{project_id}/render-provider", status_code=status.HTTP_200_OK)
def get_render_settings(project_id: str):
    """Retrieve global AI render provider settings with masked API keys."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM project_render_settings WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    conn.close()

    if not row:
        return {"configured": False, "projectId": project_id}

    raw_configs: Dict[str, Any] = {}
    try:
        raw_configs = json.loads(row["provider_configs_json"])
    except Exception:
        raw_configs = {}

    masked_configs: Dict[str, Any] = {}
    for pid, cfg in raw_configs.items():
        stored_key = cfg.get("apiKey", "")
        decrypted = decrypt_key(stored_key) if stored_key else ""
        masked_configs[pid] = {
            **cfg,
            "apiKey": mask_key(decrypted),
        }

    free_portals: List[Any] = []
    try:
        free_portals = json.loads(row["free_portals_json"])
    except Exception:
        free_portals = []

    return {
        "configured": True,
        "projectId": row["project_id"],
        "activeProviderId": row["active_provider_id"],
        "applyToAllScenes": bool(row["apply_to_all_scenes"]),
        "configs": masked_configs,
        "freePortals": free_portals,
        "updatedAt": row["updated_at"],
    }


@router.post("/{project_id}/render-provider/test-key", status_code=status.HTTP_200_OK)
async def test_render_provider_key(project_id: str, payload: TestKeyPayload):
    """Probe / ping the provider API key & base URL to verify credentials before batch rendering."""
    key_to_use = (payload.apiKey or "").strip()

    # If incoming key is masked or empty, lookup decrypted stored key
    if not key_to_use or "••••" in key_to_use:
        conn = get_db()
        row = conn.execute(
            "SELECT provider_configs_json FROM project_render_settings WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        conn.close()
        if row and row["provider_configs_json"]:
            try:
                configs = json.loads(row["provider_configs_json"])
                stored_key = configs.get(payload.providerId, {}).get("apiKey", "")
                key_to_use = decrypt_key(stored_key)
            except Exception:
                pass

    adapter = UniversalImageAdapter()
    result = await adapter.ping_connection(
        provider_id=payload.providerId,
        base_url=payload.baseUrl,
        api_key=key_to_use,
        model_id=payload.modelId,
    )
    return result


@router.post("/{project_id}/render-provider/generate", status_code=status.HTTP_200_OK)
async def generate_universal_render(project_id: str, payload: UniversalGeneratePayload):
    """Execute image generation using the project's persistent global render provider settings."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM project_render_settings WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    conn.close()

    provider_id = payload.provider_id_override or (row["active_provider_id"] if row else "9router")
    model_id = payload.model_id_override
    base_url = None
    decrypted_key = ""

    if row and row["provider_configs_json"]:
        try:
            configs = json.loads(row["provider_configs_json"])
            prov_cfg = configs.get(provider_id, {})
            base_url = prov_cfg.get("baseUrl")
            if not model_id:
                model_id = prov_cfg.get("modelId")
            stored_key = prov_cfg.get("apiKey", "")
            decrypted_key = decrypt_key(stored_key) if stored_key else ""
        except Exception:
            pass

    adapter = UniversalImageAdapter()
    req = UniversalImageRequest(
        provider_id=provider_id,
        model_id=model_id,
        prompt=payload.prompt,
        negative_prompt=payload.negative_prompt,
        aspect_ratio=payload.aspect_ratio,
        width=payload.width,
        height=payload.height,
        seed=payload.seed,
        reference_image_paths=payload.reference_image_paths,
        base_url_override=base_url,
        api_key_override=decrypted_key,
        enable_fallback=True,
    )

    try:
        gen_res = await adapter.generate_image(req)
        return {
            "status": "success",
            "projectId": project_id,
            "data": gen_res.model_dump(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Generation failed via {provider_id}: {str(exc)}",
        )
