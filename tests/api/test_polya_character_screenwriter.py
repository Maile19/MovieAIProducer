import uuid
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.domain.screenwriter import (
    CastEnsembleData,
    CharacterData,
    CharacterStateData,
    generate_unique_deterministic_seed,
    extract_project_narrative_context,
)
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)


def create_dummy_character_output(
    name: str,
    role: str,
    summary: str,
    prompt: str,
    voice: str,
) -> CharacterData:
    states = [
        CharacterStateData(
            state_number=1,
            state_label="Normal Baseline",
            wardrobe="Clean tactical trenchcoat and tailored underlayer",
            physical_damage="Immaculate, zero defects",
            emotional_anchor="Guarded, focused ocular scan",
        ),
        CharacterStateData(
            state_number=2,
            state_label="Wear & Tear",
            wardrobe="Unbuttoned collar, dust on shoulders",
            physical_damage="Light scratches on knuckles",
            emotional_anchor="Fatigued, vigilant",
        ),
        CharacterStateData(
            state_number=3,
            state_label="Battle Damaged",
            wardrobe="Torn shoulder seam, exposed ballistic plate",
            physical_damage="Singed fabric, bloodied temple",
            emotional_anchor="Adrenaline surge, defiant glare",
        ),
        CharacterStateData(
            state_number=4,
            state_label="Psychological Breakdown",
            wardrobe="Disheveled coat, field bandage on forearm",
            physical_damage="Heavy bruising, frayed gear",
            emotional_anchor="Grim exhaustion turning into desperate lethal focus",
        ),
        CharacterStateData(
            state_number=5,
            state_label="Climax / Catharsis",
            wardrobe="Pristine ceremonial jacket or battle-worn signature silhouette",
            physical_damage="Patina of survival, deep healing scar",
            emotional_anchor="Transcendent resolve and quiet closure",
        ),
    ]
    return CharacterData(
        name=name,
        role=role,
        narrative_summary=summary,
        base_visual_prompt=prompt,
        voice_dna_profile=voice,
        states=states,
    )


def test_empty_state_zero_static_characters(client: TestClient, auth_headers: dict):
    """Proyek baru wajib dimulai dalam kondisi Empty State (0 karakter). Tidak ada Cipher Vance."""
    # 1. Create a fresh project
    create_res = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"title": f"Fresh Clean Project {uuid.uuid4().hex[:6]}"},
    )
    assert create_res.status_code == 201, create_res.text
    project_id = create_res.json()["data"]["id"]

    # 2. Query characters
    res = client.get(f"/api/v1/projects/{project_id}/characters", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 0, f"Expected 0 characters for fresh project, got {len(data)}"

    # 3. Direct DB check: verify zero characters in database
    settings = get_settings()
    engine = create_engine(f"sqlite:///{settings.database_path}")
    with Session(engine) as session:
        chars = session.execute(
            select(CharacterModel).where(CharacterModel.project_id == uuid.UUID(project_id))
        ).scalars().all()
        assert len(chars) == 0
        vance_count = session.execute(
            text("SELECT count(*) FROM characters WHERE name LIKE '%Cipher Vance%'")
        ).scalar()
        assert vance_count == 0, "Cipher Vance must be 100% purged from the database"
    engine.dispose()


def test_generate_cast_missing_synopsis_fails(client: TestClient, auth_headers: dict):
    """Generate cast tanpa sinopsis wajib mengembalikan HTTP 400 Bad Request."""
    create_res = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"title": "No Synopsis Movie"},
    )
    project_id = create_res.json()["data"]["id"]

    res = client.post(
        f"/api/v1/projects/{project_id}/characters/generate-cast",
        headers=auth_headers,
        json={"preferred_count": 6},
    )
    assert res.status_code == 400
    assert "sinopsis" in str(res.json()).lower()


