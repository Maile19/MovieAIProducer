"""Tests verifying the downstream batch audit fixes and invariants:
1. record_account_failure resets status to 'active' on transient failures (<3) and 'cooldown' on 3+ failures.
2. Wardrobe extraction handles gowns (Mei-Ling) without trousers fallback, and excludes 'collarbone' from collar extraction (Ren).
3. Dynamic States use anchors [Card 1, Card 3] exclusively (Card 2 removed).
4. Strict Production Constraints are injected with Card 2 exempt from no-grid rules.
5. Card 5 (3/4 Hero Angle) enforces 45-degree shoulder/torso turn and non-frontal directives.
"""

import sqlite3
import tempfile
import uuid
from unittest.mock import MagicMock

import pytest

from backend.app.api.v1.bible import (
    _extract_biometric_and_collar,
    _extract_full_body_costume,
    compile_sheet_prompt,
)
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.workers.flow_image_worker import record_account_failure


def test_record_account_failure_resets_to_active_when_under_threshold():
    """Ensure accounts do not stay locked in 'busy' status on transient failures (<3 fails)."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        conn = sqlite3.connect(tmp.name)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE flow_accounts (
                id INTEGER PRIMARY KEY,
                email TEXT,
                status TEXT,
                consecutive_failures INTEGER,
                last_error TEXT,
                cooldown_until TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        cursor.execute(
            "INSERT INTO flow_accounts (id, email, status, consecutive_failures, updated_at) VALUES (1, 'pro1@flow.local', 'busy', 0, '2026-11-23T00:00:00Z')"
        )
        conn.commit()

        # 1st failure: should reset status to 'active'
        record_account_failure(conn, 1, "Temporary canvas timeout")
        row = cursor.execute("SELECT status, consecutive_failures, last_error FROM flow_accounts WHERE id = 1").fetchone()
        assert row[0] == "active", f"Expected status 'active' but got {row[0]}"
        assert row[1] == 1
        assert "timeout" in row[2]

        # 2nd failure: should still reset status to 'active'
        record_account_failure(conn, 1, "Network glitch")
        row = cursor.execute("SELECT status, consecutive_failures FROM flow_accounts WHERE id = 1").fetchone()
        assert row[0] == "active", f"Expected status 'active' but got {row[0]}"
        assert row[1] == 2

        # 3rd failure: threshold reached, should enter 'cooldown'
        record_account_failure(conn, 1, "Repeated crash")
        row = cursor.execute("SELECT status, consecutive_failures, cooldown_until FROM flow_accounts WHERE id = 1").fetchone()
        assert row[0] == "cooldown", f"Expected status 'cooldown' but got {row[0]}"
        assert row[1] == 3
        assert row[2] is not None
        conn.close()


def test_wardrobe_extraction_mei_ling_gown_no_trousers():
    """Mei-Ling's silk embroidered gown must NOT be degraded to trousers."""
    base_prompt = (
        "elegant imperial noblewoman, wearing an exquisite flowing red and gold silk embroidered gown "
        "with delicate floral embroidery, translucent flutter sleeves, and floor-length silk skirt"
    )
    biometric, collar = _extract_biometric_and_collar(base_prompt, char_name="Mei-Ling")
    costume = _extract_full_body_costume(base_prompt, wardrobe_collar=collar, char_name="Mei-Ling")

    assert "gown" in costume.lower(), f"Expected 'gown' in costume, got: {costume}"
    assert "trousers" not in costume.lower(), f"Costume should not contain 'trousers', got: {costume}"
    assert "pants" not in costume.lower(), f"Costume should not contain 'pants', got: {costume}"
    assert "flutter sleeves" in costume.lower(), f"Expected 'flutter sleeves' to be preserved, got: {costume}"


def test_wardrobe_extraction_ren_collarbone_not_collar():
    """Ren's collarbone must not collide with collar regex, and sleeveless vest must be preserved."""
    base_prompt = (
        "athletic cyberpunk rebel with cybernetic lines tracing along the collarbone, "
        "wearing a sleeveless tactical vest and dark combat trousers"
    )
    biometric, collar = _extract_biometric_and_collar(base_prompt, char_name="Ren")
    costume = _extract_full_body_costume(base_prompt, wardrobe_collar=collar, char_name="Ren")

    assert "collarbone" not in collar.lower(), f"Collarbone was erroneously matched as collar: {collar}"
    assert "sleeveless" in costume.lower(), f"Expected 'sleeveless' in costume, got: {costume}"
    assert "vest" in costume.lower(), f"Expected 'vest' in costume, got: {costume}"
    assert "trousers" in costume.lower(), f"Expected 'trousers' in costume, got: {costume}"


