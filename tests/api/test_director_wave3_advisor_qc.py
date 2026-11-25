import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.domain.catalog import validate_matrix_code
from backend.app.domain.director_rag import DirectorRAGClient
from backend.app.domain.screenwriter import PolyaScreenwriterEngine
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.story import ShotModel


def _create_project(client: TestClient, auth_headers: dict[str, str], style: str = "#Style 02") -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"title": f"Wave3 {uuid.uuid4().hex[:8]}", "target_style_code": style},
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


def _create_scene(
    client: TestClient,
    auth_headers: dict[str, str],
    project_id: str,
    act_number: int = 1,
    scene_number: int = 1,
    slugline: str = "INT. OBSERVATORY LAB - NIGHT",
    narrative_goal: str = "Elena inspects the cracked brass astrolabe.",
) -> str:
    resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={
            "act_number": act_number,
            "scene_number": scene_number,
            "slugline": slugline,
            "narrative_goal": narrative_goal,
            "duration_target": 5.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


def _create_shot(
    client: TestClient,
    auth_headers: dict[str, str],
    scene_id: str,
    shot_number: int = 1,
    camera_code: str = "#Cam 01",
    light_code: str = "#Light 03",
    speed_code: str = "#Speed 02",
    transition_type: str = "J_CUT",
    dialogue: str | None = "Stay behind the glass.",
) -> str:
    resp = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={
            "shot_number": shot_number,
            "duration_seconds": 5.0,
            "camera_code": camera_code,
            "lens_code": "#Lens 01",
            "comp_code": "#Comp 01",
            "light_code": light_code,
            "act_code": "#Act 01",
            "speed_code": speed_code,
            "transition_type": transition_type,
            "dialogue": dialogue,
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


def _insert_character_with_states(
    project_id: str,
    name: str = "Elena",
    voice_dna: str | None = "Measured alto, crisp pauses, dry restraint",
    dna_seed: int | None = 445566,
    base_prompt: str = "34yo astrophysicist in navy wool trenchcoat, silver hair clasp",
    with_ref: bool = True,
    states: list[tuple[str, str]] | None = None,
) -> str:
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
                base_prompt=base_prompt,
                voice_dna_profile=voice_dna,
                dna_seed=dna_seed,
                closeup_image_url="/api/v1/assets/elena_cu.webp" if with_ref else None,
                sheet_metadata={},
                sheet_overrides={},
            )
        )
        for st_code, wardrobe in (states if states is not None else [("#State 01", "Navy trenchcoat, pristine")]):
            session.add(
                CharacterStateModel(
                    id=uuid.uuid4(),
                    character_id=char_id,
                    state_code=st_code,
                    state_label=st_code,
                    wardrobe=wardrobe,
                    injuries_and_wear="None",
                    expression_anchor="Focused gaze",
                )
            )
        session.commit()
    engine.dispose()
    return str(char_id)


