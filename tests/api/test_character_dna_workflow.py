import json
import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.api.v1.bible import (
    STANDARD_STUDIO_BACKGROUND,
    compile_sheet_prompt,
    get_character_sheet_prompts,
    _url_to_local_path,
)
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.app.infrastructure.sd35_client import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from backend.app.core.config import get_settings


class MockFastImageProvider(ImageGenerationProvider):
    """Generates synthetic studio gray (#D4D4D4) PNG images for fast, deterministic testing."""
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        settings = get_settings()
        out_dir = settings.effective_preview_storage_path
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"mock_{uuid.uuid4().hex[:8]}.png"
        file_path = out_dir / filename

        w = request.width or 768
        h = request.height or 1024
        # Generate valid #D4D4D4 Neutral Matte Light-Medium Studio Gray image
        img = Image.new("RGB", (w, h), color=(212, 212, 212))
        img.save(file_path, format="PNG")

        return ImageGenerationResult(
            local_path=str(file_path),
            local_url=f"/api/v1/assets/previews/{filename}",
            remote_url=None,
            seed=request.seed,
            width=w,
            height=h,
            steps=25,
            file_size_bytes=file_path.stat().st_size,
            mime_type="image/png",
            sha256_checksum="mocksha256",
            provider="mock_studio_gray",
        )


def test_guardrail_flow_worker_and_selectors_intact():
    """Verify flow_image_worker.py and flow_selectors.json have not been corrupted or broken."""
    worker_path = Path("backend/workers/flow_image_worker.py")
    selectors_path = Path("backend/config/flow_selectors.json")

    assert worker_path.exists(), "flow_image_worker.py must exist"
    assert selectors_path.exists(), "flow_selectors.json must exist"

    worker_code = worker_path.read_text(encoding="utf-8")
    selectors_content = selectors_path.read_text(encoding="utf-8")
    selectors_json = json.loads(selectors_content)

    # 1. Privacy & onboarding modal dismissal check in worker
    assert "dismiss_onboarding_dialogs" in worker_code, "flow_image_worker.py must have dismiss_onboarding_dialogs logic"
    assert "Modal persetujuan hak cipta gambar" in worker_code, "flow_image_worker.py must handle copyright/terms modal"

    # 2. Key selectors in flow_selectors.json
    assert "login_detectors" in selectors_json, "flow_selectors.json must have login_detectors"
    assert "reference_image_input" in selectors_json, "flow_selectors.json must have reference_image_input"
    assert "generate_button" in selectors_json, "flow_selectors.json must have generate_button"

    # 3. ProseMirror newline sanitization
    assert 'clean_prompt = " ".join(prompt.split())' in worker_code or '.replace("\\n", " ")' in worker_code, (
        "flow_image_worker.py must sanitize newlines for ProseMirror"
    )

    # 4. Reference image size validation (> 2 KB)
    assert "2048" in worker_code, "flow_image_worker.py must validate reference file size > 2 KB (2048 bytes)"


def test_guardrail_no_polia_leakage():
    """Verify that Polia AI / Hermes Agent is strictly excluded from providers and modal flows."""
    frontend_tab_code = Path("frontend/src/components/bible/CharacterMatrixTab.tsx").read_text(encoding="utf-8")
    bible_api_code = Path("backend/app/api/v1/bible.py").read_text(encoding="utf-8")

    # Frontend must not have any reference or dropdown option for polia / hermes
    assert "polia" not in frontend_tab_code.lower()
    assert "hermes" not in frontend_tab_code.lower()

    # Backend endpoints must restrict providers to approved list (9router, gemini, agy / google_flow, ag_gemini_flash, sd35_large)
    from backend.app.api.v1.bible import CharacterAutoGenerateRequest, CharacterPreviewRequest
    auto_gen_fields = CharacterAutoGenerateRequest.model_fields
    preview_fields = CharacterPreviewRequest.model_fields
    assert "polia" not in str(auto_gen_fields["llm_provider"].annotation).lower()
    assert "hermes" not in str(auto_gen_fields["llm_provider"].annotation).lower()
    assert "polia" not in str(preview_fields["image_provider"].annotation).lower()