def test_generate_cast_polya_screenwriter_success(client: TestClient, auth_headers: dict):
    """Generate cast 5-8 karakter via Polya AI Screenwriter dengan 5 state progression & 0 image render."""
    # 1. Create project with rich synopsis
    create_res = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "title": "Jakarta Cyber Syndicate 2099",
            "settings": {
                "synopsis": "In a flood-drenched Neo Jakarta, an ex-cybernetic detective and an underground memory broker uncover a syndicate conspiracy involving memory counterfeiting.",
                "genre": "Cyberpunk Noir",
                "tone": "Gritty & Atmospheric",
            },
        },
    )
    project_id = create_res.json()["data"]["id"]

    # 2. Mock PolyaScreenwriterEngine.generate_cast_ensemble
    mock_ensemble = [
        create_dummy_character_output(
            name="Rian Sanjaya",
            role="PROTAGONIST",
            summary="Disillusioned 36-year-old cyber-detective hunting illicit memory implants.",
            prompt="Male cyber-detective, 36 years old, tired amber cybernetic eye, worn matte-black trenchcoat, studio gray background.",
            voice="Gravelly baritone, calm cadence, subtle Indonesian inflection.",
        ),
        create_dummy_character_output(
            name="Vesper Zhao",
            role="ANTAGONIST",
            summary="Ruthless executive of Zhao Neuro-Corp, architect of neural erasure.",
            prompt="Female corporate syndicate overseer, 44 years old, sharp asymmetrical bob, monochromatic silver suit, studio gray background.",
            voice="Cold, crisp mid-Atlantic cadence, restrained volume.",
        ),
        create_dummy_character_output(
            name="Maya Lin",
            role="DEUTERAGONIST",
            summary="Subterranean memory broker who operates out of floating wet-market barges.",
            prompt="Female memory hacker, 28 years old, neon braided hair, augmented finger stylus, studio gray background.",
            voice="Rapid, energetic cadence, street slang fluency.",
        ),
        create_dummy_character_output(
            name="Bambang Surya",
            role="MENTOR",
            summary="Retired police commissioner who gave Rian his first cyberware.",
            prompt="Elderly Indonesian man, 62 years old, cybernetic walking cane, batik-patterned tactical vest, studio gray background.",
            voice="Resonant elder voice, patient and weary.",
        ),
        create_dummy_character_output(
            name="Kiki",
            role="SUPPORTING",
            summary="Drone mechanic and loyal alleyway surveillance specialist.",
            prompt="Androgynous mechanic, 22 years old, grease smudges, holographic welding goggles, studio gray background.",
            voice="High-energy, fast talker with nervous laugh.",
        ),
        create_dummy_character_output(
            name="Inspector Darma",
            role="SUPPORTING",
            summary="Corrupt precinct chief torn between syndicate bribes and old loyalties.",
            prompt="Male precinct chief, 50 years old, heavy build, formal police uniform with tarnished brass badges, studio gray background.",
            voice="Heavy guttural voice, defensive posture.",
        ),
    ]

    with patch(
        "backend.app.domain.screenwriter.PolyaScreenwriterEngine.generate_cast_ensemble",
        new=AsyncMock(return_value=CastEnsembleData(characters=mock_ensemble)),
    ):
        res = client.post(
            f"/api/v1/projects/{project_id}/characters/generate-cast",
            headers=auth_headers,
            json={"preferred_count": 6, "replace_existing": True},
        )

    assert res.status_code in (200, 201), res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["generated_count"] == 6

    chars = body["data"]
    assert len(chars) == 6

    # Verify Seeds: Unique, 6-digit integers
    seeds = [c["dna_seed"] for c in chars]
    assert len(set(seeds)) == 6, f"All seeds must be unique, got duplicates: {seeds}"
    for s in seeds:
        assert isinstance(s, int)
        assert 100000 <= s <= 999999

    # Verify Strict Text-Only: Zero auto-rendered images!
    for c in chars:
        assert c["closeup_image_url"] is None, "Zero Auto-Render: closeup_image_url must be None!"
        assert c["front_image_url"] is None
        assert c["narrative_summary"] is not None
        assert c["voice_dna_profile"] is not None

        # Verify exactly 5 states per character
        states = c["states"]
        assert len(states) == 5, f"Expected exactly 5 states, got {len(states)}"
        expected_codes = ["#State 01", "#State 02", "#State 03", "#State 04", "#State 05"]
        actual_codes = [st["state_code"] for st in states]
        assert actual_codes == expected_codes
        for st in states:
            assert st["image_url"] is None, "Zero Auto-Render: state.image_url must be None!"
            assert st["state_label"] is not None, "state_label must be populated"

    # 3. Test Conflict: replace_existing=False when characters exist returns 409
    conflict_res = client.post(
        f"/api/v1/projects/{project_id}/characters/generate-cast",
        headers=auth_headers,
        json={"replace_existing": False},
    )
    assert conflict_res.status_code == 409

    # 4. Test generate-one: add 1 character without mutating siblings
    new_char_output = create_dummy_character_output(
        name="Tariq Al-Mansoor",
        role="DEUTERAGONIST",
        summary="Foreign syndicate emissary sent to inspect Jakarta operations.",
        prompt="Male emissary, 38 years old, gold geometric lapel pin, dark tailored linen jacket, studio gray background.",
        voice="Smooth baritone with cosmopolitan accent.",
    )

    with patch(
        "backend.app.domain.screenwriter.PolyaScreenwriterEngine.generate_one_character",
        new=AsyncMock(return_value=new_char_output),
    ) as mock_gen_one:
        one_res = client.post(
            f"/api/v1/projects/{project_id}/characters/generate-one",
            headers=auth_headers,
            json={"preferred_role": "DEUTERAGONIST", "custom_directive": "Foreign emissary"},
        )

    assert one_res.status_code in (200, 201), one_res.text
    created_char = one_res.json()["data"]
    assert created_char["name"] == "Tariq Al-Mansoor"
    assert created_char["role"] == "DEUTERAGONIST"
    assert created_char["dna_seed"] not in seeds, "New character must have a unique seed not colliding with siblings"
    assert len(created_char["states"]) == 5
    assert created_char["closeup_image_url"] is None, "Zero Auto-Render check"

    # Verify mock was called with sibling_characters containing the 6 previous characters
    mock_gen_one.assert_called_once()
    call_args = mock_gen_one.call_args[1]
    sibling_cast = call_args["sibling_characters"]
    assert len(sibling_cast) == 6

    # 5. Test regenerate single character
    target_id = created_char["id"]
    regen_output = create_dummy_character_output(
        name="Tariq Al-Mansoor (Resurgent)",
        role="DEUTERAGONIST",
        summary="A heavily scarred veteran emissary who survived an assassination attempt.",
        prompt="Male veteran, 45 years old, prominent scar across jaw, tactical combat attire, studio gray background.",
        voice="Raspy whisper due to vocal damage.",
    )

    with patch(
        "backend.app.domain.screenwriter.PolyaScreenwriterEngine.regenerate_single_character",
        new=AsyncMock(return_value=regen_output),
    ):
        regen_res = client.post(
            f"/api/v1/projects/{project_id}/characters/{target_id}/regenerate",
            headers=auth_headers,
            json={"preserve_role": True, "custom_directive": "Add severe vocal scar"},
        )

    assert regen_res.status_code == 200, regen_res.text
    regened = regen_res.json()["data"]
    assert regened["name"] == "Tariq Al-Mansoor (Resurgent)"
    assert regened["narrative_summary"] == "A heavily scarred veteran emissary who survived an assassination attempt."
    assert regened["closeup_image_url"] is None, "Must reset image URL"

    # 6. Test PATCH character identity & prompt
    patch_res = client.patch(
        f"/api/v1/projects/{project_id}/characters/{target_id}",
        headers=auth_headers,
        json={
            "name": "Lord Tariq",
            "role": "ANTAGONIST",
            "base_prompt": "Supreme corporate lord in gilded power-armor, studio gray background.",
        },
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()["data"]
    assert patched["name"] == "Lord Tariq"
    assert patched["role"] == "ANTAGONIST"
    assert "Supreme corporate lord" in patched["base_prompt"]

    # 7. Test DELETE character cascades deletion of character and its states
    del_res = client.delete(
        f"/api/v1/projects/{project_id}/characters/{target_id}",
        headers=auth_headers,
    )
    assert del_res.status_code == 200

    # Verify from DB that character and states are gone
    settings = get_settings()
    engine = create_engine(f"sqlite:///{settings.database_path}")
    with Session(engine) as session:
        c_check = session.get(CharacterModel, uuid.UUID(target_id))
        assert c_check is None, "Character must be deleted"
        s_count = session.execute(
            select(CharacterStateModel).where(CharacterStateModel.character_id == uuid.UUID(target_id))
        ).scalars().all()
        assert len(s_count) == 0, "All associated character_states must be cascade-deleted"
    engine.dispose()
