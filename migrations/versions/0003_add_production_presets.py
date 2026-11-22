"""add_production_presets

Revision ID: 0003_add_production_presets
Revises: 0002_full_studio_schema
Create Date: 2026-11-20 12:00:00.000000

"""
from datetime import datetime, timezone
import json
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_add_production_presets'
down_revision: Union[str, None] = '0002_full_studio_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

YOUTUBE_KIDS_COMEDY_SEED = {
    "name": "YouTube Global Kids Comedy (Non-Verbal)",
    "slug": "youtube-global-kids-comedy-non-verbal",
    "category": "kids_comedy",
    "description": "High-retention, slapstick non-verbal comedic format optimized for global YouTube algorithms. Features DreamWorks/Illumination 3D visual style, fast-paced 4.0-5.0s pacing, multi-layer depth staging, and strict biometric/aesthetic QC thresholds.",
    "is_system": True,
    "preset_data": {
        "project_defaults": {
            "aspect_ratio": "16:9",
            "target_style_code": "#Style 10",
            "genre_theme": "Kids Comedy / Slapstick Non-Verbal (Global Algorithm Friendly)",
            "format_type": "Long-form 4-Act 50-Scene",
            "target_audience": "Global Family & Kids (Universal Non-Language Dependent)",
            "operational_stage": 1,
        },
        "bible_blueprint": {
            "style_parameters": {
                "master_style_code": "#Style 10",
                "style_name": "DreamWorks / Illumination",
                "aesthetic_directives": "Snappy comedic character timing, expressive cartoon eyes, tactile stylized materials, punchy visual gags, exaggerated physical squash-and-stretch.",
                "color_grade_emulation": "High-contrast vibrant saturated primaries, crisp rim highlights, energetic bounce lighting, velvety cheerful shadows.",
                "render_pipeline": "3D Stylized Feature Animation with Raytraced Global Illumination",
                "aspect_ratio": "16:9",
                "cinematography_matrix": {
                    "preferred_lenses": [
                        {"code": "#Lens 02", "name": "35mm Wide", "usage": "Environmental slapstick interactions"},
                        {"code": "#Lens 04", "name": "24mm Ultra-Wide", "usage": "Exaggerated perspective distortion for comedy"},
                    ],
                    "preferred_compositions": [
                        {"code": "#Comp 01", "name": "Rule of Thirds", "usage": "Dynamic action and comedic chase framing"},
                        {"code": "#Comp 03", "name": "Center Symmetry", "usage": "Shock reactions and fourth-wall micro-expressions"},
                    ],
                    "preferred_lighting": [
                        {"code": "#Light 02", "name": "Volumetric God Rays", "usage": "Dramatic comedic revelations with warm 4500K beam contrast"}
                    ],
                    "preferred_speeds": [
                        {"code": "#Speed 03", "name": "Standard Narrative Dynamic (24fps)", "timing": "Brisk character staging"},
                        {"code": "#Speed 04", "name": "Fast Action / Comedic Undercranking", "timing": "Slapstick bursts and chaotic stunts"},
                    ],
                    "raw_authentic_touch": {
                        "hook_cameras": [
                            {"code": "#Cam 19", "name": "Dolly-In", "usage": "High-urgency visual hook"},
                            {"code": "#Cam 23", "name": "360 Orbital", "usage": "Spectacular visual setup"},
                        ],
                        "reaction_camera": {
                            "code": "#Cam 25",
                            "name": "Subtle Handheld",
                            "usage": "Shaky mockumentary-style funny character reactions",
                        },
                        "dynamic_states": ["#State 01", "#State 02", "#State 03"],
                    },
                },
            },
            "world_rules": {
                "physics_engine": "Cartoony elastic squash-and-stretch with rapid recovery",
                "visual_non_verbal_mode": {
                    "enabled": True,
                    "spoken_dialogue_allowed": False,
                    "override_5s_dialogue_rule": True,
                    "audio_expression_types": ["SFX", "laughter", "cartoon_vocalizations", "whistles", "exaggerated_sighs"],
                    "audio_bridges": {
                        "j_cut_offset_seconds": -1.2,
                        "l_cut_offset_seconds": 1.0,
                        "foley_emphasis": "High-priority tactile comedy sound effects (boing, whoosh, splat)",
                    },
                    "acting_directives": "Heavy focus on #Act 01 through #Act 24 comedic micro-expressions, double-takes, and wide-eyed reactions",
                },
            },
        },
        "storyboard_defaults": {
            "total_scenes": 50,
            "acts_count": 4,
            "cold_open_30s": {
                "enabled": True,
                "reserved_scenes": "01-03",
                "duration_seconds": 30.0,
                "shots_count": 6,
                "structure": {
                    "scene_01": {
                        "time_range": "0-10s",
                        "title": "In-Media-Res Shock Hook + Hero Prop Reveal",
                        "directive": "Immediate high-energy visual shock hook in media res, dramatic hero prop reveal, dynamic camera movement",
                    },
                    "scene_02": {
                        "time_range": "10-20s",
                        "title": "Fast Slapstick Chaos Tease + Main Obstacle/Rival",
                        "directive": "Fast-paced comedic chaos tease, introduce antagonist/rival obstacle, rapid slapstick gag escalation",
                    },
                    "scene_03": {
                        "time_range": "20-30s",
                        "title": "Peak Climax Preview + Freeze-Frame/Rewind Transition ke Scene 04",
                        "directive": "Preview of peak catastrophic climax, abrupt comical freeze-frame / VHS rewind sound effect transitioning to linear story at Scene 04 (Ordinary World)",
                    },
                },
            },
            "act_distribution": {
                "act_1": {"scenes": "01-12", "narrative_function": "Ordinary World, Comic Setup & Inciting Disaster"},
                "act_2": {"scenes": "13-25", "narrative_function": "Escalating Slapstick Trials & Chaos Midpoint"},
                "act_3": {"scenes": "26-38", "narrative_function": "Total Comic Catastrophe & Absurd Breakthrough"},
                "act_4": {"scenes": "39-50", "narrative_function": "Hyperactive Climax & Final Cathartic Visual Gag"},
            },
            "pacing": {
                "shot_duration_min": 4.0,
                "shot_duration_max": 5.0,
                "default_scene_duration": 10.0,
                "shots_per_scene": 2,
                "pacing_profile": "high_retention_kids",
            },
            "layer_depth_spec": {
                "foreground": "Multi-layer #FG (playful floating dust, bubbles, confetti, comic debris)",
                "midground": "Multi-layer #MG (character physical comedy and immediate obstacles)",
                "background": "Multi-layer #BG (lively colorful animated environment with subtle secondary motion)",
            },
        },
        "transpiler_rules": {
            "positive_prompt_modifiers": "3D animation, DreamWorks Illumination aesthetic, snappy comedic character timing, vibrant bouncy lighting, punchy bounce light, subsurface scattering, tactile stylized materials, volumetric god rays, high retention cinematic composition, masterpiece, 8k render",
            "negative_prompt_additions": "spoken words, subtitles, text, watermarks, realistic blood, grim dark atmosphere, scary horror elements, photorealistic human skin pores, eerie uncanny valley, deformed limbs, jerky stutter",
            "default_matrix_codes": {
                "style_code": "#Style 10",
                "lens_code": "#Lens 02",
                "comp_code": "#Comp 01",
                "light_code": "#Light 02",
                "speed_code": "#Speed 03",
                "cam_code": "#Cam 19",
                "act_code": "#Act 01",
            },
        },
        "qc_gate_thresholds": {
            "overall_score": 0.85,
            "face_similarity_insightface": 0.82,
            "clip_text_video_score": 0.80,
            "aesthetic_score": 8.0,
            "temporal_jitter_variance": 0.15,
            "audio_snr_db": 28.0,
            "gate_enforcement": "STRICT_CRITICAL_REJECTION",
        },
    },
}