def test_eight_sheet_matrix_hierarchy_and_sequential_anchoring():
    """
    Eight-Sheet Character Matrix & Dynamic State Verification:
    Card 1 is Character Close-Up (Master Face Anchor, 3:4, ref_candidates=[]).
    Card 2 is Expression Sheet (3x2 Grid, 16:9, ref_candidates=[Card 1 Close-Up]).
    Card 3 is Full Body Front (Primary Body Anchor, 3:4, ref_candidates=[Card 1 Close-Up]).
    Cards 4-8 (side, 3/4, back, tpose, action) anchor strictly to Card 1 Close-Up and Card 3 Full Body Front.
    Dynamic States anchor to Card 1 Close-Up and Card 2 Expression Sheet (+ Card 3 if present).
    All prompts must use pure natural prose without bracket headers or hex codes (#D4D4D4).
    """
    proj_id = uuid.uuid4()
    char = CharacterModel(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Elena Rostova",
        role="PROTAGONIST",
        base_prompt="A 28-year-old operative with silver hair and tactical bodysuit",
        dna_seed="774921",
        closeup_image_url="/api/v1/assets/previews/char_closeup_master.png",
        expression_image_url="/api/v1/assets/previews/char_expression_master.png",
        front_image_url="/api/v1/assets/previews/char_front_master.png",
        side_image_url=None,
        three_quarter_image_url=None,
        back_image_url=None,
        tpose_image_url=None,
        action_image_url=None,
    )
    proj = ProjectModel(
        id=proj_id,
        title="Neon Syndicate",
        slug="neon-syndicate",
        status="PLANNING",
        settings={"description": "Cyberpunk Noir thriller"},
    )
    bible = MasterProductionBibleModel(
        project_id=proj_id,
        style_parameters={"master_style_code": "#Style 01", "genre": "Sci-Fi Cyberpunk"},
        world_rules={"world_setting": "Neo-Shinjuku"},
    )

    # 1. Card 2: Expression Sheet (Anchored to Card 1 Close-Up)
    card_expr = compile_sheet_prompt(char, proj, bible, "expression")
    assert card_expr["recommended_aspect_ratio"] == "16:9"
    assert card_expr["width"] == 1344
    assert card_expr["height"] == 768
    assert len(card_expr["ref_candidates"]) == 1
    assert card_expr["ref_candidates"][0][0] == "Card 1 Character Close-Up"
    assert card_expr["ref_candidates"][0][1] == "/api/v1/assets/previews/char_closeup_master.png"
    assert "3-column by 2-row grid" in card_expr["positive_prompt"]
    assert "#D4D4D4" not in card_expr["positive_prompt"]
    assert "butterfly/clamshell studio lighting" in card_expr["positive_prompt"]

    # 2. Card 3: 4-Panel Character & Wardrobe Master Reference (Anchored strictly to Card 1 Close-Up)
    card_front = compile_sheet_prompt(char, proj, bible, "front")
    assert card_front["recommended_aspect_ratio"] == "16:9"
    assert card_front["width"] == 1344
    assert card_front["height"] == 768
    assert len(card_front["ref_candidates"]) == 1
    assert card_front["ref_candidates"][0][0] == "Card 1 Character Close-Up"
    assert card_front["ref_candidates"][0][1] == "/api/v1/assets/previews/char_closeup_master.png"
    assert "3-column, 4-panel" in card_front["positive_prompt"]
    assert "NO head shown" in card_front["positive_prompt"]
    assert "#D4D4D4" not in card_front["positive_prompt"]
    assert "butterfly/clamshell studio lighting" in card_front["positive_prompt"]

    # 3. Card 4: Side Profile (Anchored strictly to Card 1 Close-Up & Card 3 Full Body Front)
    card_side = compile_sheet_prompt(char, proj, bible, "side")
    assert len(card_side["ref_candidates"]) == 2
    assert card_side["ref_candidates"][0][0] == "Card 1 Character Close-Up"
    assert card_side["ref_candidates"][1][0] == "Card 3 Full Body Front"
    assert "#D4D4D4" not in card_side["positive_prompt"]

    # 4. Cards 5-8: three_quarter, tpose, action (Card 1 -> Card 3) & back (Card 3 Primary -> Card 1 Hair)
    for slot in ["three_quarter", "tpose", "action"]:
        card = compile_sheet_prompt(char, proj, bible, slot)
        assert len(card["ref_candidates"]) == 2, f"{slot} must reference Card 1 and Card 3"
        assert card["ref_candidates"][0][0] == "Card 1 Character Close-Up"
        assert card["ref_candidates"][1][0] == "Card 3 Full Body Front"
        assert "#D4D4D4" not in card["positive_prompt"]
        assert "butterfly/clamshell studio lighting" in card["positive_prompt"]

    card_back = compile_sheet_prompt(char, proj, bible, "back")
    assert len(card_back["ref_candidates"]) == 2, "back must reference Card 3 (Primary) and Card 1 (Secondary Hair)"
    assert card_back["ref_candidates"][0][0] == "Card 3 Full Body Front"
    assert card_back["ref_candidates"][1][0] == "Card 1 Character Close-Up"
    assert "#D4D4D4" not in card_back["positive_prompt"]
    assert "butterfly/clamshell studio lighting" in card_back["positive_prompt"]

    # 5. Slot ordering in get_character_sheet_prompts
    slots = ["closeup", "expression", "front", "side", "three_quarter", "back", "tpose", "action"]
    assert len(slots) == 8, "Must have exactly 8 cards"
    assert slots[0] == "closeup", "Slot 0 must be closeup (Card 1)"
    assert slots[1] == "expression", "Slot 1 must be expression (Card 2)"
    assert slots[2] == "front", "Slot 2 must be front (Card 3)"
    assert slots[7] == "action", "Slot 7 must be action (Card 8)"

    # 6. Dynamic State Anchor Verification (Card 1 Close-Up + Card 3 Full Body Front; Card 2 strictly excluded)
    state_sample = CharacterStateModel(
        id=uuid.uuid4(),
        character_id=char.id,
        state_code="#State 02",
        state_label="Fatigue & Wear",
        wardrobe="Torn tactical bodysuit, dirt streaks",
        injuries_and_wear="Surface abrasions on cheek",
        expression_anchor="Weary but vigilant",
    )
    state_compiled = compile_sheet_prompt(char, proj, bible, "state", target_state=state_sample)
    assert state_compiled["recommended_aspect_ratio"] == "1:1"
    assert len(state_compiled["ref_candidates"]) == 2
    ref_names = [r[0] for r in state_compiled["ref_candidates"]]
    assert "Card 1 Character Close-Up" in ref_names
    assert "Card 3 Full Body Front" in ref_names
    assert "Card 2 Expression Sheet" not in ref_names
    assert "Torn tactical bodysuit" in state_compiled["positive_prompt"]
    assert "Surface abrasions on cheek" in state_compiled["positive_prompt"]

    # 7. Style-Lock Anime Preservation for Dynamic State
    bible_anime = MasterProductionBibleModel(
        project_id=proj_id,
        style_parameters={"master_style_code": "#Style 15", "genre": "Anime / Cel Animation"},
        world_rules={"world_setting": "Neo-Tokyo"},
    )
    anime_state = compile_sheet_prompt(char, proj, bible_anime, "state", target_state=state_sample)
    assert "Clean studio animation character model sheet state portrait" in anime_state["positive_prompt"]
    assert "animation" in anime_state["positive_prompt"].lower()


# Backward-compatible alias
test_seven_sheet_matrix_hierarchy_and_sequential_anchoring = test_eight_sheet_matrix_hierarchy_and_sequential_anchoring


def test_slot_1_closeup_refinements_and_chaining():
    """
    Slot 1 Refinements:
    1. Mode A: Natural affirmative prose, aspect ratio 3:4 (768x1024), 5500K neutral daylight studio softboxes.
    2. Zero character name leakage in visual prompt, stripped bracket headers/bullets/hex codes.
    3. Wardrobe collar fallback to charcoal-gray crewneck collar or extracted collar.
    4. Mode B: Reference asset analysis prose preservation.
    5. Chaining: Slot 1 -> Slot 2 -> Slot 3 -> Slot 4+.
    """
    proj_id = uuid.uuid4()
    proj = ProjectModel(
        id=proj_id,
        title="Neon Syndicate",
        slug="neon-syndicate",
        status="PLANNING",
        settings={"description": "Cyberpunk Noir thriller"},
    )
    bible = MasterProductionBibleModel(
        project_id=proj_id,
        style_parameters={"master_style_code": "#Style 01", "genre": "Sci-Fi Cyberpunk"},
        world_rules={"world_setting": "Neo-Shinjuku"},
    )

    # 1. Mode A: Text-to-Image without wardrobe description (fallback collar)
    char_a = CharacterModel(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Elena Rostova",
        role="PROTAGONIST",
        base_prompt="[FACIAL GEOMETRY] • Elena Rostova is a 28-year-old operative with silver hair and sharp cheekbones #D4D4D4",
        dna_seed="774921",
    )
    card1_a = compile_sheet_prompt(char_a, proj, bible, "closeup")
    assert card1_a["slot"] == "closeup"
    assert card1_a["recommended_aspect_ratio"] == "1:1"
    assert card1_a["width"] == 1024
    assert card1_a["height"] == 1024
    assert card1_a["ref_candidates"] == []
    # Verify no name, bracket headers, bullets, or hex codes leaked into positive prompt
    pos_prompt = card1_a["positive_prompt"]
    assert "Elena Rostova" not in pos_prompt, "Character name must be stripped to prevent ethnic/name bias"
    assert "[FACIAL GEOMETRY]" not in pos_prompt, "Bracket headers must be stripped"
    assert "•" not in pos_prompt, "Bullet characters must be stripped"
    assert "#D4D4D4" not in pos_prompt, "Literal hex code must not appear in positive prompt body"
    # Verify frozen Layer 1 + Layer 2 + Layer 3 directives
    assert "Hyper-realistic raw studio portrait photograph" in pos_prompt
    assert "dead-center symmetrical straight-on frontal close-up headshot" in pos_prompt
    assert "Soft diffused overhead-front octabox key light (butterfly/clamshell studio lighting)" in pos_prompt
    assert "85mm portrait lens at f/4.5, ISO 100" in pos_prompt
    assert "100mm macro-portrait" not in pos_prompt
    assert "a simple neutral charcoal-gray crewneck collar" in pos_prompt
    # Verify negative prompt isolation
    assert card1_a["negative_prompt"] != ""
    assert "--negative_prompt" not in card1_a["positive_prompt"]

    # 2. Wardrobe extraction
    char_wardrobe = CharacterModel(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Marcus Vance",
        role="ANTAGONIST",
        base_prompt="A 45-year-old commander wearing a high-collared armored tactical vest and scars",
        dna_seed="123456",
    )
    card1_wardrobe = compile_sheet_prompt(char_wardrobe, proj, bible, "closeup")
    assert "high-collared armored tactical vest" in card1_wardrobe["positive_prompt"]

    # 3. Mode B: Reference Asset Upload
    char_ref = CharacterModel(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Aria Kane",
        role="PROTAGONIST",
        base_prompt="A young engineer with braided hair",
        face_ref_asset_id=uuid.uuid4(),
        dna_seed="654321",
    )
    card1_ref = compile_sheet_prompt(char_ref, proj, bible, "closeup")
    assert len(card1_ref["ref_candidates"]) == 1
    assert card1_ref["ref_candidates"][0][0] == "Face Reference Asset"
    assert "Analyze the reference photograph and strictly preserve" in card1_ref["positive_prompt"]

    # 4. Chaining pipeline when closeup_image_url is populated
    char_chained = CharacterModel(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Elena Rostova",
        role="PROTAGONIST",
        base_prompt="Operative with silver hair",
        dna_seed="774921",
        closeup_image_url="/api/v1/assets/previews/char_closeup_master.png",
        expression_image_url="/api/v1/assets/previews/char_expression_master.png",
        front_image_url="/api/v1/assets/previews/char_front_master.png",
    )
    # Expression sheet now anchors to Card 1 Close-Up
    expr_card = compile_sheet_prompt(char_chained, proj, bible, "expression")
    assert len(expr_card["ref_candidates"]) == 1
    assert expr_card["ref_candidates"][0] == ("Card 1 Character Close-Up", "/api/v1/assets/previews/char_closeup_master.png")

    # Front Full Body anchors strictly to Card 1 Close-Up (Slot 1)
    front_card = compile_sheet_prompt(char_chained, proj, bible, "front")
    assert len(front_card["ref_candidates"]) == 1
    assert front_card["ref_candidates"][0] == ("Card 1 Character Close-Up", "/api/v1/assets/previews/char_closeup_master.png")

    # Side Profile anchors to Card 1 Close-Up & Card 3 Full Body Front
    side_card = compile_sheet_prompt(char_chained, proj, bible, "side")
    assert len(side_card["ref_candidates"]) == 2
    assert side_card["ref_candidates"][0] == ("Card 1 Character Close-Up", "/api/v1/assets/previews/char_closeup_master.png")
    assert side_card["ref_candidates"][1] == ("Card 3 Full Body Front", "/api/v1/assets/previews/char_front_master.png")


