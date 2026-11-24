from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.pipeline import (
    AssetModel,
    PromptSpecificationModel,
    QCReportModel,
)
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

HOLLYWOOD_16_STAGES_META: dict[int, dict[str, Any]] = {
    1: {
        "name": "Concept & Logline Specification",
        "phase": "Phase 1: Pre-Production & Narrative Blueprint",
        "gate": "Showrunner Logline Approval",
        "step_ref": 1,
    },
    2: {
        "name": "Genre & Visual Style Catalog (#Style)",
        "phase": "Phase 1: Pre-Production & Narrative Blueprint",
        "gate": "Art Director Style Signoff",
        "step_ref": 2,
    },
    3: {
        "name": "4-Act Storyboard & 50-Scene Blueprint",
        "phase": "Phase 1: Pre-Production & Narrative Blueprint",
        "gate": "Narrative Blueprint Freeze",
        "step_ref": 3,
    },
    4: {
        "name": "Character Profile & Voice DNA",
        "phase": "Phase 1: Pre-Production & Narrative Blueprint",
        "gate": "Casting & Character Lock",
        "step_ref": 4,
    },
    5: {
        "name": "Dynamic Character Evolution Matrix (#State)",
        "phase": "Phase 2: Visual Style & DNA Freeze",
        "gate": "Character State Matrix Lock",
        "step_ref": 5,
    },
    6: {
        "name": "Environment Bible & Hero Prop Continuity",
        "phase": "Phase 2: Visual Style & DNA Freeze",
        "gate": "Production Design Freeze",
        "step_ref": 6,
    },
    7: {
        "name": "Dialogue Pacing & Audio Bridge Calibration",
        "phase": "Phase 2: Visual Style & DNA Freeze",
        "gate": "Dialogue & Sound Script Gate",
        "step_ref": 7,
    },
    8: {
        "name": "Cinematography Optics & Framing Matrix",
        "phase": "Phase 2: Visual Style & DNA Freeze",
        "gate": "Director of Photography Approval",
        "step_ref": 8,
    },
    9: {
        "name": "Cinematic Lighting & Performance Matrix",
        "phase": "Phase 3: Generative Inference & Performance",
        "gate": "Lighting & Performance Gate",
        "step_ref": 9,
    },
    10: {
        "name": "Prompt Transpilation & Compiler Freeze",
        "phase": "Phase 3: Generative Inference & Performance",
        "gate": "Engine Prompt Lock",
        "step_ref": 10,
    },
    11: {
        "name": "Generative Video & Audio Inference Execution",
        "phase": "Phase 3: Generative Inference & Performance",
        "gate": "Raw Generation Batch Gate",
        "step_ref": 11,
    },
    12: {
        "name": "Automated Biometric & Aesthetic QC Audit",
        "phase": "Phase 3: Generative Inference & Performance",
        "gate": "Continuity Quality Gate",
        "step_ref": 12,
    },
    13: {
        "name": "Timeline Multi-Track Assembly (NLE)",
        "phase": "Phase 4: Post-Production & Showrunner Delivery",
        "gate": "Rough Cut Signoff",
        "step_ref": None,
    },
    14: {
        "name": "Cinematic Color Timing & Film Emulation",
        "phase": "Phase 4: Post-Production & Showrunner Delivery",
        "gate": "Color Timing Final Lock",
        "step_ref": None,
    },
    15: {
        "name": "Soundtrack & Foley Acoustic Mastering",
        "phase": "Phase 4: Post-Production & Showrunner Delivery",
        "gate": "Audio Master Approval",
        "step_ref": None,
    },
    16: {
        "name": "Final Showrunner Master Cut Delivery",
        "phase": "Phase 4: Post-Production & Showrunner Delivery",
        "gate": "Executive Producer Golden Cut",
        "step_ref": None,
    },
}