def test_dynamic_states_anchors_exclude_card_2():
    """Dynamic States must use Anchors [Card 1, Card 3] only, NEVER Card 2 (Expression Sheet)."""
    char = CharacterModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Wei",
        role="Protagonist",
        base_prompt="young martial artist in charcoal linen tunic and loose trousers",
        closeup_image_url="http://localhost:8090/media/wei_closeup.png",
        expression_image_url="http://localhost:8090/media/wei_expression_grid.png",
        front_image_url="http://localhost:8090/media/wei_front.png",
    )
    proj = ProjectModel(id=char.project_id, title="Test Project")
    mpb = MasterProductionBibleModel(
        id=uuid.uuid4(),
        project_id=char.project_id,
        version=1,
        style_parameters={"style_family": "cinematic_live_action", "aesthetic_directives": "photorealistic"},
    )
    state = CharacterStateModel(
        id=uuid.uuid4(),
        character_id=char.id,
        state_code="#State 01",
        state_label="Normal Baseline",
        wardrobe="charcoal linen tunic and loose trousers",
        injuries_and_wear="pristine",
        expression_anchor="calm",
    )

    compiled = compile_sheet_prompt(
        character=char,
        project=proj,
        bible=mpb,
        slot="state",
        target_state=state,
    )

    labels = [label for label, _ in compiled["ref_candidates"]]
    assert "Card 1 Character Close-Up" in labels
    assert "Card 3 Full Body Front" in labels
    assert "Card 2 Expression Sheet" not in labels, "Card 2 (Expression Sheet) must NOT be an anchor for Dynamic States!"
    assert len(compiled["ref_candidates"]) == 2

    # Verify single-frame constraint in positive prompt
    assert "single unified" in compiled["positive_prompt"].lower()
    assert "zero multi-panel grid" in compiled["positive_prompt"].lower()


def test_strict_production_constraints_card_2_vs_downstream():
    """Card 2 must have 3x2 grid directive without 'zero grids', while Card 3-8/States must have 'zero grids'."""
    char = CharacterModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Lian-Hua",
        base_prompt="master sorceress wearing an elegant midnight blue silk robe with long flowing sleeves",
        closeup_image_url="http://localhost:8090/media/lh_c1.png",
        front_image_url="http://localhost:8090/media/lh_c3.png",
    )
    proj = ProjectModel(id=char.project_id, title="Test")
    mpb = MasterProductionBibleModel(
        id=uuid.uuid4(),
        project_id=char.project_id,
        version=1,
        style_parameters={"style_family": "cinematic_live_action"},
    )

    # Card 2 (Expression Sheet)
    c2 = compile_sheet_prompt(character=char, project=proj, bible=mpb, slot="expression")
    assert "[Strict Production Constraints:" in c2["positive_prompt"]
    assert "3x2 grid" in c2["positive_prompt"]
    assert "Zero grids" not in c2["positive_prompt"], "Card 2 must NOT prohibit grids!"

    # Card 3 (Full Body Front)
    c3 = compile_sheet_prompt(character=char, project=proj, bible=mpb, slot="front")
    assert "[Strict Production Constraints:" in c3["positive_prompt"]
    assert "zero grids" in c3["positive_prompt"].lower()
    assert "zero collages" in c3["positive_prompt"].lower()

    # Card 5 (3/4 Hero Angle)
    c5 = compile_sheet_prompt(character=char, project=proj, bible=mpb, slot="three_quarter")
    assert "45-degree" in c5["positive_prompt"]
    assert "torso and shoulders are distinctly turned 45 degrees" in c5["positive_prompt"].lower()
    assert "strictly avoid flat orthogonal front-facing orientation" in c5["positive_prompt"].lower()
    assert "zero grids" in c5["positive_prompt"].lower()