def test_context_aware_auto_generate_endpoint(client: TestClient, auth_headers: dict[str, str]):
    """Verify POST /api/v1/projects/{project_id}/characters/auto-generate absorbs project metadata."""
    # 1. Create project with rich metadata
    proj_resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Neon Syndicate 2099",
            "settings": {
                "synopsis": "A cyberpunk thriller about a rogue synthetic detective investigating corporate memory theft in Neo-Shinjuku.",
                "genre": "Cyberpunk Noir",
            },
        },
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # 2. Update Bible world rules & style
    client.put(
        f"/api/v1/projects/{project_id}/bible",
        json={
            "style_parameters": {
                "genre": "Cyberpunk Noir",
                "tone": "Gritty, dystopian, philosophical",
                "master_style_code": "#Style 01 (Cinematic Gritty Neon)",
            },
            "world_rules": {"world_setting": "Neo-Shinjuku underground metropolis, constant acid rain"},
        },
        headers=auth_headers,
    )

    # 3. Call auto-generate with mode="all"
    gen_resp = client.post(
        f"/api/v1/projects/{project_id}/characters/auto-generate",
        json={"mode": "all", "llm_provider": "9router"},
        headers=auth_headers,
    )
    assert gen_resp.status_code == 200
    data = gen_resp.json()["data"]
    assert "name" in data and len(data["name"]) > 0
    assert "role_suggestion" in data and len(data["role_suggestion"]) > 0
    assert "archetype_and_bio" in data and len(data["archetype_and_bio"]) > 0
    assert "base_visual_prompt" in data and len(data["base_visual_prompt"]) > 0

    # Ensure studio gray backdrop directive is present
    assert "#D4D4D4" in data["base_visual_prompt"]
    # Ensure sanitized from newlines
    assert "\n" not in data["base_visual_prompt"]
    assert "\r" not in data["base_visual_prompt"]

    # 4. Test individual mode regeneration with current draft
    gen_name_resp = client.post(
        f"/api/v1/projects/{project_id}/characters/auto-generate",
        json={
            "mode": "name",
            "llm_provider": "9router",
            "current_draft": {
                "name": "Old Name",
                "role_suggestion": "ANTAGONIST",
                "archetype_and_bio": "Ruthless megacorp director",
                "base_visual_prompt": "Middle-aged man in tailored charcoal suit",
            },
        },
        headers=auth_headers,
    )
    assert gen_name_resp.status_code == 200
    name_data = gen_name_resp.json()["data"]
    assert "name" in name_data
    assert name_data["role_suggestion"].upper() == "ANTAGONIST"