HOLLYWOOD_12_STEPS_META: dict[int, dict[str, str]] = {
    1: {"name": "Genre & Ratio", "code": "STEP_01", "desc": "Genre tone & aspect ratio specification"},
    2: {"name": "Visual Style", "code": "STEP_02", "desc": "Master #Style 01-18 selection"},
    3: {"name": "Story Blueprint", "code": "STEP_03", "desc": "50-scene 4-act narrative curve"},
    4: {"name": "Character DNA", "code": "STEP_04", "desc": "Biometric seed & voice profile"},
    5: {"name": "Extras Sheet", "code": "STEP_05", "desc": "Crowd ensembles & secondary cast"},
    6: {"name": "Environment & Props", "code": "STEP_06", "desc": "#Env 01-05 & #Prop 01-05 tracking"},
    7: {"name": "Dialogue & Audio", "code": "STEP_07", "desc": "5s limiter & J/L-cut transitions"},
    8: {"name": "Cinematography", "code": "STEP_08", "desc": "#Cam 01-34, #Lens 01-06, #Comp 01-08"},
    9: {"name": "Lighting Matrix", "code": "STEP_09", "desc": "#Light 01-14 volumetric illumination"},
    10: {"name": "Acting Matrix", "code": "STEP_10", "desc": "#Act 01-24 micro-expression cues"},
    11: {"name": "Motion Dynamics", "code": "STEP_11", "desc": "#Speed 01-05 velocity & parallax"},
    12: {"name": "Studio Execution", "code": "STEP_12", "desc": "Prompt compile, inference & QC"},
}


