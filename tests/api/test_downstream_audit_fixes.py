"""Tests verifying the downstream batch audit fixes and invariants:
1. record_account_failure resets status to 'active' on transient failures (<3) and 'cooldown' on 3+ failures.
2. Wardrobe extraction handles gowns (Mei-Ling) without trousers fallback, and excludes 'collarbone' from collar extraction (Ren).
3. Dynamic States use anchors [Card 1, Card 3] exclusively (Card 2 removed).
4. Strict Production Constraints are injected with Card 2 exempt from no-grid rules.
5. Card 5 (3/4 Hero Angle) enforces 45-degree shoulder/torso turn and non-frontal directives.
"""

from datetime import datetime
from pathlib import Path
import sqlite3
import uuid

from sqlalchemy import create_engine

from backend.app.api.v1.bible import (
    _extract_biometric_and_collar,
    _extract_full_body_costume,
    compile_sheet_prompt,
)
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.flow import FlowAccountModel
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.workers.flow_image_worker import record_account_failure


def test_record_account_failure_resets_to_active_when_under_threshold(tmp_path: Path):
    """Ensure accounts reset to 'active' under 3 fails, enter 'cooldown' at 3, and move to back of LRU."""
    db_path = tmp_path / "test_flow_accounts.db"
    engine = create_engine(f"sqlite:///{db_path}")
    FlowAccountModel.__table__.create(bind=engine)
    engine.dispose()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO flow_accounts (
                id, label, profile_dir, status, daily_count, last_reset_date,
                total_count, consecutive_failures, last_used_at, updated_at
            ) VALUES (?, ?, ?, ?, 0, '2026-11-23', 0, 0, ?, ?)
            """,
            [
                (1, "Akun Pro 1", "flow_profile_1", "busy", None, "2026-11-23T00:00:00+00:00"),
                (2, "Akun Pro 2", "flow_profile_2", "active", "2026-11-23T01:00:00+00:00", "2026-11-23T01:00:00+00:00"),
                (3, "Akun Pro 3", "flow_profile_3", "active", "2026-11-23T02:00:00+00:00", "2026-11-23T02:00:00+00:00"),
            ],
        )
        conn.commit()

        def _active_lru_order() -> list[int]:
            rows = cursor.execute(
                """
                SELECT id FROM flow_accounts
                WHERE status = 'active'
                ORDER BY
                    CASE WHEN last_used_at IS NULL THEN 0 ELSE 1 END ASC,
                    last_used_at ASC,
                    id ASC
                """
            ).fetchall()
            return [int(r["id"]) for r in rows]

        assert _active_lru_order() == [2, 3]

        # 1st failure: should reset status to 'active' and move account #1 to back of LRU
        record_account_failure(conn, 1, "Temporary canvas timeout")
        row = cursor.execute(
            "SELECT status, consecutive_failures, last_error, last_used_at, cooldown_until "
            "FROM flow_accounts WHERE id = 1"
        ).fetchone()
        assert row["status"] == "active", f"Expected status 'active' but got {row['status']}"
        assert row["consecutive_failures"] == 1
        assert "timeout" in row["last_error"]
        assert row["cooldown_until"] is None
        assert row["last_used_at"] is not None
        fail1_used_at = datetime.fromisoformat(row["last_used_at"])
        assert fail1_used_at > datetime.fromisoformat("2026-11-23T02:00:00+00:00")
        assert _active_lru_order() == [2, 3, 1]

        # 2nd failure: should still reset status to 'active' and keep account #1 at back of LRU
        record_account_failure(conn, 1, "Network glitch")
        row = cursor.execute(
            "SELECT status, consecutive_failures, last_error, last_used_at, cooldown_until "
            "FROM flow_accounts WHERE id = 1"
        ).fetchone()
        assert row["status"] == "active", f"Expected status 'active' but got {row['status']}"
        assert row["consecutive_failures"] == 2
        assert "Network glitch" in row["last_error"]
        assert row["cooldown_until"] is None
        assert row["last_used_at"] is not None
        fail2_used_at = datetime.fromisoformat(row["last_used_at"])
        assert fail2_used_at >= fail1_used_at
        assert _active_lru_order() == [2, 3, 1]

        # 3rd failure: threshold reached, should enter 'cooldown' and exit active LRU queue
        record_account_failure(conn, 1, "Repeated crash")
        row = cursor.execute(
            "SELECT status, consecutive_failures, last_error, last_used_at, cooldown_until "
            "FROM flow_accounts WHERE id = 1"
        ).fetchone()
        assert row["status"] == "cooldown", f"Expected status 'cooldown' but got {row['status']}"
        assert row["consecutive_failures"] == 3
        assert "Repeated crash" in row["last_error"]
        assert row["cooldown_until"] is not None
        assert row["last_used_at"] is not None
        fail3_used_at = datetime.fromisoformat(row["last_used_at"])
        assert fail3_used_at >= fail2_used_at
        assert datetime.fromisoformat(row["cooldown_until"]) > fail3_used_at
        assert _active_lru_order() == [2, 3]
    finally:
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

    # Card 3 (4-Panel Character & Wardrobe Composite) — must allow 4-panel grid without 'zero grids'
    c3 = compile_sheet_prompt(character=char, project=proj, bible=mpb, slot="front")
    assert "[Strict Production Constraints:" in c3["positive_prompt"]
    assert c3["recommended_aspect_ratio"] == "16:9"
    assert c3["width"] == 1344 and c3["height"] == 768
    assert "4-panel" in c3["positive_prompt"].lower()
    assert "1-2px clean white" in c3["positive_prompt"].lower()
    assert "no head shown" in c3["positive_prompt"].lower()
    assert "zero grids" not in c3["positive_prompt"].lower(), "Card 3 4-panel composite must NOT prohibit grids!"

    # Card 5 (3/4 Hero Angle)
    c5 = compile_sheet_prompt(character=char, project=proj, bible=mpb, slot="three_quarter")
    assert "45-degree" in c5["positive_prompt"]
    assert "torso and shoulders are distinctly turned 45 degrees" in c5["positive_prompt"].lower()
    assert "strictly avoid flat orthogonal front-facing orientation" in c5["positive_prompt"].lower()
    assert "zero grids" in c5["positive_prompt"].lower()