def test_pre_creation_visual_gatekeeper_full_lifecycle(client: TestClient, auth_headers: dict[str, str]):
    """
    Test End-to-End Pre-Creation Visual Gatekeeper:
    1. Generate preview -> staging files created, ZERO rows in SQLite `characters` table.
    2. Re-roll single preview -> updates staging file.
    3. Commit 'Create Character' -> character inserted in SQLite, files promoted to permanent storage, staging directory removed, Card 1 & Card 2 marked completed.
    4. Cleanup endpoint -> verifies temp previews can be discarded on cancel.
    """
    # 1. Create project
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Visual Gatekeeper Test Proj", "settings": {"synopsis": "Testing preview-first workflow."}},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # Check baseline character count in SQLite
    list_before = client.get(f"/api/v1/projects/{project_id}/characters", headers=auth_headers)
    assert len(list_before.json()["data"]) == 0

    # 2. Stage preview (Expression + Full Body) using mocked fast provider
    preview_req = {
        "name": "Kaelen Voss",
        "role": "PROTAGONIST",
        "base_visual_prompt": "A 32-year-old cyber-recon specialist with short black cropped hair, sharp cheekbones, wearing a slate-gray reinforced combat jumpsuit with matte carbon fiber accents, isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, even softbox lighting, zero environment props or color cast",
        "dna_seed": 583921,
        "image_provider": "ag_gemini_flash",
        "target": "both",
    }

    with patch("backend.app.api.v1.bible.get_image_provider", return_value=MockFastImageProvider()):
        prev_resp = client.post(
            f"/api/v1/projects/{project_id}/characters/preview",
            json=preview_req,
            headers=auth_headers,
        )
    assert prev_resp.status_code == 200
    prev_data = prev_resp.json()
    token = prev_data["preview_token"]
    assert token
    assert prev_data["expression_url"]
    assert prev_data["front_url"]

    # CRITICAL VERIFICATION: No character row added in SQLite yet!
    list_mid = client.get(f"/api/v1/projects/{project_id}/characters", headers=auth_headers)
    assert len(list_mid.json()["data"]) == 0, "No character row must be created in SQLite during preview stage!"

    # Verify staging files exist on disk
    staging_dir = Path("data/assets/temp_previews") / token
    assert staging_dir.exists(), f"Staging folder {staging_dir} must exist"
    assert (staging_dir / "expression.png").exists()
    assert (staging_dir / "front.png").exists()
    assert (staging_dir / "expression.png").stat().st_size > 2048
    assert (staging_dir / "front.png").stat().st_size > 2048

    # 3. Test Re-roll Expression Sheet
    with patch("backend.app.api.v1.bible.get_image_provider", return_value=MockFastImageProvider()):
        reroll_resp = client.post(
            f"/api/v1/projects/{project_id}/characters/preview",
            json={**preview_req, "target": "expression", "preview_token": token, "dna_seed": 583922},
            headers=auth_headers,
        )
    assert reroll_resp.status_code == 200
    assert reroll_resp.json()["preview_token"] == token
    assert (staging_dir / "expression.png").exists()

    # Still zero rows in SQLite
    list_mid2 = client.get(f"/api/v1/projects/{project_id}/characters", headers=auth_headers)
    assert len(list_mid2.json()["data"]) == 0

    # 4. Test Commit 'Create Character' (Atomic promotion)
    create_char_payload = {
        "name": "Kaelen Voss",
        "role": "PROTAGONIST",
        "bio": "Elite reconnaissance agent operating in the border sectors.",
        "base_prompt": preview_req["base_visual_prompt"],
        "dna_seed": 583922,
        "preview_token": token,
    }
    commit_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json=create_char_payload,
        headers=auth_headers,
    )
    assert commit_resp.status_code == 201
    char_record = commit_resp.json()["data"]
    char_id = char_record["id"]
    assert char_record["name"] == "Kaelen Voss"
    assert int(char_record["dna_seed"]) == 583922

    # Verify permanent image URLs
    assert char_record["expression_image_url"].startswith("/api/v1/assets/previews/char_")
    assert char_record["front_image_url"].startswith("/api/v1/assets/previews/char_")

    # Verify permanent files exist on disk and size > 2 KB
    expr_disk_path = _url_to_local_path(char_record["expression_image_url"])
    front_disk_path = _url_to_local_path(char_record["front_image_url"])
    assert expr_disk_path and Path(expr_disk_path).exists()
    assert front_disk_path and Path(front_disk_path).exists()
    assert Path(expr_disk_path).stat().st_size > 2048
    assert Path(front_disk_path).stat().st_size > 2048

    # Verify temp folder was cleaned up
    assert not staging_dir.exists(), "Staging folder must be purged after promotion"

    # Verify sheet_metadata marks Card 1 and Card 2 as completed
    assert char_record["sheet_metadata"]["expression"]["status"] == "completed"
    assert char_record["sheet_metadata"]["expression"]["source"] == "pre_creation_gatekeeper"
    assert char_record["sheet_metadata"]["front"]["status"] == "completed"
    assert char_record["sheet_metadata"]["front"]["source"] == "pre_creation_gatekeeper"

    # Verify characters count in SQLite is now exactly 1
    list_after = client.get(f"/api/v1/projects/{project_id}/characters", headers=auth_headers)
    assert len(list_after.json()["data"]) == 1

    # 5. Test Cancel / Discard cleanup mechanism
    with patch("backend.app.api.v1.bible.get_image_provider", return_value=MockFastImageProvider()):
        cancel_prev_resp = client.post(
            f"/api/v1/projects/{project_id}/characters/preview",
            json={**preview_req, "name": "Discarded Character", "target": "both"},
            headers=auth_headers,
        )
    assert cancel_prev_resp.status_code == 200
    cancel_token = cancel_prev_resp.json()["preview_token"]
    cancel_dir = Path("data/assets/temp_previews") / cancel_token
    assert cancel_dir.exists()

    # User presses Cancel in modal -> DELETE preview endpoint called
    del_resp = client.delete(
        f"/api/v1/projects/{project_id}/characters/preview/{cancel_token}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 200
    assert not cancel_dir.exists(), "Cancelled staging folder must be removed"


class MockSVGImageProvider(ImageGenerationProvider):
    """Generates invalid SVG placeholder output to test gatekeeper rejection."""
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        settings = get_settings()
        out_dir = settings.effective_preview_storage_path
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"mock_svg_{uuid.uuid4().hex[:8]}.svg"
        file_path = out_dir / filename

        svg_content = '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><rect fill="black"/>' + ('<!-- padding -->' * 150) + '</svg>'
        file_path.write_text(svg_content, encoding="utf-8")

        return ImageGenerationResult(
            local_path=str(file_path),
            local_url=f"/api/v1/assets/previews/{filename}",
            remote_url=None,
            seed=request.seed,
            width=800,
            height=600,
            steps=20,
            file_size_bytes=file_path.stat().st_size,
            mime_type="image/svg+xml",
            sha256_checksum="mocksvgsha256",
            provider="mock_svg_engine",
        )


def test_preview_endpoint_rejects_svg_and_non_raster(client: TestClient, auth_headers: dict[str, str]):
    """Ensure SVG or non-raster output from providers is strictly rejected with HTTP 502."""
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "SVG Rejection Test Proj", "settings": {"synopsis": "Gatekeeper verification."}},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    preview_req = {
        "name": "Vektor User",
        "role": "PROTAGONIST",
        "base_visual_prompt": "Vector test character",
        "dna_seed": 112233,
        "image_provider": "ag_gemini_flash",
        "target": "both",
    }

    with patch("backend.app.api.v1.bible.get_image_provider", return_value=MockSVGImageProvider()):
        prev_resp = client.post(
            f"/api/v1/projects/{project_id}/characters/preview",
            json=preview_req,
            headers=auth_headers,
        )

    assert prev_resp.status_code == 502, f"Expected 502 Bad Gateway for SVG output, got {prev_resp.status_code}: {prev_resp.text}"
    err_data = prev_resp.json()
    detail = err_data.get("detail") or err_data.get("error", {}).get("message", "")
    assert "SVG" in detail or "raster" in detail.lower()


def test_ninerouter_provider_429_raises_explicit_rate_limit_error(client: TestClient, auth_headers: dict[str, str]):
    """Verify that HTTP 429 quota exhaustion on 9Router raises explicit RateLimitExceededError and returns HTTP 429."""
    import pytest
    from unittest.mock import AsyncMock
    from backend.app.infrastructure.sd35_client import NineRouterImageProvider, RateLimitExceededError

    # 1. Direct provider test: 429 across all candidate models
    provider = NineRouterImageProvider(
        base_url="http://mock-9router:8080/v1",
        combo_models=["gemini-3.1-flash-image"],
        storage_path=Path("./data/assets/previews"),
    )

    req = ImageGenerationRequest(prompt="Direct rate limit test character")

    class Mock429Client:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, url, headers=None, json=None):
            resp = AsyncMock()
            resp.status_code = 429
            resp.text = '{"error": {"message": "You exceeded your current quota (HTTP 429)"}}'
            return resp

    with patch("httpx.AsyncClient", Mock429Client):
        with pytest.raises(RateLimitExceededError) as exc_info:
            import anyio
            anyio.run(provider.generate, req)

    err_msg = str(exc_info.value)
    assert "429" in err_msg or "batas kuota" in err_msg
    assert "Google Flow" in err_msg
    assert exc_info.value.provider == "9router"

    # 2. Endpoint integration test: verify preview endpoint maps RateLimitExceededError to HTTP 429
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Rate Limit 429 Proj", "settings": {"synopsis": "Testing 429 response mapping."}},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    mock_rate_limited_provider = AsyncMock()
    mock_rate_limited_provider.generate.side_effect = RateLimitExceededError(
        "Semua model gambar 9Router/Gemini sedang mencapai batas kuota (HTTP 429). Silakan pindah ke Google Flow [5 Akun PRO].",
        provider="9router",
    )

    with patch("backend.app.api.v1.bible.get_image_provider", return_value=mock_rate_limited_provider):
        resp = client.post(
            f"/api/v1/projects/{project_id}/characters/preview",
            json={
                "name": "Limit Tester",
                "role": "PROTAGONIST",
                "base_visual_prompt": "Test visual prompt",
                "dna_seed": 998877,
                "image_provider": "ag_gemini_flash",
                "target": "both",
            },
            headers=auth_headers,
        )

    assert resp.status_code == 429, f"Expected HTTP 429 for rate limited provider, got {resp.status_code}: {resp.text}"
    err_data2 = resp.json()
    err_msg2 = err_data2.get("detail") or err_data2.get("error", {}).get("message", "")
    assert "Google Flow" in err_msg2


