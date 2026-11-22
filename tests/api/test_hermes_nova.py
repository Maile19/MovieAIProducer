"""Unit and integration tests for Hermes Nova (Polya AI) YouTube Trend Engine & Endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.app.domain.hermes_engine import HermesNovaEngine, YOUTUBE_TREND_CATALOG


def test_hermes_nova_catalog_endpoint(client: TestClient, auth_headers: dict[str, str]):
    """Verify that GET /api/v1/hermes-nova/catalog returns canonical YouTube trend archetypes."""
    resp = client.get("/api/v1/hermes-nova/catalog", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["total"] >= 6
    assert len(data["data"]) >= 6

    # Verify canonical style codes and ratios
    ratios = {item["aspect_ratio"] for item in data["data"]}
    assert "16:9" in ratios
    assert "9:16" in ratios  # At least one vertical shorts archetype

    for item in data["data"]:
        assert item["target_style_code"].startswith("#Style ")
        assert int(item["target_style_code"].replace("#Style ", "")) in range(1, 19)
        assert len(item["trend_tag"]) > 0
        assert len(item["suggested_premise_seed"]) > 0


def test_hermes_nova_ideate_titles_endpoint(client: TestClient, auth_headers: dict[str, str]):
    """Verify that POST /api/v1/hermes-nova/ideate-titles returns exactly 10 recommendations."""
    payload = {
        "preset_name": "Custom Sci-Fi Anime",
        "category": "anime",
        "target_style_code": "#Style 15",
        "target_style_desc": "Anime (Shinkai / Ufotable)",
        "aspect_ratio": "16:9",
        "seed_premise": "A lone mecha pilot uncovers a sentient cosmic signal.",
    }
    resp = client.post("/api/v1/hermes-nova/ideate-titles", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["source"] in ("llm", "procedural_fallback")
    recs = data["recommendations"]
    assert len(recs) == 10
    assert "seo_description_tags" in data
    assert isinstance(data["seo_description_tags"], list)
    assert len(data["seo_description_tags"]) >= 1

    for idx, rec in enumerate(recs, start=1):
        assert rec["rank"] == idx
        assert len(rec["title"]) > 0
        assert len(rec["slug"]) > 0
        assert "-" in rec["slug"] or len(rec["slug"].split()) == 1
        assert len(rec["trend_hook"]) > 0
        assert len(rec["target_keywords"]) >= 1
        assert 8.0 <= rec["hook_score"] <= 10.0


def test_hermes_nova_ideate_synopses_endpoint(client: TestClient, auth_headers: dict[str, str]):
    """Verify that POST /api/v1/hermes-nova/ideate-synopses returns exactly 10 premise variations."""
    payload = {
        "locked_title": "Signal of the Iron Nebula",
        "preset_name": "Custom Sci-Fi Anime",
        "target_style_code": "#Style 15",
        "aspect_ratio": "16:9",
        "seed_premise": "A lone mecha pilot uncovers a sentient cosmic signal.",
        "trend_keywords": ["Mecha", "Nebula", "SciFi Anime"],
    }
    resp = client.post("/api/v1/hermes-nova/ideate-synopses", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["source"] in ("llm", "procedural_fallback")
    assert data["locked_title"] == "Signal of the Iron Nebula"
    synopses = data["synopses"]
    assert len(synopses) == 10

    for idx, syn in enumerate(synopses, start=1):
        assert syn["rank"] == idx
        assert len(syn["angle_label"]) > 0
        assert len(syn["synopsis"]) > 20
        assert len(syn["retention_hook"]) > 0
        assert len(syn["target_audience"]) > 0


@pytest.mark.anyio
async def test_hermes_nova_engine_procedural_fallback_direct():
    """Verify HermesNovaEngine direct procedural fallback when LLM base url is unreachable."""
    engine = HermesNovaEngine(base_url="http://127.0.0.1:99999/invalid", timeout=1.0)
    
    # Titles fallback
    titles_res = await engine.generate_10_titles(
        preset_name="Test Preset",
        category="fantasy",
        target_style_code="#Style 07",
        seed_premise="An inquisitor and a cursed child.",
    )
    assert titles_res["source"] == "procedural_fallback"
    assert len(titles_res["recommendations"]) == 10
    assert titles_res["recommendations"][0]["rank"] == 1
    assert "seo_description_tags" in titles_res
    assert len(titles_res["seo_description_tags"]) >= 1

    # Synopses fallback
    synopses_res = await engine.generate_10_synopses(
        locked_title="Cursed Child of the Frost",
        preset_name="Test Preset",
        target_style_code="#Style 07",
        seed_premise="An inquisitor and a cursed child.",
    )
    assert synopses_res["source"] == "procedural_fallback"
    assert len(synopses_res["synopses"]) == 10
    assert "Cursed Child of the Frost" in synopses_res["synopses"][0]["synopsis"]


def test_synopsis_item_default_fallback_and_coercion():
    """Verify SynopsisItem model gracefully defaults when fields are omitted or passed as lists."""
    from backend.app.api.v1.hermes_nova import SynopsisItem

    # 1. Missing target_audience (mimics live incident payload)
    raw_item = {
        "rank": 5,
        "angle_label": "Bio-Synthetic Fusion",
        "synopsis": "A cybernetic mechanic discovers an organic core fused to a decommissioned war engine.",
        "retention_hook": "Explosive cold open in first 3 seconds",
    }
    item = SynopsisItem(**raw_item)
    assert item.rank == 5
    assert item.target_audience == "General YouTube Audience"
    assert item.angle_label == "Bio-Synthetic Fusion"

    # 2. List-to-string coercion on all validated fields
    list_item = {
        "rank": 2,
        "angle_label": ["High Retention", "Sci-Fi Thriller"],
        "synopsis": ["Part one of the premise.", "Part two with higher stakes."],
        "retention_hook": ["Opening blast", "5-second cliffhanger"],
        "target_audience": ["Cyberpunk Fans", "Lore Theorists"],
    }
    coerced = SynopsisItem(**list_item)
    assert coerced.angle_label == "High Retention, Sci-Fi Thriller"
    assert coerced.synopsis == "Part one of the premise., Part two with higher stakes."
    assert coerced.retention_hook == "Opening blast, 5-second cliffhanger"
    assert coerced.target_audience == "Cyberpunk Fans, Lore Theorists"


@pytest.mark.anyio
async def test_hermes_nova_engine_normalization_guardrails():
    """Verify HermesNovaEngine normalization for missing target_audience, targetAudience alias, lists, and non-dicts."""
    from unittest.mock import AsyncMock, patch

    engine = HermesNovaEngine()

    mock_llm_items = [
        {"angle_label": "Angle 1", "synopsis": "Synopsis 1", "retention_hook": "Hook 1"},  # missing target_audience
        {"angle_label": "Angle 2", "synopsis": "Synopsis 2", "retention_hook": "Hook 2", "targetAudience": "CamelCase Audience"},
        {"angle_label": "Angle 3", "synopsis": "Synopsis 3", "retention_hook": "Hook 3", "target_demographic": "Demographic Audience"},
        {"angle_label": ["List", "Angle"], "synopsis": ["List", "Synopsis"], "retention_hook": ["List", "Hook"], "target_audience": ["List", "Audience"]},
        "Repaired string-only item premise",  # non-dict repairable element
        {"angle_label": "Angle 6", "synopsis": "Synopsis 6", "retention_hook": "Hook 6", "audience": "Short Audience Key"},
        {"angle_label": "Angle 7", "synopsis": "Synopsis 7", "retention_hook": "Hook 7", "demographic": "Young Adults"},
        {"angle_label": "Angle 8", "synopsis": "Synopsis 8", "retention_hook": "Hook 8", "target": "Sci-Fi Gamers"},
        {"angle_label": "Angle 9", "synopsis": "Synopsis 9", "retention_hook": "Hook 9", "target_audience": "Standard Audience"},
        {"angle_label": "Angle 10", "synopsis": "Synopsis 10", "retention_hook": "Hook 10", "target_audience": "Ending Audience"},
        {"angle_label": "Angle 11", "synopsis": "Synopsis 11", "retention_hook": "Hook 11", "target_audience": "Surplus Audience"},
    ]

    with patch.object(engine, "_call_llm", new=AsyncMock(return_value=({"synopses": mock_llm_items}, "llm"))):
        res = await engine.generate_10_synopses(
            locked_title="Neon Nexus",
            preset_name="Cyberpunk SciFi",
            target_style_code="#Style 06",
            seed_premise="A rogue netrunner encounters an anomaly.",
        )

    assert res["source"] == "llm"
    assert res["locked_title"] == "Neon Nexus"
    synopses = res["synopses"]
    assert len(synopses) == 10

    # Item 1: missing target_audience defaulted
    assert synopses[0]["rank"] == 1
    assert synopses[0]["target_audience"] == "General YouTube Audience"

    # Item 2: camelCase targetAudience mapped
    assert synopses[1]["rank"] == 2
    assert synopses[1]["target_audience"] == "CamelCase Audience"

    # Item 3: target_demographic mapped
    assert synopses[2]["rank"] == 3
    assert synopses[2]["target_audience"] == "Demographic Audience"

    # Item 4: list coercion to comma-separated string
    assert synopses[3]["rank"] == 4
    assert synopses[3]["target_audience"] == "List, Audience"
    assert synopses[3]["angle_label"] == "List, Angle"
    assert synopses[3]["synopsis"] == "List, Synopsis"
    assert synopses[3]["retention_hook"] == "List, Hook"

    # Item 5: string-only repaired element
    assert synopses[4]["rank"] == 5
    assert synopses[4]["synopsis"] == "Repaired string-only item premise"
    assert synopses[4]["target_audience"] == "General YouTube Audience"
