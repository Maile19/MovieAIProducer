from datetime import datetime, timezone
import subprocess
from typing import Any, Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.app.api.deps import get_current_user, get_session
from backend.app.core.proxy_health import DEFAULT_SOCKS5_URL, check_socks5_health, get_cached_socks5_health
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.flow import (
    FlowAccountModel,
    FlowImageJobModel,
    FlowSettingModel,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/flow", tags=["Google Flow Automation Pool"])


# ==============================================================================
# Request / Response Schemas
# ==============================================================================
class FlowJobCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Prompt visual scene untuk di-generate Google Flow")
    aspect_ratio: str = Field(default="16:9", description="Rasio aspek: 16:9, 3:4, 1:1, 9:16, atau 4:3")
    reference_image_paths: list[str] | None = Field(default=None, description="Path lokal gambar referensi")
    project_id: uuid.UUID | None = Field(default=None, description="Project ID konteks")
    scene_id: uuid.UUID | None = Field(default=None, description="Scene ID konteks")
    shot_id: uuid.UUID | None = Field(default=None, description="Shot ID konteks spesifik")
    preferred_account_id: int | None = Field(default=None, ge=1, le=6, description="Nomor akun spesifik (1-6)")


class FlowAccountPatchRequest(BaseModel):
    label: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, description="'active' atau 'disabled'")


class FlowSettingsUpdateRequest(BaseModel):
    socks5_proxy: str | None = None
    batch_size_per_account: int | None = Field(default=None, ge=1, le=20)
    min_delay_sec: int | None = Field(default=None, ge=1, le=60)
    max_delay_sec: int | None = Field(default=None, ge=2, le=120)
    cooldown_minutes: int | None = Field(default=None, ge=1, le=1440)
    worker_enabled: bool | None = None
    target_resolution: Literal["1k", "2k", "4k"] | None = None


def _normalize_target_resolution(value: str | None) -> str:
    norm = (value or "2k").strip().lower()
    return norm if norm in ("1k", "2k", "4k") else "2k"