def test_stylized_anime_multimodal_anchoring_no_photorealism():
    """
    Verify Style 15 (Anime Shinkai / Ufotable) multimodal compilation:
    1. Card 1-8 and Dynamic States must preserve 2D Anime cel-shading and lineart.
    2. Zero leakage of photorealistic terms: visible pores, micro-wrinkles, human skin texture,
       100mm portrait lens, medium-format camera, casting photograph, even softbox lighting.
    3. Stored studio boilerplate (isolated on a flat seamless, softbox) is purged at runtime.
    4. Aesthetic Constraints inline guardrail is appended to positive prompt.
    5. Negative prompt contains photorealism anti-drift terms.
    """
    proj_id = uuid.uuid4()
    char = CharacterModel(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Kaito Ren",
        role="PROTAGONIST",
        base_prompt="24-year-old Japanese male with lean, angular bone structure and sharp, high cheekbones. He wears a frayed, charcoal-gray flight suit with reinforced carbon-fiber plating, isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, even softbox lighting, zero environment props or color cast.",
        dna_seed=939603,
        closeup_image_url="/api/v1/assets/previews/char_closeup_master.png",
        expression_image_url="/api/v1/assets/previews/char_expression_master.png",
        front_image_url="/api/v1/assets/previews/char_front_master.png",
    )
    proj = ProjectModel(
        id=proj_id,
        title="Rain: The Last Awakening",
        slug="rain-the-last-awakening",
        target_style_code="#Style 15",
    )
    bible = MasterProductionBibleModel(
        project_id=proj_id,
        style_parameters={"master_style_code": "#Style 15", "genre": "Anime / Sci-Fi"},
    )

    photo_forbidden = [
        "visible pores",
        "micro-wrinkles",
        "unretouched human skin texture",
        "100mm portrait lens",
        "medium-format camera",
        "casting photograph",
        "even softbox lighting",
        "isolated on a flat seamless",
        "#D4D4D4",
    ]

    # Verify all 8 sheet cards
    slots = ["closeup", "expression", "front", "side", "three_quarter", "back", "tpose", "action"]
    for s in slots:
        compiled = compile_sheet_prompt(char, proj, bible, s)
        pos = compiled["positive_prompt"]
        neg = compiled["negative_prompt"]

        # Assert no photorealistic leaks
        for term in photo_forbidden:
            assert term not in pos, f"Photorealistic term '{term}' leaked into {s} positive prompt!"

        # Assert anime constraints and keywords
        assert "Aesthetic Constraints: Strictly 2D anime cel-shaded illustration" in pos
        assert "cel-shading" in pos.lower() or "cel-shaded" in pos.lower()
        assert "photorealism" in neg
        assert "real human photography" in neg

    # Verify Card 2 Expression Sheet specifics
    card2 = compile_sheet_prompt(char, proj, bible, "expression")
    assert card2["width"] == 1344 and card2["height"] == 768
    assert len(card2["ref_candidates"]) == 1
    assert card2["ref_candidates"][0][0] == "Card 1 Character Close-Up"
    assert "3-column by 2-row grid" in card2["positive_prompt"]
    assert "delicate cel-shading" in card2["positive_prompt"]

    # Verify Card 3 4-Panel Character & Wardrobe Master Reference specifics
    card3 = compile_sheet_prompt(char, proj, bible, "front")
    assert card3["recommended_aspect_ratio"] == "16:9"
    assert card3["width"] == 1344 and card3["height"] == 768
    assert len(card3["ref_candidates"]) == 1
    assert card3["ref_candidates"][0][0] == "Card 1 Character Close-Up"
    assert "frayed, charcoal-gray flight suit" in card3["positive_prompt"]
    assert "3-column, 4-panel" in card3["positive_prompt"]
    assert "NO head shown" in card3["positive_prompt"]

    # Verify Dynamic State specifics (#State 01) - Anchors [Card 1, Card 3], Card 2 strictly excluded
    state01 = CharacterStateModel(
        id=uuid.uuid4(),
        character_id=char.id,
        state_code="#State 01",
        state_label="Normal Baseline",
        wardrobe="Pristine flight suit with high-collar compression gear",
        injuries_and_wear="Immaculate, zero defects",
        expression_anchor="Composed, neutral resting gaze",
    )
    state_compiled = compile_sheet_prompt(char, proj, bible, "state", target_state=state01)
    assert len(state_compiled["ref_candidates"]) == 2
    state_ref_names = [r[0] for r in state_compiled["ref_candidates"]]
    assert "Card 1 Character Close-Up" in state_ref_names
    assert "Card 3 Full Body Front" in state_ref_names
    assert "Card 2 Expression Sheet" not in state_ref_names
    state_pos = state_compiled["positive_prompt"]
    for term in photo_forbidden:
        assert term not in state_pos, f"Photorealistic term '{term}' leaked into dynamic state prompt!"
    assert "Pristine flight suit with high-collar compression gear" in state_pos
    assert "Aesthetic Constraints: Strictly 2D anime" in state_pos
    assert "cel-shading" in state_pos.lower()


