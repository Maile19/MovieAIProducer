import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.api.v1.bible import _apply_sheet_overrides
from backend.app.core.config import get_settings
from backend.app.domain.catalog import STYLE_CATALOG
from backend.app.domain.director_rag import DirectorRAGClient
from backend.app.domain.look_dev import LOOK_DEV_PRESETS
from backend.app.domain.screenwriter import PolyaScreenwriterEngine
from backend.app.infrastructure.database.models.character import CharacterModel

NON_LIVE_ACTION_STYLES = {
    "#Style 06",
    "#Style 09",
    "#Style 10",
    "#Style 11",
    "#Style 12",
    "#Style 13",
    "#Style 14",
    "#Style 15",
    "#Style 16",
    "#Style 17",
}


def _create_project(client: TestClient, auth_headers: dict[str, str], style: str = "#Style 01") -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"title": f"Wave2 {uuid.uuid4().hex[:8]}", "target_style_code": style},
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


def _insert_character(project_id: str, name: str = "Ari") -> str:
    settings = get_settings()
    engine = create_engine(f"sqlite:///{settings.database_path}")
    char_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(
            CharacterModel(
                id=char_id,
                project_id=uuid.UUID(project_id),
                name=name,
                role="Protagonist",
                base_prompt="weathered traveler in a charcoal linen coat, amber eyes, old scar over the left brow",
                dna_seed=123456,
                sheet_metadata={},
                sheet_overrides={},
            )
        )
        session.commit()
    engine.dispose()
    return str(char_id)


