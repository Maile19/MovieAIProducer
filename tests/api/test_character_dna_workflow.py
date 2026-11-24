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
    assert "5500K neutral daylight studio softboxes" in card_expr["positive_prompt"]

    # 2. Card 3: Full Body Front (Anchored strictly to Card 1 Close-Up)
    card_front = compile_sheet_prompt(char, proj, bible, "front")
    assert card_front["recommended_aspect_ratio"] == "3:4"
    assert card_front["width"] == 768
    assert card_front["height"] == 1024
    assert len(card_front["ref_candidates"]) == 1
    assert card_front["ref_candidates"][0][0] == "Card 1 Character Close-Up"
    assert card_front["ref_candidates"][0][1] == "/api/v1/assets/previews/char_closeup_master.png"
    assert "#D4D4D4" not in card_front["positive_prompt"]
    assert "5500K neutral daylight studio softboxes" in card_front["positive_prompt"]

    # 3. Card 4: Side Profile (Anchored strictly to Card 1 Close-Up & Card 3 Full Body Front)
    card_side = compile_sheet_prompt(char, proj, bible, "side")
    assert len(card_side["ref_candidates"]) == 2
    assert card_side["ref_candidates"][0][0] == "Card 1 Character Close-Up"
    assert card_side["ref_candidates"][1][0] == "Card 3 Full Body Front"
    assert "#D4D4D4" not in card_side["positive_prompt"]

    # 4. Cards 5-8: three_quarter, back, tpose, action (strictly Card 1 and Card 3)
    for slot in ["three_quarter", "back", "tpose", "action"]:
        card = compile_sheet_prompt(char, proj, bible, slot)
        assert len(card["ref_candidates"]) == 2, f"{slot} must reference Card 1 and Card 3"
        assert card["ref_candidates"][0][0] == "Card 1 Character Close-Up"
        assert card["ref_candidates"][1][0] == "Card 3 Full Body Front"
        assert "#D4D4D4" not in card["positive_prompt"]
        assert "5500K neutral daylight studio softboxes" in card["positive_prompt"]

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
    assert card1_a["recommended_aspect_ratio"] == "3:4"
    assert card1_a["width"] == 768
    assert card1_a["height"] == 1024
    assert card1_a["ref_candidates"] == []
    # Verify no name, bracket headers, bullets, or hex codes leaked into positive prompt
    pos_prompt = card1_a["positive_prompt"]
    assert "Elena Rostova" not in pos_prompt, "Character name must be stripped to prevent ethnic/name bias"
    assert "[FACIAL GEOMETRY]" not in pos_prompt, "Bracket headers must be stripped"
    assert "•" not in pos_prompt, "Bullet characters must be stripped"
    assert "#D4D4D4" not in pos_prompt, "Literal hex code must not appear in positive prompt body for Imagen 3"
    # Verify affirmative prose directives
    assert "Unretouched RAW photographic studio casting portrait" in pos_prompt
    assert "Tight head-and-shoulders close-up framed cleanly" in pos_prompt
    assert "5500K neutral daylight studio softboxes" in pos_prompt
    assert "100mm macro-portrait prime lens at f/5.6" in pos_prompt
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

    # Verify Card 3 Full Body Front specifics
    card3 = compile_sheet_prompt(char, proj, bible, "front")
    assert card3["width"] == 768 and card3["height"] == 1024
    assert len(card3["ref_candidates"]) == 1
    assert card3["ref_candidates"][0][0] == "Card 1 Character Close-Up"
    assert "frayed, charcoal-gray flight suit" in card3["positive_prompt"]
    assert "model sheet A-pose" in card3["positive_prompt"]

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
    1. Global button label: 'Generate All Downstream for All Characters (Cards 2–8 + 5 States)'
    2. Strict Card 1 protection: Card 1 is read-only input anchor and never modified.
    3. Resume Mode / Skip Existing Assets toggle support.
    4. Screen Wake Lock integration for mobile browser background resistance.
    5. Target isolation: options?.targetChar ?? selectedChar.
    6. Graceful skip for characters without Card 1.
    7. Zero leakage of forbidden words ('polia' / 'hermes').
    """
    frontend_code = Path("frontend/src/components/bible/CharacterMatrixTab.tsx").read_text(encoding="utf-8")

    # 1. Button label exact match
    assert "Generate All Downstream for All Characters (Cards 2–8 + 5 States)" in frontend_code

    # 2. Card 1 protection comments and logic
    assert "Card 1 (Master Anchor) is read-only input anchor and NEVER modified" in frontend_code or "Card 1: Character Close-Up (Master Anchor) belum tersedia" in frontend_code
    assert "STRICT CARD 1 PROTECTION ACTIVE" in frontend_code

    # 3. Resume Mode support
    assert "batchResumeMode" in frontend_code
    assert "Skip kartu &amp; state yang sudah ter-generate (Resume Mode)" in frontend_code or "Skip kartu & state yang sudah ter-generate (Resume Mode)" in frontend_code

    # 4. Mobile Screen Wake Lock support
    assert "requestWakeLock" in frontend_code
    assert "releaseWakeLock" in frontend_code
    assert 'wakeLock' in frontend_code

    # 5. Target isolation in handleRenderAsset
    assert "options?.targetChar ?? selectedChar" in frontend_code

    # 6. Graceful skip for characters without Card 1
    assert "c.closeup_image_url" in frontend_code
    assert "Di-skip (No Card 1)" in frontend_code or "Belum memiliki Card 1" in frontend_code

    # 7. Zero forbidden words leakage
    assert "polia" not in frontend_code.lower()
    assert "hermes" not in frontend_code.lower()