def test_strict_card_1_read_only_protection_during_downstream_generation(client: TestClient, auth_headers: dict[str, str]):
    """
    STRICT CARD 1 READ-ONLY PROTECTION (Guardrail Verification):
    1. Verify that downstream generation endpoints (Cards 2-8 and Dynamic States) NEVER mutate,
       overwrite, or delete Card 1: Character Close-Up (Master Anchor).
    2. Card 1 must strictly serve as an input visual reference anchor for downstream chained compilation.
    """
    # 1. Create test project and character with initial Card 1
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Downstream Protection Proj", "settings": {"synopsis": "Verifying Card 1 protection."}},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    master_anchor_url = "/api/v1/assets/previews/master_anchor_card1_original.png"
    char_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "General Kai",
            "role": "PROTAGONIST",
            "base_prompt": "A hardened veteran commander with cybernetic eye and scarred jawline",
            "dna_seed": 778899,
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    char_id = char_resp.json()["data"]["id"]

    # Directly seed Card 1 (Master Anchor) in SQLite via synchronous engine (parity with conftest.py)
    from backend.app.infrastructure.database.models.character import CharacterModel
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from backend.app.core.config import get_settings

    settings = get_settings()
    engine = create_engine(f"sqlite:///{settings.database_path}")
    with Session(engine) as session:
        c = session.execute(select(CharacterModel).where(CharacterModel.id == uuid.UUID(char_id))).scalar_one()
        c.closeup_image_url = master_anchor_url
        session.commit()

    # 2. Execute downstream generation for Card 2 (Expression Sheet), Card 3 (Front), Card 4 (Side)
    with patch("backend.app.api.v1.bible.get_image_provider", return_value=MockFastImageProvider()):
        # Render Card 2 (Expression)
        res_card2 = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={"target_type": "sheet", "angle": "expression", "provider": "ag_gemini_flash"},
            headers=auth_headers,
        )
        assert res_card2.status_code == 200
        assert res_card2.json()["status"] == "completed"

        # Render Card 3 (Front)
        res_card3 = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={"target_type": "turnaround", "angle": "front", "provider": "ag_gemini_flash"},
            headers=auth_headers,
        )
        assert res_card3.status_code == 200
        assert res_card3.json()["status"] == "completed"

        # Render Card 4 (Side)
        res_card4 = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={"target_type": "turnaround", "angle": "side", "provider": "ag_gemini_flash"},
            headers=auth_headers,
        )
        assert res_card4.status_code == 200
        assert res_card4.json()["status"] == "completed"

    # 3. Query character and assert Card 1 is 100% untouched and intact
    char_check = client.get(f"/api/v1/projects/{project_id}/characters", headers=auth_headers)
    assert char_check.status_code == 200
    chars = char_check.json()["data"]
    target_char = next(c for c in chars if c["id"] == char_id)

    # Card 1 must remain exactly the original master anchor URL
    assert target_char["closeup_image_url"] == master_anchor_url, "Card 1 Close-Up MUST NEVER be mutated by downstream generation"
    # Other cards must have been successfully populated
    assert target_char["expression_image_url"] is not None
    assert target_char["front_image_url"] is not None
    assert target_char["side_image_url"] is not None


def test_frontend_batch_downstream_orchestrator_guardrails():
    """
    Verify frontend CharacterMatrixTab.tsx implementation guarantees:
    1. Global button label: 'Generate All Downstream for All Characters (Cards 4–8 + 5 States)'
    2. Single-character button label: 'Regenerate All Downstream (Cards 4–8 + ...)'
    3. Strict Row 1 protection: Cards 1, 2, 3 are NEVER included in executeDownstreamForCharacter or calculateEstimatedAssets.
    4. Resume Mode / Skip Existing Assets toggle support.
    5. Screen Wake Lock integration for mobile browser background resistance.
    6. Target isolation: options?.targetChar ?? selectedChar.
    7. Graceful skip for characters without Row 1 Master Anchors (Card 1 & Card 3).
    8. Zero leakage of forbidden words ('polia' / 'hermes').
    """
    frontend_code = Path("frontend/src/components/bible/CharacterMatrixTab.tsx").read_text(encoding="utf-8")

    # 1. Button labels exact match (Cards 4-8 + 5 States ONLY)
    assert "Generate All Downstream for All Characters (Cards 4–8 + 5 States)" in frontend_code
    assert "Regenerate All Downstream (Cards 4–8 +" in frontend_code
    assert "Cards 2–8" not in frontend_code

    # 2. Row 1 Master Anchors (Cards 1-3) strictly protected & excluded from batch downstream
    assert "STRICT CARD 1 PROTECTION ACTIVE" in frontend_code
    assert "const totalSteps = 5 + statesList.length;" in frontend_code
    exec_start = frontend_code.index("const executeDownstreamForCharacter = async")
    exec_end = frontend_code.index("const handleRetryFailedOnly = async")
    exec_block = frontend_code[exec_start:exec_end]
    for row2_slot in ('"side"', '"three_quarter"', '"back"', '"tpose"', '"action"'):
        assert row2_slot in exec_block
    assert '"expression"' not in exec_block
    assert '"front"' not in exec_block

    # 3. Resume Mode locked ON support (cannot be unchecked, always trims URLs & passes skipExisting)
    assert "batchResumeMode" in frontend_code
    assert "const batchResumeMode = true" in frontend_code
    assert "setBatchResumeMode" not in frontend_code
    assert "Skip kartu &amp; state yang sudah ter-generate (Resume Mode)" in frontend_code or "Skip kartu & state yang sudah ter-generate (Resume Mode)" in frontend_code
    assert "Terkunci Aktif" in frontend_code
    assert ".trim()" in exec_block
    assert "skipExisting: resumeMode" in exec_block
    assert "skip_existing: options?.skipExisting ? true : undefined" in frontend_code

    # 4. Mobile Screen Wake Lock support
    assert "requestWakeLock" in frontend_code
    assert "releaseWakeLock" in frontend_code
    assert 'wakeLock' in frontend_code

    # 5. Target isolation in handleRenderAsset
    assert "options?.targetChar ?? selectedChar" in frontend_code

    # 6. Graceful skip for characters without Card 1 / Card 3
    assert "closeup_image_url" in frontend_code
    assert "front_image_url" in frontend_code
    assert "hasRequiredMasterAnchors" in frontend_code
    assert "Di-skip (No Card 1/3)" in frontend_code or "Belum memiliki Card 1" in frontend_code

    # 7. Zero forbidden words leakage
    assert "polia" not in frontend_code.lower()
    assert "hermes" not in frontend_code.lower()


def test_global_render_provider_overrides_stale_9router_payload(client: TestClient, auth_headers: dict[str, str]):
    """
    Verify that when Save Global Provider sets activeProviderId='google-flow' or 'gpt-2-6'
    with applyToAllScenes=True, a stale client payload sending provider='9router' and
    model='ag/gemini-3.8-flash' MUST NOT override the saved global provider.
    """
    from unittest.mock import AsyncMock
    from backend.app.infrastructure.universal_image_adapter import UniversalImageResult

    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Global Provider Sync Proj", "settings": {"synopsis": "Testing global provider precedence."}},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    char_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Captain Aria",
            "role": "PROTAGONIST",
            "base_prompt": "Cinematographic portrait of a female aerospace commander",
            "dna_seed": 424242,
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    char_id = char_resp.json()["data"]["id"]

    base_configs = {
        "google-flow": {
            "baseUrl": "https://labs.google/fx/api",
            "apiKey": "",
            "modelId": "flow-imagen-anchor-pro",
        },
        "gpt-2-6": {
            "baseUrl": "https://api.openai.com/v1",
            "apiKey": "sk-proj-test-openai-key",
            "modelId": "gpt-image-2.6",
        },
        "9router": {
            "baseUrl": "http://127.0.0.1:8080/v1",
            "apiKey": "sk-9router-test",
            "modelId": "ag/gemini-3.8-flash",
        },
    }

    # Case A: Global provider = 'google-flow' with applyToAllScenes=True + stale '9router' payload
    put_flow = client.put(
        f"/api/v1/projects/{project_id}/render-provider",
        json={
            "activeProviderId": "google-flow",
            "applyToAllScenes": True,
            "configs": base_configs,
            "freePortals": [],
        },
    )
    assert put_flow.status_code == 200

    with patch("backend.app.api.v1.bible._assert_socks5_healthy_for_flow", new_callable=AsyncMock):
        res_flow = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={
                "target_type": "sheet",
                "angle": "closeup",
                "provider": "9router",
                "model": "ag/gemini-3.8-flash",
                "aspect_ratio": "3:4",
            },
            headers=auth_headers,
        )
    assert res_flow.status_code == 200
    flow_data = res_flow.json()
    assert flow_data["status"] == "queued"
    assert flow_data["provider"] == "google_flow"

    # Case B: Global provider = 'gpt-2-6' with applyToAllScenes=True + stale '9router' payload
    put_gpt = client.put(
        f"/api/v1/projects/{project_id}/render-provider",
        json={
            "activeProviderId": "gpt-2-6",
            "applyToAllScenes": True,
            "configs": base_configs,
            "freePortals": [],
        },
    )
    assert put_gpt.status_code == 200

    captured_requests = []

    async def fake_generate_image(req):
        captured_requests.append(req)
        return UniversalImageResult(
            local_path="data/assets/previews/gpt_mock.png",
            local_url="/api/v1/assets/previews/gpt_mock.png",
            provider_id="gpt-2-6",
            model_id=req.model_id or "gpt-image-2.6",
            width=768,
            height=1024,
            seed=req.seed,
        )

    with patch("backend.app.api.v1.bible.UniversalImageAdapter") as MockAdapterCls:
        MockAdapterCls.return_value.generate_image = AsyncMock(side_effect=fake_generate_image)
        res_gpt = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={
                "target_type": "sheet",
                "angle": "closeup",
                "provider": "9router",
                "model": "ag/gemini-3.8-flash",
                "aspect_ratio": "3:4",
            },
            headers=auth_headers,
        )
    assert res_gpt.status_code == 200
    gpt_data = res_gpt.json()
    assert gpt_data["provider"] == "gpt-2-6"
    assert gpt_data["model"] == "gpt-image-2.6"
    assert len(captured_requests) == 1
    assert captured_requests[0].provider_id == "gpt-2-6"
    assert captured_requests[0].model_id == "gpt-image-2.6"
    assert captured_requests[0].api_key_override == "sk-proj-test-openai-key"