async def compute_project_pipeline_status(
    project: ProjectModel,
    session: AsyncSession,
    sync_operational_stage: bool = True,
) -> dict[str, Any]:
    """
    Centrally computes objective, deterministic status for all 16 Stages and 12 Steps.
    Enforces Artifact-First Guard (stale signoffs are automatically invalidated if underlying artifacts are missing).
    Optionally syncs project.operational_stage with the derived current_working_stage.
    """
    settings = dict(project.settings or {}) if isinstance(project.settings, dict) else {}
    gate_signoffs: dict[str, Any] = settings.get("gate_signoffs", {})

    # 1. Scenes metrics
    scene_stmt = select(
        func.count(SceneModel.id).label("total"),
        func.count(func.distinct(SceneModel.act_number)).label("acts"),
    ).where(SceneModel.project_id == project.id)
    scene_row = (await session.execute(scene_stmt)).one()
    total_scenes = scene_row.total or 0
    total_acts = scene_row.acts or 0

    # 2. Characters metrics
    char_stmt = select(
        func.count(CharacterModel.id).label("total"),
        func.count(case((CharacterModel.closeup_image_url.is_not(None), 1), else_=None)).label("with_face"),
        func.count(case((CharacterModel.voice_dna_profile.is_not(None), 1), else_=None)).label("with_voice"),
    ).where(CharacterModel.project_id == project.id)
    char_row = (await session.execute(char_stmt)).one()
    total_chars = char_row.total or 0
    chars_with_face = char_row.with_face or 0
    chars_with_voice = char_row.with_voice or 0

    # 3. Character states metrics
    state_stmt = select(func.count(CharacterStateModel.id)).join(
        CharacterModel, CharacterStateModel.character_id == CharacterModel.id
    ).where(CharacterModel.project_id == project.id)
    total_states = (await session.execute(state_stmt)).scalar() or 0

    # 4. Master Production Bible
    mpb_stmt = select(MasterProductionBibleModel).where(
        MasterProductionBibleModel.project_id == project.id
    ).order_by(MasterProductionBibleModel.version.desc()).limit(1)
    mpb = (await session.execute(mpb_stmt)).scalar_one_or_none()

    mpb_envs = []
    mpb_props = []
    mpb_locked = False
    if mpb:
        mpb_locked = bool(mpb.is_locked)
        if isinstance(mpb.world_rules, dict):
            envs = mpb.world_rules.get("environments", [])
            if isinstance(envs, list):
                mpb_envs = envs
            props = mpb.world_rules.get("props", [])
            if isinstance(props, list):
                mpb_props = props

    # 5. Shots metrics
    shot_stmt = select(
        func.count(ShotModel.id).label("total"),
        func.count(case((ShotModel.camera_code.is_not(None), 1), else_=None)).label("with_cam"),
        func.count(case((ShotModel.light_code.is_not(None), 1), else_=None)).label("with_light"),
        func.count(case((ShotModel.act_code.is_not(None), 1), else_=None)).label("with_act"),
        func.count(case((ShotModel.dialogue.is_not(None), 1), else_=None)).label("with_dialogue"),
        func.count(
            case(
                (and_(ShotModel.dialogue.is_not(None), ShotModel.duration_seconds <= 5.0), 1),
                else_=None,
            )
        ).label("calibrated_dialogue"),
    ).join(SceneModel, ShotModel.scene_id == SceneModel.id).where(SceneModel.project_id == project.id)
    shot_row = (await session.execute(shot_stmt)).one()
    total_shots = shot_row.total or 0
    shots_with_cam = shot_row.with_cam or 0
    shots_with_light = shot_row.with_light or 0
    shots_with_dialogue = shot_row.with_dialogue or 0
    shots_calibrated = shot_row.calibrated_dialogue or 0

    # 6. Prompt specifications
    ps_stmt = select(func.count(PromptSpecificationModel.id)).join(
        ShotModel, PromptSpecificationModel.shot_id == ShotModel.id
    ).join(SceneModel, ShotModel.scene_id == SceneModel.id).where(SceneModel.project_id == project.id)
    total_prompt_specs = (await session.execute(ps_stmt)).scalar() or 0

    # 7. Assets & QC
    asset_stmt = select(func.count(AssetModel.id)).where(AssetModel.project_id == project.id)
    total_assets = (await session.execute(asset_stmt)).scalar() or 0

    qc_stmt = select(
        func.count(QCReportModel.id).label("total"),
        func.count(case((QCReportModel.passed.is_(True), 1), else_=None)).label("passed"),
    ).join(ShotModel, QCReportModel.shot_id == ShotModel.id).join(
        SceneModel, ShotModel.scene_id == SceneModel.id
    ).where(SceneModel.project_id == project.id)
    qc_row = (await session.execute(qc_stmt)).one()
    total_qc = qc_row.total or 0
    passed_qc = qc_row.passed or 0

    # =========================================================================
    # Compute 16 Stages (Artifact-First Guard)
    # =========================================================================
    stages_result: dict[str, Any] = {}

    def is_gate_approved(stage_num: int) -> bool:
        key = f"S{stage_num:02d}"
        signoff = gate_signoffs.get(key)
        if isinstance(signoff, dict):
            return signoff.get("action") == "APPROVE"
        return False

    def get_gate_signoff(stage_num: int) -> dict[str, Any] | None:
        key = f"S{stage_num:02d}"
        signoff = gate_signoffs.get(key)
        return signoff if isinstance(signoff, dict) else None

    # S01: Concept & Logline Specification
    has_title = bool(project.title and project.title.strip())
    has_premise = bool(
        settings.get("logline")
        or settings.get("premise_seed")
        or settings.get("synopsis")
        or (mpb and isinstance(mpb.style_parameters, dict) and mpb.style_parameters.get("premise"))
    )
    if not has_premise:
        s01_status = "in_progress" if has_title else "not_started"
    else:
        s01_status = "completed" if is_gate_approved(1) else "awaiting_gate"

    stages_result["S01"] = {
        "stage": 1,
        **HOLLYWOOD_16_STAGES_META[1],
        "status": s01_status,
        "metrics": {"has_title": has_title, "has_premise": has_premise},
        "gate_signoff": get_gate_signoff(1),
    }

    # S02: Genre & Visual Style Catalog (#Style)
    has_explicit_style = bool(
        settings.get("style_confirmed")
        or settings.get("style_selected")
        or (mpb and isinstance(mpb.style_parameters, dict) and len(mpb.style_parameters.keys()) > 3)
        or is_gate_approved(2)
        or mpb_locked
    )
    if not has_explicit_style:
        s02_status = "not_started"
    elif is_gate_approved(2) or mpb_locked:
        s02_status = "completed"
    else:
        s02_status = "awaiting_gate"

    stages_result["S02"] = {
        "stage": 2,
        **HOLLYWOOD_16_STAGES_META[2],
        "status": s02_status,
        "metrics": {
            "target_style_code": project.target_style_code,
            "aspect_ratio": project.aspect_ratio,
            "style_confirmed": has_explicit_style,
        },
        "gate_signoff": get_gate_signoff(2),
    }

    # S03: 4-Act Storyboard & 50-Scene Blueprint (Artifact Guard: 0 scenes -> not_started)
    if total_scenes == 0:
        s03_status = "not_started"
    elif total_scenes < 12:
        s03_status = "in_progress"
    else:
        s03_status = "completed" if is_gate_approved(3) else "awaiting_gate"

    stages_result["S03"] = {
        "stage": 3,
        **HOLLYWOOD_16_STAGES_META[3],
        "status": s03_status,
        "metrics": {"scenes_count": total_scenes, "acts_count": total_acts},
        "gate_signoff": get_gate_signoff(3),
    }

    # S04: Character Profile & Voice DNA (Artifact Guard: 0 characters -> not_started)
    if total_chars == 0:
        s04_status = "not_started"
    elif chars_with_face == 0 and chars_with_voice == 0:
        s04_status = "in_progress"
    else:
        s04_status = "completed" if (is_gate_approved(4) or mpb_locked) else "awaiting_gate"

    stages_result["S04"] = {
        "stage": 4,
        **HOLLYWOOD_16_STAGES_META[4],
        "status": s04_status,
        "metrics": {
            "characters_count": total_chars,
            "with_face_anchor": chars_with_face,
            "with_voice_profile": chars_with_voice,
        },
        "gate_signoff": get_gate_signoff(4),
    }

    # S05: Dynamic Character Evolution Matrix (#State) (Artifact Guard: 0 states -> not_started)
    if total_states == 0:
        s05_status = "not_started"
    elif total_states < 2:
        s05_status = "in_progress"
    else:
        s05_status = "completed" if is_gate_approved(5) else "awaiting_gate"

    stages_result["S05"] = {
        "stage": 5,
        **HOLLYWOOD_16_STAGES_META[5],
        "status": s05_status,
        "metrics": {"character_states_count": total_states},
        "gate_signoff": get_gate_signoff(5),
    }

    # S06: Environment Bible & Hero Prop Continuity (Artifact Guard: 0 envs & 0 props -> not_started)
    has_env_props = bool(len(mpb_envs) > 0 or len(mpb_props) > 0)
    if not has_env_props:
        s06_status = "not_started"
    else:
        s06_status = "completed" if (is_gate_approved(6) or mpb_locked) else "awaiting_gate"

    stages_result["S06"] = {
        "stage": 6,
        **HOLLYWOOD_16_STAGES_META[6],
        "status": s06_status,
        "metrics": {"environments_count": len(mpb_envs), "props_count": len(mpb_props), "mpb_locked": mpb_locked},
        "gate_signoff": get_gate_signoff(6),
    }

    # S07: Dialogue Pacing & Audio Bridge Calibration
    if total_shots == 0:
        s07_status = "not_started"
    elif shots_with_dialogue == 0:
        # Shots exist without dialogue: marked in_progress or not_started based on scenes
        s07_status = "not_started"
    elif shots_calibrated < shots_with_dialogue:
        s07_status = "in_progress"
    else:
        s07_status = "completed" if is_gate_approved(7) else "awaiting_gate"

    stages_result["S07"] = {
        "stage": 7,
        **HOLLYWOOD_16_STAGES_META[7],
        "status": s07_status,
        "metrics": {"shots_with_dialogue": shots_with_dialogue, "calibrated_shots": shots_calibrated},
        "gate_signoff": get_gate_signoff(7),
    }

    # S08: Cinematography Optics & Framing Matrix
    if total_shots == 0:
        s08_status = "not_started"
    elif shots_with_cam < total_shots:
        s08_status = "in_progress"
    else:
        s08_status = "completed" if is_gate_approved(8) else "awaiting_gate"

    stages_result["S08"] = {
        "stage": 8,
        **HOLLYWOOD_16_STAGES_META[8],
        "status": s08_status,
        "metrics": {"total_shots": total_shots, "shots_with_optics": shots_with_cam},
        "gate_signoff": get_gate_signoff(8),
    }

    # S09: Cinematic Lighting & Performance Matrix
    if total_shots == 0:
        s09_status = "not_started"
    elif shots_with_light < total_shots:
        s09_status = "in_progress"
    else:
        s09_status = "completed" if is_gate_approved(9) else "awaiting_gate"

    stages_result["S09"] = {
        "stage": 9,
        **HOLLYWOOD_16_STAGES_META[9],
        "status": s09_status,
        "metrics": {"total_shots": total_shots, "shots_with_lighting": shots_with_light},
        "gate_signoff": get_gate_signoff(9),
    }

    # S10: Prompt Transpilation & Compiler Freeze
    has_prompt_specs = bool(total_prompt_specs > 0 or settings.get("prompt_specs_compiled"))
    if not has_prompt_specs:
        s10_status = "not_started"
    else:
        s10_status = "completed" if is_gate_approved(10) else "awaiting_gate"

    stages_result["S10"] = {
        "stage": 10,
        **HOLLYWOOD_16_STAGES_META[10],
        "status": s10_status,
        "metrics": {"prompt_specifications_count": total_prompt_specs},
        "gate_signoff": get_gate_signoff(10),
    }

    # S11: Generative Video & Audio Inference Execution
    has_generative_media = bool(total_assets > 0 or settings.get("preview_url"))
    if not has_generative_media:
        s11_status = "not_started"
    else:
        s11_status = "completed" if is_gate_approved(11) else "awaiting_gate"

    stages_result["S11"] = {
        "stage": 11,
        **HOLLYWOOD_16_STAGES_META[11],
        "status": s11_status,
        "metrics": {"assets_count": total_assets, "has_preview": bool(settings.get("preview_url"))},
        "gate_signoff": get_gate_signoff(11),
    }

    # S12: Automated Biometric & Aesthetic QC Audit
    if total_qc == 0:
        s12_status = "not_started"
    elif passed_qc < total_qc:
        s12_status = "in_progress"
    else:
        s12_status = "completed" if is_gate_approved(12) else "awaiting_gate"

    stages_result["S12"] = {
        "stage": 12,
        **HOLLYWOOD_16_STAGES_META[12],
        "status": s12_status,
        "metrics": {"qc_reports_count": total_qc, "passed_qc_count": passed_qc},
        "gate_signoff": get_gate_signoff(12),
    }

    # S13: Timeline Multi-Track Assembly (NLE)
    has_timeline = bool(settings.get("timeline_assembled"))
    if not has_timeline:
        s13_status = "not_started"
    else:
        s13_status = "completed" if is_gate_approved(13) else "awaiting_gate"

    stages_result["S13"] = {
        "stage": 13,
        **HOLLYWOOD_16_STAGES_META[13],
        "status": s13_status,
        "metrics": {"timeline_assembled": has_timeline},
        "gate_signoff": get_gate_signoff(13),
    }

    # S14: Cinematic Color Timing & Film Emulation
    has_color_timing = bool(settings.get("color_timing_locked"))
    if not has_color_timing:
        s14_status = "not_started"
    else:
        s14_status = "completed" if is_gate_approved(14) else "awaiting_gate"

    stages_result["S14"] = {
        "stage": 14,
        **HOLLYWOOD_16_STAGES_META[14],
        "status": s14_status,
        "metrics": {"color_timing_locked": has_color_timing},
        "gate_signoff": get_gate_signoff(14),
    }

    # S15: Soundtrack & Foley Acoustic Mastering
    has_audio_master = bool(settings.get("audio_master_locked"))
    if not has_audio_master:
        s15_status = "not_started"
    else:
        s15_status = "completed" if is_gate_approved(15) else "awaiting_gate"

    stages_result["S15"] = {
        "stage": 15,
        **HOLLYWOOD_16_STAGES_META[15],
        "status": s15_status,
        "metrics": {"audio_master_locked": has_audio_master},
        "gate_signoff": get_gate_signoff(15),
    }

    # S16: Final Showrunner Master Cut Delivery
    is_master_approved = bool(project.status == "APPROVED" or settings.get("master_cut_delivered") or is_gate_approved(16))
    all_prior_completed = all(stages_result[f"S{i:02d}"]["status"] == "completed" for i in range(1, 16))
    if is_master_approved:
        s16_status = "completed"
    elif all_prior_completed:
        s16_status = "awaiting_gate"
    else:
        s16_status = "not_started"

    stages_result["S16"] = {
        "stage": 16,
        **HOLLYWOOD_16_STAGES_META[16],
        "status": s16_status,
        "metrics": {"project_status": project.status, "master_cut_delivered": is_master_approved},
        "gate_signoff": get_gate_signoff(16),
    }

    # =========================================================================
    # Header Metrics Calculation & current_working_stage
    # =========================================================================
    completed_stages_count = sum(1 for s in stages_result.values() if s["status"] == "completed")

    # current_working_stage is the FIRST uncompleted stage, or 16 if all completed
    current_working_stage = 16
    for i in range(1, 17):
        if stages_result[f"S{i:02d}"]["status"] != "completed":
            current_working_stage = i
            break

    # Tag is_current on stages
    for key, s_val in stages_result.items():
        s_val["is_current"] = (s_val["stage"] == current_working_stage)

    # =========================================================================
    # Compute 12 Steps Mapping
    # =========================================================================
    def derive_step_status(stage_keys: list[str]) -> str:
        statuses = [stages_result[k]["status"] for k in stage_keys if k in stages_result]
        if not statuses:
            return "not_started"
        if all(st == "completed" for st in statuses):
            return "completed"
        if any(st in ["in_progress", "awaiting_gate", "completed"] for st in statuses):
            return "in_progress"
        return "not_started"

    steps_result: dict[str, Any] = {}
    step_stage_map: dict[int, list[str]] = {
        1: ["S01", "S02"],
        2: ["S02"],
        3: ["S03"],
        4: ["S04"],
        5: ["S05"],
        6: ["S06"],
        7: ["S07"],
        8: ["S08"],
        9: ["S09"],
        10: ["S09"],
        11: ["S08", "S09"],
        12: ["S10", "S11", "S12"],
    }

    for step_num in range(1, 13):
        mapped_stages = step_stage_map[step_num]
        step_meta = HOLLYWOOD_12_STEPS_META[step_num]
        step_status = derive_step_status(mapped_stages)
        steps_result[step_meta["code"]] = {
            "step": step_num,
            "code": step_meta["code"],
            "name": step_meta["name"],
            "desc": step_meta["desc"],
            "status": step_status,
            "mapped_stages": mapped_stages,
            "is_current": False,
        }

    completed_steps_count = sum(1 for st in steps_result.values() if st["status"] == "completed")
    current_working_step = 12
    for step_num in range(1, 13):
        code = HOLLYWOOD_12_STEPS_META[step_num]["code"]
        if steps_result[code]["status"] != "completed":
            current_working_step = step_num
            break

    for code, st_val in steps_result.items():
        st_val["is_current"] = (st_val["step"] == current_working_step)

    # Sync project.operational_stage if requested
    if sync_operational_stage and project.operational_stage != current_working_stage:
        project.operational_stage = current_working_stage
        project.updated_at = datetime.now(timezone.utc)

    header_metrics = {
        "current_working_stage": current_working_stage,
        "completed_stages_count": completed_stages_count,
        "total_stages": 16,
        "current_working_step": current_working_step,
        "completed_steps_count": completed_steps_count,
        "total_steps": 12,
        "progress_percentage": round((completed_stages_count / 16.0) * 100, 1),
    }

    return {
        "project_id": str(project.id),
        "header_metrics": header_metrics,
        "stages": stages_result,
        "steps": steps_result,
    }