def test_look_dev_presets_cover_all_18_styles(client: TestClient, auth_headers: dict[str, str]):
    project_id = _create_project(client, auth_headers)
    seen_ids: set[str] = set()

    for entry in STYLE_CATALOG:
        code = entry["code"]
        resp = client.get(
            f"/api/v1/projects/{project_id}/bible/look-dev-presets",
            params={"style_code": code, "include_rag_cues": "false"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["style_code"] == code
        assert body["count"] == 3
        assert len(body["data"]) == 3
        assert body["director_rag_cues"] == ""

        for preset in body["data"]:
            assert preset["preset_id"] not in seen_ids
            seen_ids.add(preset["preset_id"])
            assert len(preset["palette_tokens"]) == 5
            roles = {token["role"] for token in preset["palette_tokens"]}
            assert roles == {
                "Primary Key",
                "Shadow/Depth",
                "Accent/Highlight",
                "Skin/Material Midtone",
                "Atmospheric Wash",
            }
            for token in preset["palette_tokens"]:
                assert token["hex"].startswith("#") and len(token["hex"]) == 7
            if code in NON_LIVE_ACTION_STYLES:
                assert "5219" not in preset["film_stock_or_medium"]

    assert len(seen_ids) == 54
    assert sum(len(presets) for presets in LOOK_DEV_PRESETS.values()) == 54


def test_look_dev_presets_reject_unknown_style_and_foreign_project(
    client: TestClient,
    auth_headers: dict[str, str],
):
    project_id = _create_project(client, auth_headers)
    bad = client.get(
        f"/api/v1/projects/{project_id}/bible/look-dev-presets",
        params={"style_code": "#Style 99", "include_rag_cues": "false"},
        headers=auth_headers,
    )
    assert bad.status_code == 400

    missing = client.get(
        f"/api/v1/projects/{uuid.uuid4()}/bible/look-dev-presets",
        headers=auth_headers,
    )
    assert missing.status_code == 404


def test_look_dev_presets_rag_failure_degrades_gracefully(client: TestClient, auth_headers: dict[str, str]):
    project_id = _create_project(client, auth_headers, "#Style 15")
    with patch.object(DirectorRAGClient, "retrieve", new_callable=AsyncMock) as mock_rag:
        mock_rag.side_effect = TimeoutError("rag offline")
        resp = client.get(
            f"/api/v1/projects/{project_id}/bible/look-dev-presets",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["count"] == 3
    assert resp.json()["director_rag_cues"] == ""


def test_world_prop_variations_returns_three_distinct_options_and_never_mutates_bible(
    client: TestClient, auth_headers: dict[str, str]
):
    project_id = _create_project(client, auth_headers, "#Style 07")

    with patch.object(DirectorRAGClient, "retrieve", new_callable=AsyncMock) as mock_rag, patch.object(
        PolyaScreenwriterEngine, "_call_llm", new_callable=AsyncMock
    ) as mock_llm:
        mock_rag.return_value = {"director_context": "", "shots": [], "grammars": []}
        mock_llm.side_effect = RuntimeError("llm offline")
        resp = client.post(
            f"/api/v1/projects/{project_id}/bible/world-props/variations",
            json={
                "item_type": "environment",
                "code": "#Env 02",
                "current_item": {"code": "#Env 02", "name": "Cliffside Shrine"},
            },
            headers=auth_headers,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["item_type"] == "environment"
    assert body["code"] == "#Env 02"
    variations = body["data"]
    assert len(variations) == 3
    assert {v["label"] for v in variations} == {
        "Atmospheric / Moody",
        "Architectural / Grand Scale",
        "Tactile / Intimate Detail",
    }
    assert len({v["variation_id"] for v in variations}) == 3
    for variation in variations:
        assert variation["code"] == "#Env 02"
        assert variation["name"]
        assert variation["lighting_code"].startswith("#Light ")
        assert variation["visual_description"]
        assert variation["ambient_foley"]

    bible = client.get(f"/api/v1/projects/{project_id}/bible", headers=auth_headers)
    assert bible.status_code == 200
    world_rules = bible.json()["data"].get("world_rules") or {}
    assert not world_rules.get("environments")
    assert not world_rules.get("props")


def test_world_prop_variations_prop_shape_and_validation(client: TestClient, auth_headers: dict[str, str]):
    project_id = _create_project(client, auth_headers)

    with patch.object(DirectorRAGClient, "retrieve", new_callable=AsyncMock) as mock_rag, patch.object(
        PolyaScreenwriterEngine, "_call_llm", new_callable=AsyncMock
    ) as mock_llm:
        mock_rag.return_value = {"director_context": "", "shots": [], "grammars": []}
        mock_llm.side_effect = RuntimeError("llm offline")
        resp = client.post(
            f"/api/v1/projects/{project_id}/bible/world-props/variations",
            json={"item_type": "prop", "code": "#Prop 03"},
            headers=auth_headers,
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) == 3
    for variation in data:
        assert variation["code"] == "#Prop 03"
        assert variation["dramatic_significance"]
        assert variation["visual_details"]

    missing = client.post(
        f"/api/v1/projects/{project_id}/bible/world-props/variations",
        json={"item_type": "environment"},
        headers=auth_headers,
    )
    assert missing.status_code == 422


def test_sheet_override_roundtrip_and_style_sanitized_negative(
    client: TestClient, auth_headers: dict[str, str]
):
    project_id = _create_project(client, auth_headers, "#Style 09")
    character_id = _insert_character(project_id)

    initial = client.get(f"/api/v1/characters/{character_id}/sheet-prompts", headers=auth_headers)
    assert initial.status_code == 200, initial.text
    front = initial.json()["data"]["prompts"]["front"]
    assert front["has_override"] is False
    assert front["effective_prompt"] == front["positive_prompt"]
    assert front["effective_negative_prompt"] == front["negative_prompt"]

    saved = client.put(
        f"/api/v1/projects/{project_id}/characters/{character_id}/sheet-overrides",
        json={
            "slot_key": "front",
            "prompt_override": "CUSTOM FRONT POSITIVE, cinematic hero framing",
            "negative_prompt_override": "watermark, extra fingers, 3d render, cartoon",
        },
        headers=auth_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["has_override"] is True

    refreshed = client.get(f"/api/v1/characters/{character_id}/sheet-prompts", headers=auth_headers)
    assert refreshed.status_code == 200
    front = refreshed.json()["data"]["prompts"]["front"]
    assert front["has_override"] is True
    assert front["prompt_override"] == "CUSTOM FRONT POSITIVE, cinematic hero framing"
    assert front["effective_prompt"] == "CUSTOM FRONT POSITIVE, cinematic hero framing"
    assert "watermark" in front["effective_negative_prompt"]
    assert "3d render" not in front["effective_negative_prompt"].lower()
    assert "cartoon" not in front["effective_negative_prompt"].lower()
    assert "CUSTOM FRONT POSITIVE" in front["copy_ready_text"]

    cleared = client.put(
        f"/api/v1/projects/{project_id}/characters/{character_id}/sheet-overrides",
        json={"slot_key": "front", "prompt_override": None, "negative_prompt_override": None},
        headers=auth_headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["has_override"] is False

    restored = client.get(f"/api/v1/characters/{character_id}/sheet-prompts", headers=auth_headers)
    front = restored.json()["data"]["prompts"]["front"]
    assert front["has_override"] is False
    assert front["effective_prompt"] == front["positive_prompt"]


def test_sheet_override_rejects_cross_project_character(client: TestClient, auth_headers: dict[str, str]):
    project_a = _create_project(client, auth_headers)
    project_b = _create_project(client, auth_headers)
    character_id = _insert_character(project_a)

    resp = client.put(
        f"/api/v1/projects/{project_b}/characters/{character_id}/sheet-overrides",
        json={"slot_key": "front", "prompt_override": "hijack"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_apply_sheet_overrides_helper_uses_compiled_defaults():
    compiled = {"positive_prompt": "COMPILED POS", "negative_prompt": "COMPILED NEG"}

    untouched = _apply_sheet_overrides(compiled, {}, "#Style 01")
    assert untouched["effective_prompt"] == "COMPILED POS"
    assert untouched["effective_negative_prompt"] == "COMPILED NEG"
    assert untouched["has_override"] is False

    overridden = _apply_sheet_overrides(
        compiled,
        {"prompt_override": "NEW POS", "negative_prompt_override": "morphing faces, 5219 film grain"},
        "#Style 01",
    )
    assert overridden["compiled_prompt"] == "COMPILED POS"
    assert overridden["effective_prompt"] == "NEW POS"
    assert "morphing faces" in overridden["effective_negative_prompt"]
    assert "5219" not in overridden["effective_negative_prompt"]
    assert overridden["has_override"] is True

    all_stripped = _apply_sheet_overrides(
        compiled,
        {"negative_prompt_override": "3d render, cartoon"},
        "#Style 09",
    )
    assert all_stripped["effective_negative_prompt"] == ""
    assert all_stripped["has_override"] is True