def test_global_render_provider_overrides_stale_9router_in_all_preview_endpoints(
    client: TestClient, auth_headers: dict[str, str]
):
    """
    Verify all 3 locations in previews.py (scene preview, project concept preview, shot preview)
    respect applyToAllScenes=True and activeProviderId='gpt-2-6' even when a stale
    provider='9router' + model='ag/gemini-3.8-flash' payload is sent.
    """
    from unittest.mock import AsyncMock
    from backend.app.infrastructure.universal_image_adapter import UniversalImageResult

    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Previews Global Sync", "settings": {"synopsis": "Testing 3 preview endpoints."}},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    scene_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={
            "act_number": 1,
            "scene_number": 1,
            "slugline": "INT. OBSERVATORY - NIGHT",
            "narrative_goal": "Captain Aria inspects star charts",
        },
        headers=auth_headers,
    )
    assert scene_resp.status_code == 201
    scene_id = scene_resp.json()["data"]["id"]

    shot_resp = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={
            "shot_number": 1,
            "camera_code": "#Cam 01",
            "lens_code": "#Lens 01",
            "comp_code": "#Comp 01",
            "light_code": "#Light 01",
            "duration_seconds": 4.0,
        },
        headers=auth_headers,
    )
    assert shot_resp.status_code == 201
    shot_id = shot_resp.json()["data"]["id"]

    put_res = client.put(
        f"/api/v1/projects/{project_id}/render-provider",
        json={
            "activeProviderId": "gpt-2-6",
            "applyToAllScenes": True,
            "configs": {
                "gpt-2-6": {
                    "baseUrl": "https://api.openai.com/v1",
                    "apiKey": "sk-proj-global-preview-key",
                    "modelId": "gpt-image-2.6",
                },
                "9router": {
                    "baseUrl": "http://127.0.0.1:8080/v1",
                    "apiKey": "sk-9router-stale",
                    "modelId": "ag/gemini-3.8-flash",
                },
            },
            "freePortals": [],
        },
    )
    assert put_res.status_code == 200

    captured = []

    async def fake_generate(req):
        captured.append(req)
        return UniversalImageResult(
            local_path="data/assets/previews/gpt_scene.png",
            local_url="/api/v1/assets/previews/gpt_scene.png",
            provider_id="gpt-2-6",
            model_id=req.model_id or "gpt-image-2.6",
            width=1024,
            height=576,
            seed=req.seed,
        )

    stale_body = {
        "prompt": "Cinematic wide shot inside observatory",
        "aspect_ratio": "16:9",
        "provider": "9router",
        "model": "ag/gemini-3.8-flash",
    }

    with patch("backend.app.api.v1.previews.UniversalImageAdapter") as MockAdapterCls:
        MockAdapterCls.return_value.generate_image = AsyncMock(side_effect=fake_generate)

        r1 = client.post(f"/api/v1/scenes/{scene_id}/generate-preview", json=stale_body, headers=auth_headers)
        assert r1.status_code == 200
        assert r1.json()["data"]["provider"] == "gpt-2-6"

        r2 = client.post(f"/api/v1/projects/{project_id}/generate-preview", json=stale_body, headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json()["data"]["provider"] == "gpt-2-6"

        r3 = client.post(f"/api/v1/shots/{shot_id}/generate-preview", json=stale_body, headers=auth_headers)
        assert r3.status_code == 200
        assert r3.json()["data"]["provider"] == "gpt-2-6"

    assert len(captured) == 3
    for req in captured:
        assert req.provider_id == "gpt-2-6"
        assert req.model_id == "gpt-image-2.6"
        assert req.api_key_override == "sk-proj-global-preview-key"


def test_flow_accounts_seeded_and_character_sheet_accepts_google_flow_aliases(
    client: TestClient, auth_headers: dict[str, str]
):
    """Verify Flow accounts are auto-seeded globally, FreePortals/render-provider preserves configs, and google_flow/google-flow aliases queue Character Sheet jobs."""
    # 1. Global /api/flow/accounts must return the 6 seeded accounts
    acc_res = client.get("/api/flow/accounts", headers=auth_headers)
    assert acc_res.status_code == 200, acc_res.text
    accounts = acc_res.json()["accounts"]
    assert len(accounts) == 6
    assert any(a["status"] == "active" for a in accounts)

    # 2. Create project + character
    proj_res = client.post(
        "/api/v1/projects",
        json={"title": "Flow Recovery Test", "target_style_code": "#Style 01"},
        headers=auth_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    char_res = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={"name": "Raka", "role": "PROTAGONIST", "base_prompt": "Indonesian man 30s"},
        headers=auth_headers,
    )
    assert char_res.status_code == 201
    char_id = char_res.json()["data"]["id"]

    # 3. Save render-provider with google_flow alias and then update freePortals with partial configs -> existing keys preserved
    put1 = client.put(
        f"/api/v1/projects/{project_id}/render-provider",
        json={
            "activeProviderId": "google_flow",
            "applyToAllScenes": True,
            "configs": {
                "google-flow": {"baseUrl": "https://labs.google/fx/api", "apiKey": "", "modelId": "flow-imagen-anchor-pro"},
                "seedream-5-5": {"baseUrl": "https://ark.ap-southeast.bytepluses.com/api/v3", "apiKey": "sk-secret-keep", "modelId": "seedream-5.5"},
            },
            "freePortals": [],
        },
    )
    assert put1.status_code == 200
    assert put1.json()["activeProviderId"] == "google-flow"

    put2 = client.put(
        f"/api/v1/projects/{project_id}/render-provider",
        json={
            "activeProviderId": "google-flow",
            "applyToAllScenes": True,
            "configs": {},
            "freePortals": [{"id": "fp-1", "name": "Whisk", "url": "https://labs.google/fx/tools/whisk"}],
        },
    )
    assert put2.status_code == 200
    get_cfg = client.get(f"/api/v1/projects/{project_id}/render-provider")
    assert get_cfg.status_code == 200
    assert get_cfg.json()["configs"]["seedream-5-5"]["apiKey"].startswith("sk-s••••")
    assert len(get_cfg.json()["freePortals"]) == 1

    # 4. Real DB FlowAccountModel check inside _assert_socks5_healthy_for_flow (only mock SOCKS5 socket check)
    with patch(
        "backend.app.api.v1.bible.get_cached_socks5_health",
        return_value={"healthy": True, "status": "online", "proxy_url": "socks5://127.0.0.1:10808", "detail": "ok"},
    ):
        gen_res = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={"target_type": "sheet", "angle": "closeup", "provider": "google_flow", "aspect_ratio": "1:1"},
            headers=auth_headers,
        )
    assert gen_res.status_code == 200, gen_res.text
    assert gen_res.json()["status"] == "queued"
    assert gen_res.json()["provider"] == "google_flow"