async def apply_gate_signoff(
    project: ProjectModel,
    stage_num: int,
    action: str,
    notes: str,
    user_email: str,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """
    Applies an explicit Gate Signoff (APPROVE or REVOKE) using safe SQLAlchemy deepcopy and flag_modified.
    Recalculates pipeline status deterministically and persists changes.
    """
    if not (1 <= stage_num <= 16):
        raise ValueError(f"Invalid stage number: {stage_num}. Must be 1 to 16.")

    norm_action = action.upper().strip()
    if norm_action not in ["APPROVE", "REVOKE"]:
        raise ValueError(f"Invalid action: {action}. Must be APPROVE or REVOKE.")

    # 1. Deepcopy settings to ensure mutation tracking in SQLAlchemy
    updated_settings = copy.deepcopy(project.settings or {})
    gate_signoffs = dict(updated_settings.get("gate_signoffs", {}))

    key = f"S{stage_num:02d}"
    now = datetime.now(timezone.utc)

    if norm_action == "APPROVE":
        gate_signoffs[key] = {
            "action": "APPROVE",
            "stage": stage_num,
            "notes": notes.strip(),
            "signed_by": user_email,
            "signed_by_user_id": str(user_id),
            "timestamp": now.isoformat(),
        }
    else:
        # REVOKE / Reopen Gate
        gate_signoffs[key] = {
            "action": "REVOKE",
            "stage": stage_num,
            "notes": notes.strip(),
            "revoked_by": user_email,
            "revoked_by_user_id": str(user_id),
            "timestamp": now.isoformat(),
        }

    updated_settings["gate_signoffs"] = gate_signoffs

    # Clean legacy stage_manually_set flag
    if "stage_manually_set" in updated_settings:
        del updated_settings["stage_manually_set"]

    project.settings = updated_settings
    flag_modified(project, "settings")

    # 2. Recompute pipeline status
    pipeline_status = await compute_project_pipeline_status(
        project,
        session,
        sync_operational_stage=True,
    )

    # Explicitly guarantee project.operational_stage is updated to current_working_stage and committed
    current_working = pipeline_status["header_metrics"]["current_working_stage"]
    project.operational_stage = current_working
    project.updated_at = now
    await session.commit()
    await session.refresh(project)

    return pipeline_status
