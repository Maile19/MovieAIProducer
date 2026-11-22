"""Hermes Nova (Polya AI) FastAPI Router.

Provides endpoints for:
1. Dynamic YouTube Trend Archetype Catalog (GET /catalog)
2. 10 YouTube-trend Title Ideation with CTR hooks (POST /ideate-titles)
3. 10 Chained Retention-Optimized Premise Synopses (POST /ideate-synopses)
"""

from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from backend.app.api.deps import get_current_user
from backend.app.domain.hermes_engine import (
    HermesNovaEngine,
    YOUTUBE_TREND_CATALOG,
)
from backend.app.infrastructure.database.models import UserModel

router = APIRouter(prefix="/hermes-nova", tags=["hermes-nova"])


class CatalogItemResponse(BaseModel):
    id: str
    category: str
    trend_tag: str
    target_style_code: str
    target_style_name: str
    aspect_ratio: str
    avg_retention_pacing: str
    suggested_premise_seed: str
    seo_keywords: List[str] = Field(default_factory=list)


class CatalogResponse(BaseModel):
    status: str = "success"
    total: int
    data: List[CatalogItemResponse]


class IdeateTitlesRequest(BaseModel):
    preset_name: str = Field(default="Polya AI Preset", description="Name of the selected preset")
    category: str = Field(default="general", description="Category or genre tag")
    target_style_code: str = Field(default="#Style 01", description="Master Hollywood #Style Code (e.g. #Style 06)")
    target_style_desc: str = Field(default="", description="Visual style summary")
    aspect_ratio: str = Field(default="16:9", description="Framing aspect ratio (16:9, 2.39:1, 9:16)")
    seed_premise: str = Field(default="", description="User input seed premise or logline")


class TitleItem(BaseModel):
    rank: int
    title: str
    slug: str
    trend_hook: str
    target_keywords: List[str]
    hook_score: float


class IdeateTitlesResponse(BaseModel):
    status: str = "success"
    source: str = Field(description="'llm' or 'procedural_fallback'")
    context_summary: str
    recommendations: List[TitleItem]
    seo_description_tags: List[str] = Field(
        default_factory=list,
        description="Aggregated 1-click copy SEO hashtags and keywords for YouTube description",
    )


class IdeateSynopsesRequest(BaseModel):
    locked_title: str = Field(..., description="Chosen production title from Step 1")
    preset_name: str = Field(default="Polya AI Preset")
    target_style_code: str = Field(default="#Style 01")
    aspect_ratio: str = Field(default="16:9")
    seed_premise: str = Field(default="")
    trend_keywords: List[str] = Field(default_factory=list)


class SynopsisItem(BaseModel):
    rank: int = Field(default=1)
    angle_label: str = Field(default="Cinematic Variation")
    synopsis: str = Field(default="High-stakes cinematic narrative premise.")
    retention_hook: str = Field(default="Cold open cliffhanger within opening seconds.")
    target_audience: str = Field(
        default="General YouTube Audience",
        description="Target audience demographic or community",
    )

    @field_validator("target_audience", mode="before")
    @classmethod
    def coerce_target_audience(cls, v: Any) -> str:
        if v is None or v == "":
            return "General YouTube Audience"
        if isinstance(v, list):
            joined = ", ".join(str(x).strip() for x in v if x is not None and str(x).strip())
            return joined or "General YouTube Audience"
        return str(v).strip() or "General YouTube Audience"

    @field_validator("angle_label", mode="before")
    @classmethod
    def coerce_angle_label(cls, v: Any) -> str:
        if v is None or v == "":
            return "Cinematic Variation"
        if isinstance(v, list):
            joined = ", ".join(str(x).strip() for x in v if x is not None and str(x).strip())
            return joined or "Cinematic Variation"
        return str(v).strip() or "Cinematic Variation"

    @field_validator("synopsis", mode="before")
    @classmethod
    def coerce_synopsis(cls, v: Any) -> str:
        if v is None or v == "":
            return "High-stakes cinematic narrative premise."
        if isinstance(v, list):
            joined = ", ".join(str(x).strip() for x in v if x is not None and str(x).strip())
            return joined or "High-stakes cinematic narrative premise."
        return str(v).strip() or "High-stakes cinematic narrative premise."

    @field_validator("retention_hook", mode="before")
    @classmethod
    def coerce_retention_hook(cls, v: Any) -> str:
        if v is None or v == "":
            return "Cold open cliffhanger within opening seconds."
        if isinstance(v, list):
            joined = ", ".join(str(x).strip() for x in v if x is not None and str(x).strip())
            return joined or "Cold open cliffhanger within opening seconds."
        return str(v).strip() or "Cold open cliffhanger within opening seconds."


class IdeateSynopsesResponse(BaseModel):
    status: str = "success"
    source: str = Field(description="'llm' or 'procedural_fallback'")
    locked_title: str
    synopses: List[SynopsisItem]


@router.get("/catalog", response_model=CatalogResponse, status_code=status.HTTP_200_OK)
async def get_trend_catalog(
    current_user: UserModel = Depends(get_current_user),
) -> CatalogResponse:
    """Retrieve verified YouTube trend archetypes for dynamic production initialization."""
    return CatalogResponse(
        status="success",
        total=len(YOUTUBE_TREND_CATALOG),
        data=[CatalogItemResponse(**item) for item in YOUTUBE_TREND_CATALOG],
    )


@router.post("/ideate-titles", response_model=IdeateTitlesResponse, status_code=status.HTTP_200_OK)
async def ideate_titles(
    payload: IdeateTitlesRequest,
    current_user: UserModel = Depends(get_current_user),
) -> IdeateTitlesResponse:
    """Generate 10 structured YouTube-trend title recommendations with CTR hooks."""
    try:
        engine = HermesNovaEngine(timeout=25.0)
        res = await engine.generate_10_titles(
            preset_name=payload.preset_name,
            category=payload.category,
            target_style_code=payload.target_style_code,
            target_style_desc=payload.target_style_desc,
            aspect_ratio=payload.aspect_ratio,
            seed_premise=payload.seed_premise,
        )
        return IdeateTitlesResponse(
            status="success",
            source=res["source"],
            context_summary=res["context_summary"],
            recommendations=[TitleItem(**item) for item in res["recommendations"]],
            seo_description_tags=res.get("seo_description_tags", []),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate title recommendations: {str(exc)}",
        )


@router.post("/ideate-synopses", response_model=IdeateSynopsesResponse, status_code=status.HTTP_200_OK)
async def ideate_synopses(
    payload: IdeateSynopsesRequest,
    current_user: UserModel = Depends(get_current_user),
) -> IdeateSynopsesResponse:
    """Generate 10 chained premise synopses optimized for first 5-second viewer retention."""
    if not payload.locked_title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="locked_title is required to generate premise synopses",
        )

    try:
        engine = HermesNovaEngine(timeout=25.0)
        res = await engine.generate_10_synopses(
            locked_title=payload.locked_title.strip(),
            preset_name=payload.preset_name,
            target_style_code=payload.target_style_code,
            aspect_ratio=payload.aspect_ratio,
            seed_premise=payload.seed_premise,
            trend_keywords=payload.trend_keywords,
        )
        return IdeateSynopsesResponse(
            status="success",
            source=res["source"],
            locked_title=res["locked_title"],
            synopses=[SynopsisItem(**item) for item in res["synopses"]],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate premise synopses: {str(exc)}",
        )