def test_director_advisor_returns_valid_matrix_codes_with_bible_and_rag_cues(
    client: TestClient, auth_headers: dict[str, str]
):
    project_id = _create_project(client, auth_headers, "#Style 02")
    _insert_character_with_states(
        project_id,
        name="Elena",
        states=[("#State 01", "Navy trenchcoat"), ("#State 02", "Dust-stained navy trenchcoat")],
    )
    client.put(
        f"/api/v1/projects/{project_id}/bible",
        json={
            "world_rules": {
                "environments": [
                    {"code": "#Env 01", "name": "Observatory Lab", "lighting_code": "#Light 03"}
                ],
                "props": [
                    {"code": "#Prop 01", "name": "Brass Astrolabe", "owner_character": "Elena"}
                ],
                "continuity_rules": ["Preserve Elena silver hair clasp on left temple."],
                "negative_prompts": ["cartoon, anime cel shading"],
            }
        },
        headers=auth_headers,
    )
    scene_id = _create_scene(
        client,
        auth_headers,
        project_id,
        act_number=2,
        scene_number=1,
        slugline="INT. OBSERVATORY LAB - NIGHT",
        narrative_goal="Elena calibrates the Brass Astrolabe under low tungsten light.",
    )
    shot_id = _create_shot(client, auth_headers, scene_id, camera_code="#Cam 02", light_code="#Light 03")

    fake_rag = {
        "director_context": "Use motivated practical key light with anamorphic edge flare.",
        "shots": [{"shot_id": "s1", "matrix_codes": {"camera_code": "#Cam 04"}}],
        "grammars": [{"title": "Observatory Tension", "pacing_curve": "Slow build"}],
    }
    fake_llm = {
        "recommendations": [
            {
                "axis": "optics",
                "title": "Anamorphic Tight Push",
                "rationale": "Builds claustrophobic focus on the Brass Astrolabe.",
                "camera_code": "#Cam 99",  # intentionally bogus to verify coercion to catalog code
                "lens_code": "#Lens 01",
                "comp_code": "#Comp 05",
                "light_code": "#Light 03",
                "act_code": "#Act 04",
                "speed_code": "#Speed 02",
                "transition_type": "J_CUT",
                "continuity_warnings": ["Keep clasp on left temple."],
            },
            {
                "axis": "staging",
                "title": "Over-Shoulder Calibration",
                "rationale": "Preserves eyeline toward instrumentation.",
                "camera_code": "#Cam 07",
                "lens_code": "#Lens 03",
                "comp_code": "#Comp 01",
                "light_code": "#Light 03",
                "act_code": "#Act 01",
                "speed_code": "#Speed 01",
                "transition_type": "L_CUT",
            },
            {
                "axis": "lighting",
                "title": "Tungsten Edge Accent",
                "rationale": "Separates silhouette from obsidian glass.",
                "camera_code": "#Cam 04",
                "lens_code": "#Lens 02",
                "comp_code": "#Comp 04",
                "light_code": "#Light 05",
                "act_code": "#Act 01",
                "speed_code": "#Speed 03",
                "transition_type": "HARD_CUT",
            },
        ]
    }

    with patch.object(DirectorRAGClient, "retrieve", new_callable=AsyncMock, return_value=fake_rag), patch.object(
        PolyaScreenwriterEngine, "_call_llm", new_callable=AsyncMock, return_value=fake_llm
    ):
        resp = client.post(
            f"/api/v1/projects/{project_id}/scenes/{scene_id}/director-advisor",
            json={"shot_id": shot_id, "focus": "all", "include_rag": True},
            headers=auth_headers,
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["source"] == "llm_rag"
    assert data["director_rag_hits"] == 2
    assert data["shot_id"] == shot_id
    assert data["bible_anchors"]["matched_character"] == "Elena"
    assert data["bible_anchors"]["active_state_code"] == "#State 02"
    assert data["bible_anchors"]["matched_environment"] == "#Env 01"
    assert "#Prop 01" in data["bible_anchors"]["matched_props"]

    recs = data["recommendations"]
    assert len(recs) == 3
    for rec in recs:
        assert validate_matrix_code("cam", rec["camera_code"]) == rec["camera_code"]
        assert validate_matrix_code("lens", rec["lens_code"]) == rec["lens_code"]
        assert validate_matrix_code("comp", rec["comp_code"]) == rec["comp_code"]
        assert validate_matrix_code("light", rec["light_code"]) == rec["light_code"]
        assert validate_matrix_code("act", rec["act_code"]) == rec["act_code"]
        assert validate_matrix_code("speed", rec["speed_code"]) == rec["speed_code"]
        assert rec["camera_code"] != "#Cam 99"

    # Non-destructive: original shot camera_code remains #Cam 02
    shot_after = client.get(f"/api/v1/shots/{shot_id}", headers=auth_headers)
    assert shot_after.status_code == 200
    assert shot_after.json()["data"]["camera_code"] == "#Cam 02"


def test_director_advisor_graceful_fallback_when_rag_and_llm_offline(
    client: TestClient, auth_headers: dict[str, str]
):
    project_id = _create_project(client, auth_headers, "#Style 15")
    scene_id = _create_scene(client, auth_headers, project_id, slugline="EXT. SKYBRIDGE - DUSK")
    shot_id = _create_shot(
        client,
        auth_headers,
        scene_id,
        camera_code="#Cam 25",
        speed_code="#Speed 05",
        transition_type="NONE",
        dialogue="Hold on!",
    )

    with patch.object(DirectorRAGClient, "retrieve", new_callable=AsyncMock, side_effect=TimeoutError("8765 offline")), patch.object(
        PolyaScreenwriterEngine, "_call_llm", new_callable=AsyncMock, side_effect=RuntimeError("llm offline")
    ):
        resp = client.post(
            f"/api/v1/projects/{project_id}/scenes/{scene_id}/director-advisor",
            json={"shot_id": shot_id, "focus": "optics", "include_rag": True},
            headers=auth_headers,
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["source"] == "heuristic_rag"
    assert data["style_family"] == "anime_2d"
    assert data["director_rag_hits"] == 0
    assert len(data["recommendations"]) == 3
    risk_codes = {f["code"] for f in data["shot_risk_flags"]}
    assert "TEMPORAL_JITTER_RISK" in risk_codes
    assert "CUT_BRIDGE_MISSING" in risk_codes


def test_director_advisor_rejects_foreign_shot_and_missing_scene(
    client: TestClient, auth_headers: dict[str, str]
):
    proj_a = _create_project(client, auth_headers)
    proj_b = _create_project(client, auth_headers)
    scene_a = _create_scene(client, auth_headers, proj_a, scene_number=1)
    scene_b = _create_scene(client, auth_headers, proj_b, scene_number=1)
    shot_b = _create_shot(client, auth_headers, scene_b)

    cross_scene = client.post(
        f"/api/v1/projects/{proj_a}/scenes/{scene_b}/director-advisor",
        json={},
        headers=auth_headers,
    )
    assert cross_scene.status_code == 404

    missing_scene = client.post(
        f"/api/v1/projects/{proj_a}/scenes/{uuid.uuid4()}/director-advisor",
        json={},
        headers=auth_headers,
    )
    assert missing_scene.status_code == 404

    cross_shot = client.post(
        f"/api/v1/projects/{proj_a}/scenes/{scene_a}/director-advisor",
        json={"shot_id": shot_b},
        headers=auth_headers,
    )
    assert cross_shot.status_code == 404


def test_continuity_audit_detects_dna_state_lighting_prop_and_rule_violations(
    client: TestClient, auth_headers: dict[str, str]
):
    project_id = _create_project(client, auth_headers, "#Style 15")
    _insert_character_with_states(
        project_id,
        name="Sora",
        voice_dna=None,  # HIGH: missing Voice DNA
        with_ref=False,
        states=[("#State 01", "School blazer"), ("#State 03", "Torn blazer")],
    )
    client.put(
        f"/api/v1/projects/{project_id}/bible",
        json={
            "world_rules": {
                "environments": [{"code": "#Env 01", "name": "Rooftop", "lighting_code": "#Light 06"}],
                "props": [{"code": "#Prop 01", "name": "Chrono Key", "owner_character": "Akira"}],
                "continuity_rules": ["Keep Sora ribbon intact."],
                "negative_prompts": ["anime cel shading, blurry"],  # HIGH: conflicts with #Style 15
            }
        },
        headers=auth_headers,
    )

    scene_1 = _create_scene(
        client,
        auth_headers,
        project_id,
        act_number=3,
        scene_number=1,
        slugline="EXT. ROOFTOP - NIGHT",
        narrative_goal="Sora lifts the Chrono Key in rain.",
    )
    _create_shot(
        client,
        auth_headers,
        scene_1,
        camera_code="#Cam 08",  # HIGH: face consistency risk without visual ref
        light_code="#Light 05",  # warm_low_key
        speed_code="#Speed 05",  # MEDIUM: temporal jitter
        transition_type="NONE",  # MEDIUM: missing cut bridge
        dialogue="Look up.",
    )

    # Scene 2 in Act 1 causes state regression (#State 03 -> #State 01, MEDIUM) + lighting flip (#Light 05 -> #Light 08, MEDIUM)
    scene_2 = _create_scene(
        client,
        auth_headers,
        project_id,
        act_number=1,
        scene_number=2,
        slugline="EXT. ROOFTOP - NIGHT",
        narrative_goal="Sora waits quietly.",
    )
    _create_shot(
        client,
        auth_headers,
        scene_2,
        camera_code="#Cam 01",
        light_code="#Light 08",  # cool_high_key flip at same location/time
        speed_code="#Speed 02",
        transition_type="J_CUT",
        dialogue=None,
    )

    # Inject a direct invalid optical code via DB to verify CRITICAL detection
    settings = get_settings()
    engine = create_engine(f"sqlite:///{settings.database_path}")
    with Session(engine) as session:
        shot_row = session.query(ShotModel).filter(ShotModel.scene_id == uuid.UUID(scene_2)).first()
        shot_row.camera_code = "#Cam 99"
        session.commit()
    engine.dispose()

    resp = client.post(
        f"/api/v1/projects/{project_id}/continuity-audit",
        json={"strict_mode": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["gate_status"] == "FAIL"
    assert data["summary"]["critical_count"] >= 1
    assert data["summary"]["high_count"] >= 1
    assert data["summary"]["medium_count"] >= 1

    pillars_hit = {f["pillar"] for f in data["findings"]}
    assert {
        "character_dna_states",
        "world_props_lighting",
        "optical_spatial",
        "rules_invariants",
    }.issubset(pillars_hit)

    regression = next(
        (f for f in data["findings"] if "State Regression" in f["title"]),
        None,
    )
    assert regression is not None
    assert regression["severity"] == "MEDIUM"


def test_continuity_audit_strict_mode_escalates_high_and_medium(
    client: TestClient, auth_headers: dict[str, str]
):
    # Case 1: HIGH findings present, 0 CRITICAL -> normal=WARN, strict=FAIL
    proj_high = _create_project(client, auth_headers, "#Style 01")
    _insert_character_with_states(
        proj_high,
        name="Kai",
        voice_dna=None,  # HIGH only
        with_ref=True,
        states=[("#State 01", "Dark jacket")],
    )
    client.put(
        f"/api/v1/projects/{proj_high}/bible",
        json={
            "world_rules": {
                "continuity_rules": ["Maintain jacket patch."],
                "negative_prompts": ["cartoon, blurry"],
            }
        },
        headers=auth_headers,
    )
    sc_high = _create_scene(client, auth_headers, proj_high, slugline="INT. GARAGE - DAY")
    _create_shot(client, auth_headers, sc_high, camera_code="#Cam 01", light_code="#Light 03", speed_code="#Speed 02", dialogue=None)

    normal_high = client.post(
        f"/api/v1/projects/{proj_high}/continuity-audit",
        json={"strict_mode": False},
        headers=auth_headers,
    ).json()["data"]
    strict_high = client.post(
        f"/api/v1/projects/{proj_high}/continuity-audit",
        json={"strict_mode": True},
        headers=auth_headers,
    ).json()["data"]
    assert normal_high["summary"]["critical_count"] == 0
    assert normal_high["summary"]["high_count"] >= 1
    assert normal_high["gate_status"] == "WARN"
    assert strict_high["gate_status"] == "FAIL"

    # Case 2: Only MEDIUM findings (0 CRITICAL, 0 HIGH) -> normal=PASS, strict=WARN
    proj_med = _create_project(client, auth_headers, "#Style 01")
    _insert_character_with_states(
        proj_med,
        name="Mara",
        voice_dna="Calm soprano",
        with_ref=True,
        states=[("#State 01", "Coat")],
    )
    client.put(
        f"/api/v1/projects/{proj_med}/bible",
        json={
            "world_rules": {
                "continuity_rules": ["Keep coat buttoned."],
                "negative_prompts": ["cartoon, blurry"],
            }
        },
        headers=auth_headers,
    )
    sc_med = _create_scene(client, auth_headers, proj_med, slugline="INT. GARAGE - DAY")
    _create_shot(
        client,
        auth_headers,
        sc_med,
        camera_code="#Cam 01",
        light_code="#Light 03",
        speed_code="#Speed 05",  # MEDIUM temporal jitter only
        dialogue=None,
    )

    normal_med = client.post(
        f"/api/v1/projects/{proj_med}/continuity-audit",
        json={"strict_mode": False},
        headers=auth_headers,
    ).json()["data"]
    strict_med = client.post(
        f"/api/v1/projects/{proj_med}/continuity-audit",
        json={"strict_mode": True},
        headers=auth_headers,
    ).json()["data"]
    assert normal_med["summary"]["critical_count"] == 0
    assert normal_med["summary"]["high_count"] == 0
    assert normal_med["summary"]["medium_count"] >= 1
    assert normal_med["gate_status"] == "PASS"
    assert strict_med["gate_status"] == "WARN"


def test_continuity_audit_clean_project_passes_and_supports_scene_filter(
    client: TestClient, auth_headers: dict[str, str]
):
    project_id = _create_project(client, auth_headers, "#Style 02")
    _insert_character_with_states(
        project_id,
        name="Elena",
        voice_dna="Measured alto",
        with_ref=True,
        states=[
            ("#State 01", "Navy trenchcoat, clean"),
            ("#State 02", "Navy trenchcoat, rain-soaked"),
        ],
    )
    client.put(
        f"/api/v1/projects/{project_id}/bible",
        json={
            "world_rules": {
                "environments": [{"code": "#Env 01", "name": "Observatory Lab", "lighting_code": "#Light 03"}],
                "props": [{"code": "#Prop 01", "name": "Astrolabe", "owner_character": "Elena"}],
                "continuity_rules": ["Preserve Elena silver hair clasp."],
                "negative_prompts": ["cartoon, anime cel shading"],
            }
        },
        headers=auth_headers,
    )
    sc1 = _create_scene(
        client,
        auth_headers,
        project_id,
        act_number=1,
        scene_number=1,
        slugline="INT. OBSERVATORY LAB - NIGHT",
        narrative_goal="Elena inspects the Astrolabe.",
    )
    _create_shot(client, auth_headers, sc1, camera_code="#Cam 01", light_code="#Light 03", speed_code="#Speed 02", transition_type="J_CUT")

    sc2 = _create_scene(
        client,
        auth_headers,
        project_id,
        act_number=2,
        scene_number=2,
        slugline="INT. OBSERVATORY LAB - NIGHT",
        narrative_goal="Elena adjusts the Astrolabe.",
    )
    _create_shot(client, auth_headers, sc2, camera_code="#Cam 02", light_code="#Light 03", speed_code="#Speed 02", transition_type="L_CUT")

    clean_resp = client.post(
        f"/api/v1/projects/{project_id}/continuity-audit",
        json={"strict_mode": True},
        headers=auth_headers,
    )
    assert clean_resp.status_code == 200, clean_resp.text
    clean_data = clean_resp.json()["data"]
    assert clean_data["gate_status"] == "PASS"
    assert clean_data["summary"]["scenes_audited"] == 2
    assert clean_data["summary"]["shots_audited"] == 2
    assert clean_data["continuity_score"] >= 95.0

    filtered = client.post(
        f"/api/v1/projects/{project_id}/continuity-audit",
        json={"scene_id": sc1},
        headers=auth_headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["data"]["summary"]["scenes_audited"] == 1
    assert filtered.json()["data"]["summary"]["shots_audited"] == 1

    # Reject scene_id from a foreign project
    other_proj = _create_project(client, auth_headers)
    other_sc = _create_scene(client, auth_headers, other_proj)
    bad_filter = client.post(
        f"/api/v1/projects/{project_id}/continuity-audit",
        json={"scene_id": other_sc},
        headers=auth_headers,
    )
    assert bad_filter.status_code == 404