def upgrade() -> None:
    # 1. Create production_presets table
    op.create_table(
        'production_presets',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('category', sa.String(length=64), nullable=False, server_default='general'),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_by_user_id', sa.CHAR(36), nullable=True),
        sa.Column('preset_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('fk_production_presets_created_by_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_production_presets')),
    )
    with op.batch_alter_table('production_presets') as batch_op:
        batch_op.create_index(batch_op.f('ix_production_presets_name'), ['name'], unique=False)
        batch_op.create_index(batch_op.f('ix_production_presets_slug'), ['slug'], unique=True)
        batch_op.create_index(batch_op.f('ix_production_presets_category'), ['category'], unique=False)

    # 2. Idempotent seed insertion
    bind = op.get_bind()
    check_query = sa.text("SELECT id FROM production_presets WHERE slug = :slug")
    existing = bind.execute(check_query, {"slug": YOUTUBE_KIDS_COMEDY_SEED["slug"]}).fetchone()

    if not existing:
        now = datetime.now(timezone.utc)
        insert_query = sa.text(
            """
            INSERT INTO production_presets (
                id, name, slug, description, category, is_system, created_by_user_id, preset_data, created_at, updated_at
            ) VALUES (
                :id, :name, :slug, :description, :category, :is_system, :created_by_user_id, :preset_data, :created_at, :updated_at
            )
            """
        )
        bind.execute(
            insert_query,
            {
                "id": str(uuid.uuid4()),
                "name": YOUTUBE_KIDS_COMEDY_SEED["name"],
                "slug": YOUTUBE_KIDS_COMEDY_SEED["slug"],
                "description": YOUTUBE_KIDS_COMEDY_SEED["description"],
                "category": YOUTUBE_KIDS_COMEDY_SEED["category"],
                "is_system": True,
                "created_by_user_id": None,
                "preset_data": json.dumps(YOUTUBE_KIDS_COMEDY_SEED["preset_data"]),
                "created_at": now,
                "updated_at": now,
            },
        )
    else:
        update_query = sa.text(
            """
            UPDATE production_presets
            SET preset_data = :preset_data, description = :description, updated_at = :updated_at
            WHERE slug = :slug
            """
        )
        bind.execute(
            update_query,
            {
                "preset_data": json.dumps(YOUTUBE_KIDS_COMEDY_SEED["preset_data"]),
                "description": YOUTUBE_KIDS_COMEDY_SEED["description"],
                "updated_at": datetime.now(timezone.utc),
                "slug": YOUTUBE_KIDS_COMEDY_SEED["slug"],
            },
        )


def downgrade() -> None:
    with op.batch_alter_table('production_presets') as batch_op:
        batch_op.drop_index(batch_op.f('ix_production_presets_category'))
        batch_op.drop_index(batch_op.f('ix_production_presets_slug'))
        batch_op.drop_index(batch_op.f('ix_production_presets_name'))

    op.drop_table('production_presets')