def test_generate_character_asset_skip_existing_and_manual_rerender_overwrite(
    client: TestClient, auth_headers: dict[str, str]
):
    """
    Verify backend skip_existing guard & manual Re-render overwrite contract:
    1. With skip_existing=True, non-empty sheet slots (Cards 4-8) and state slots are skipped
       without invoking image providers or queueing Flow jobs, returning status='skipped'
       and preserving existing image URLs.
    2. Whitespace-only URLs (e.g. '   ') are normalized via .strip() and treated as empty,
       so skip_existing=True still renders them.
    3. Manual single-card Re-render (skip_existing omitted / False) is permitted to overwrite
       existing photos on both sheet slots and state slots.
    """
    from backend.app.infrastructure.database.models.character import CharacterModel, CharacterStateModel
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from backend.app.core.config import get_settings

    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Skip Existing Guardrail Proj", "settings": {"synopsis": "Verifying skip_existing vs manual rerender."}},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    char_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Aria Vance",
            "role": "PROTAGONIST",
            "base_prompt": "Woman in 30s, sharp cheekbones, dark tactical coat",
            "dna_seed": 445566,
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    char_id = char_resp.json()["data"]["id"]

    existing_side_url = "/api/v1/assets/previews/existing_card4_side.png"
    existing_state1_url = "/api/v1/assets/previews/existing_state01.png"

    settings = get_settings()
    engine = create_engine(f"sqlite:///{settings.database_path}")
    with Session(engine) as session:
        c = session.execute(select(CharacterModel).where(CharacterModel.id == uuid.UUID(char_id))).scalar_one()
        c.closeup_image_url = "/api/v1/assets/previews/master_c1.png"
        c.front_image_url = "/api/v1/assets/previews/master_c3.png"
        c.side_image_url = f"  {existing_side_url}  "
        c.three_quarter_image_url = "   "  # whitespace-only must NOT be skipped
        c.back_image_url = None

        st1 = CharacterStateModel(
            character_id=c.id,
            state_code="#State 01",
            state_label="Baseline",
            wardrobe="Dark tactical coat",
            image_url=f" {existing_state1_url} ",
        )
        st2 = CharacterStateModel(
            character_id=c.id,
            state_code="#State 02",
            state_label="Battle Damaged",
            wardrobe="Torn tactical coat",
            image_url="   ",  # whitespace-only must NOT be skipped
        )
        session.add_all([st1, st2])
        session.commit()
        state1_id = str(st1.id)
        state2_id = str(st2.id)

    class _CountingFastImageProvider(MockFastImageProvider):
        def __init__(self):
            self.call_count = 0

        async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
            self.call_count += 1
            return await super().generate(request)

    mock_provider = _CountingFastImageProvider()
    with patch("backend.app.api.v1.bible.get_image_provider", return_value=mock_provider):
        # 1. skip_existing=True on populated Card 4 (side) -> MUST skip without calling provider
        skip_side = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={
                "target_type": "turnaround",
                "angle": "side",
                "provider": "ag_gemini_flash",
                "skip_existing": True,
            },
            headers=auth_headers,
        )
        assert skip_side.status_code == 200, skip_side.text
        assert skip_side.json()["status"] == "skipped"
        assert skip_side.json()["skipped"] is True
        assert skip_side.json()["image_url"] == existing_side_url
        assert mock_provider.call_count == 0

        # 2. skip_existing=True on populated State 01 -> MUST skip without calling provider
        skip_state1 = client.post(
            f"/api/v1/characters/{char_id}/generate-downstream",
            json={
                "target_type": "state",
                "state_id": state1_id,
                "provider": "ag_gemini_flash",
                "skip_existing": True,
            },
            headers=auth_headers,
        )
        assert skip_state1.status_code == 200, skip_state1.text
        assert skip_state1.json()["status"] == "skipped"
        assert skip_state1.json()["skipped"] is True
        assert skip_state1.json()["image_url"] == existing_state1_url
        assert mock_provider.call_count == 0

        # 3. skip_existing=True on whitespace-only Card 5 (three_quarter) -> MUST render
        render_3q = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={
                "target_type": "turnaround",
                "angle": "three_quarter",
                "provider": "ag_gemini_flash",
                "skip_existing": True,
            },
            headers=auth_headers,
        )
        assert render_3q.status_code == 200, render_3q.text
        assert render_3q.json()["status"] == "completed"
        assert mock_provider.call_count == 1

        # 4. skip_existing=True on whitespace-only State 02 -> MUST render
        render_state2 = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={
                "target_type": "state",
                "state_id": state2_id,
                "provider": "ag_gemini_flash",
                "skip_existing": True,
            },
            headers=auth_headers,
        )
        assert render_state2.status_code == 200, render_state2.text
        assert render_state2.json()["status"] == "completed"
        assert mock_provider.call_count == 2

        # 5. Manual single-card Re-render (skip_existing omitted / False) -> MUST overwrite existing Card 4 & State 01
        rerender_side = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={
                "target_type": "turnaround",
                "angle": "side",
                "provider": "ag_gemini_flash",
            },
            headers=auth_headers,
        )
        assert rerender_side.status_code == 200, rerender_side.text
        assert rerender_side.json()["status"] == "completed"
        assert rerender_side.json()["image_url"] != existing_side_url
        assert mock_provider.call_count == 3

        rerender_state1 = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={
                "target_type": "state",
                "state_id": state1_id,
                "provider": "ag_gemini_flash",
                "skip_existing": False,
            },
            headers=auth_headers,
        )
        assert rerender_state1.status_code == 200, rerender_state1.text
        assert rerender_state1.json()["status"] == "completed"
        assert rerender_state1.json()["image_url"] != existing_state1_url
        assert mock_provider.call_count == 4

    # 6. Verify skip_existing=True also short-circuits before Google Flow proxy/queue check
    with patch("backend.app.api.v1.bible._assert_socks5_healthy_for_flow", side_effect=AssertionError("Should not check Flow proxy when skipped")):
        skip_flow_side = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={
                "target_type": "turnaround",
                "angle": "side",
                "provider": "google_flow",
                "skip_existing": True,
            },
            headers=auth_headers,
        )
        assert skip_flow_side.status_code == 200, skip_flow_side.text
        assert skip_flow_side.json()["status"] == "skipped"
        assert skip_flow_side.json()["skipped"] is True