# ==============================================================================
# Helper functions
# ==============================================================================
def get_worker_service_status() -> str:
    """Check systemd status of flow-image-worker.service."""
    try:
        res = subprocess.run(
            ["systemctl", "is-active", "flow-image-worker.service"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        return res.stdout.strip() or "inactive"
    except Exception:
        return "unknown"


# ==============================================================================
# Endpoints
# ==============================================================================
@router.get("/proxy/status", status_code=status.HTTP_200_OK)
async def get_proxy_status(
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Check live connectivity and RFC 1928 handshake to the Android SOCKS5 proxy."""
    stmt = select(FlowSettingModel).where(FlowSettingModel.key == "socks5_proxy")
    res = await session.execute(stmt)
    setting = res.scalar_one_or_none()
    proxy_url = setting.value if setting and setting.value else DEFAULT_SOCKS5_URL
    return get_cached_socks5_health(proxy_url, ttl_seconds=5.0)


@router.post("/images/generate", status_code=status.HTTP_201_CREATED)
async def create_flow_job(
    request: FlowJobCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Enqueue a new image generation job for Google Flow worker."""
    # Pre-Flight SOCKS5 Fail-Fast Check (with 3s cache to prevent contention)
    stmt_proxy = select(FlowSettingModel).where(FlowSettingModel.key == "socks5_proxy")
    res_proxy = await session.execute(stmt_proxy)
    setting_proxy = res_proxy.scalar_one_or_none()
    proxy_url = setting_proxy.value if setting_proxy and setting_proxy.value else DEFAULT_SOCKS5_URL

    health = get_cached_socks5_health(proxy_url, ttl_seconds=3.0)
    if not health["healthy"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "SOCKS5_PROXY_OFFLINE",
                "message": f"Proxy SOCKS5 Android ({health['proxy_url']}) sedang offline. Pastikan aplikasi SOCKS5 / reverse tunnel di HP Android sudah aktif.",
                "proxy_detail": health["detail"],
            },
        )

    valid_aspect_ratios = ["16:9", "3:4", "1:1", "9:16", "4:3"]
    aspect_ratio = request.aspect_ratio if request.aspect_ratio in valid_aspect_ratios else "16:9"

    job = FlowImageJobModel(
        id=uuid.uuid4(),
        project_id=request.project_id,
        scene_id=request.scene_id,
        shot_id=request.shot_id,
        prompt=request.prompt.strip(),
        aspect_ratio=aspect_ratio,
        reference_image_paths=request.reference_image_paths,
        preferred_account_id=request.preferred_account_id,
        status="queued",
        retry_count=0,
        max_retries=3,
        created_at=datetime.now(timezone.utc),
    )

    try:
        session.add(job)
        await session.commit()
        await session.refresh(job)
    except Exception as exc:
        await session.rollback()
        logger.error("flow_job_enqueue_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "ENQUEUE_FAILED",
                "message": f"Gagal memasukkan job ke antrean Flow: {str(exc)}",
            },
        )

    logger.info(
        "flow_job_enqueued",
        job_id=str(job.id),
        user_id=str(current_user.id),
        prompt=job.prompt[:50],
    )

    return {
        "status": "success",
        "job_id": str(job.id),
        "job_status": job.status,
        "message": "Job successfully placed into Google Flow queue.",
    }


@router.get("/images/jobs/{job_id}", status_code=status.HTTP_200_OK)
async def get_flow_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current status, output image URL, and debug info of a specific flow job."""
    stmt = select(FlowImageJobModel).where(FlowImageJobModel.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found.",
        )

    return {
        "id": str(job.id),
        "project_id": str(job.project_id) if job.project_id else None,
        "scene_id": str(job.scene_id) if job.scene_id else None,
        "prompt": job.prompt,
        "aspect_ratio": job.aspect_ratio,
        "status": job.status,
        "assigned_account_id": job.assigned_account_id,
        "output_filename": job.output_filename,
        "image_url": job.image_url,
        "debug_screenshot_url": job.debug_screenshot_url,
        "error_message": job.error_message,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.post("/images/jobs/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_flow_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel a flow job in queue or processing state to prevent zombie jobs."""
    stmt = select(FlowImageJobModel).where(FlowImageJobModel.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found.",
        )

    if job.status in ("completed", "failed", "cancelled"):
        return {
            "status": job.status,
            "message": f"Job {job_id} is already in terminal state '{job.status}'.",
        }

    job.status = "cancelled"
    job.error_message = "Cancelled by client timeout or user abort"
    job.completed_at = datetime.now(timezone.utc)
    await session.commit()

    logger.info(
        "flow_job_cancelled",
        job_id=str(job.id),
        user_id=str(current_user.id),
    )

    return {
        "status": "cancelled",
        "job_id": str(job.id),
        "message": "Job successfully cancelled.",
    }


@router.get("/images/jobs", status_code=status.HTTP_200_OK)
async def list_recent_jobs(
    limit: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """List recent flow generation jobs for monitoring."""
    stmt = (
        select(FlowImageJobModel)
        .order_by(FlowImageJobModel.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    jobs = result.scalars().all()

    return {
        "jobs": [
            {
                "id": str(j.id),
                "project_id": str(j.project_id) if j.project_id else None,
                "scene_id": str(j.scene_id) if j.scene_id else None,
                "prompt": j.prompt,
                "aspect_ratio": j.aspect_ratio,
                "status": j.status,
                "assigned_account_id": j.assigned_account_id,
                "image_url": j.image_url,
                "debug_screenshot_url": j.debug_screenshot_url,
                "error_message": j.error_message,
                "retry_count": j.retry_count,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]
    }


@router.get("/accounts", status_code=status.HTTP_200_OK)
async def list_accounts(
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """List all 6 accounts in the Google Flow pool with their real-time state."""
    stmt = select(FlowAccountModel).order_by(FlowAccountModel.id.asc())
    result = await session.execute(stmt)
    accounts = result.scalars().all()

    worker_status = get_worker_service_status()

    return {
        "worker_service": {
            "name": "flow-image-worker.service",
            "status": worker_status,
            "healthy": worker_status == "active",
        },
        "accounts": [
            {
                "id": a.id,
                "label": a.label,
                "profile_dir": a.profile_dir,
                "status": a.status,
                "cooldown_until": a.cooldown_until.isoformat() if a.cooldown_until else None,
                "daily_count": a.daily_count,
                "total_count": a.total_count,
                "consecutive_failures": a.consecutive_failures,
                "last_error": a.last_error,
                "last_used_at": a.last_used_at.isoformat() if a.last_used_at else None,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
            for a in accounts
        ],
    }


@router.patch("/accounts/{account_id}", status_code=status.HTTP_200_OK)
async def update_account(
    account_id: int,
    patch: FlowAccountPatchRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Update label or toggle active/disabled for an account."""
    stmt = select(FlowAccountModel).where(FlowAccountModel.id == account_id)
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account #{account_id} not found.",
        )

    if patch.label is not None:
        account.label = patch.label.strip()

    if patch.status is not None:
        if patch.status in ["active", "disabled"]:
            account.status = patch.status
            if patch.status == "active":
                account.consecutive_failures = 0
                account.cooldown_until = None
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status only accepts 'active' or 'disabled'.",
            )

    account.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(account)

    return {
        "status": "success",
        "account": {
            "id": account.id,
            "label": account.label,
            "status": account.status,
            "daily_count": account.daily_count,
            "total_count": account.total_count,
        },
    }


@router.post("/accounts/{account_id}/reset", status_code=status.HTTP_200_OK)
async def reset_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Reset account back to 'active' status and clear failures/cooldown (used after relogin)."""
    stmt = select(FlowAccountModel).where(FlowAccountModel.id == account_id)
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account #{account_id} not found.",
        )

    account.status = "active"
    account.cooldown_until = None
    account.consecutive_failures = 0
    account.last_error = None
    account.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(account)

    return {
        "status": "success",
        "message": f"Account #{account_id} reset to active successfully.",
        "account": {
            "id": account.id,
            "label": account.label,
            "status": account.status,
        },
    }


@router.post("/accounts/{account_id}/test", status_code=status.HTTP_201_CREATED)
async def test_account_generate(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit a lightweight test job assigned specifically to this account."""
    # Pre-Flight SOCKS5 Fail-Fast Check
    stmt_proxy = select(FlowSettingModel).where(FlowSettingModel.key == "socks5_proxy")
    res_proxy = await session.execute(stmt_proxy)
    setting_proxy = res_proxy.scalar_one_or_none()
    proxy_url = setting_proxy.value if setting_proxy and setting_proxy.value else DEFAULT_SOCKS5_URL

    health = check_socks5_health(proxy_url)
    if not health["healthy"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "SOCKS5_PROXY_OFFLINE",
                "message": f"Proxy SOCKS5 Android ({health['proxy_url']}) sedang offline. Pastikan aplikasi SOCKS5 / reverse tunnel di HP Android sudah aktif.",
                "proxy_detail": health["detail"],
            },
        )

    stmt = select(FlowAccountModel).where(FlowAccountModel.id == account_id)
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account #{account_id} not found.",
        )

    test_prompt = (
        f"Cinematic keyframe, golden hour lighting on mountain peaks, "
        f"8k resolution photorealistic test render for {account.label}."
    )

    job = FlowImageJobModel(
        id=uuid.uuid4(),
        prompt=test_prompt,
        aspect_ratio="16:9",
        preferred_account_id=account_id,
        status="queued",
        retry_count=0,
        max_retries=2,
        created_at=datetime.now(timezone.utc),
    )

    try:
        session.add(job)
        await session.commit()
        await session.refresh(job)
    except Exception as exc:
        await session.rollback()
        logger.error("flow_job_enqueue_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "ENQUEUE_FAILED",
                "message": f"Gagal memasukkan job ke antrean Flow: {str(exc)}",
            },
        )

    return {
        "status": "success",
        "message": f"Test job enqueued specifically for {account.label}.",
        "job_id": str(job.id),
        "preferred_account_id": account_id,
    }


@router.get("/settings", status_code=status.HTTP_200_OK)
async def get_settings_endpoint(
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Read dynamic key-value settings for Google Flow worker."""
    stmt = select(FlowSettingModel)
    result = await session.execute(stmt)
    settings = result.scalars().all()

    data = {s.key: s.value for s in settings}
    return {
        "settings": {
            "socks5_proxy": data.get("socks5_proxy") or DEFAULT_SOCKS5_URL,
            "batch_size_per_account": int(data.get("batch_size_per_account", 1)),
            "min_delay_sec": int(data.get("min_delay_sec", 5)),
            "max_delay_sec": int(data.get("max_delay_sec", 12)),
            "cooldown_minutes": int(data.get("cooldown_minutes", 15)),
            "worker_enabled": data.get("worker_enabled", "true").lower() == "true",
            "target_resolution": _normalize_target_resolution(data.get("target_resolution")),
        }
    }


@router.put("/settings", status_code=status.HTTP_200_OK)
async def update_settings_endpoint(
    patch: FlowSettingsUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Update dynamic settings in database for Google Flow worker."""
    updates: dict[str, str] = {}
    if patch.socks5_proxy is not None:
        updates["socks5_proxy"] = patch.socks5_proxy.strip()
    if patch.batch_size_per_account is not None:
        updates["batch_size_per_account"] = str(patch.batch_size_per_account)
    if patch.min_delay_sec is not None:
        updates["min_delay_sec"] = str(patch.min_delay_sec)
    if patch.max_delay_sec is not None:
        updates["max_delay_sec"] = str(patch.max_delay_sec)
    if patch.cooldown_minutes is not None:
        updates["cooldown_minutes"] = str(patch.cooldown_minutes)
    if patch.worker_enabled is not None:
        updates["worker_enabled"] = "true" if patch.worker_enabled else "false"
    if patch.target_resolution is not None:
        updates["target_resolution"] = _normalize_target_resolution(patch.target_resolution)

    for key, value in updates.items():
        stmt = select(FlowSettingModel).where(FlowSettingModel.key == key)
        res = await session.execute(stmt)
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            session.add(FlowSettingModel(key=key, value=value))

    await session.commit()

    # Return updated values
    stmt = select(FlowSettingModel)
    result = await session.execute(stmt)
    all_settings = result.scalars().all()
    data = {s.key: s.value for s in all_settings}

    return {
        "status": "success",
        "settings": {
            "socks5_proxy": data.get("socks5_proxy") or DEFAULT_SOCKS5_URL,
            "batch_size_per_account": int(data.get("batch_size_per_account", 1)),
            "min_delay_sec": int(data.get("min_delay_sec", 5)),
            "max_delay_sec": int(data.get("max_delay_sec", 12)),
            "cooldown_minutes": int(data.get("cooldown_minutes", 15)),
            "worker_enabled": data.get("worker_enabled", "true").lower() == "true",
            "target_resolution": _normalize_target_resolution(data.get("target_resolution")),
        },
    }
