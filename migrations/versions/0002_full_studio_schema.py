"""full_studio_schema

Revision ID: 0002_full_studio_schema
Revises: 0001_foundation
Create Date: 2026-11-19 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_full_studio_schema'
down_revision: Union[str, None] = '0001_foundation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.String(length=1024), nullable=True),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='SHOWRUNNER'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    )
    with op.batch_alter_table('users') as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    # 2. projects
    op.create_table(
        'projects',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PLANNING'),
        sa.Column('aspect_ratio', sa.String(length=16), nullable=False, server_default='16:9'),
        sa.Column('target_style_code', sa.String(length=16), nullable=False, server_default='#Style 01'),
        sa.Column('operational_stage', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('owner_id', sa.CHAR(36), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_projects_owner_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_projects')),
    )
    with op.batch_alter_table('projects') as batch_op:
        batch_op.create_index(batch_op.f('ix_projects_slug'), ['slug'], unique=True)

    # 3. project_members
    op.create_table(
        'project_members',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('project_id', sa.CHAR(36), nullable=False),
        sa.Column('user_id', sa.CHAR(36), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='MEMBER'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_members_project_id_projects'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_project_members_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_project_members')),
        sa.UniqueConstraint('project_id', 'user_id', name='uq_project_members_project_user'),
    )

    # 4. master_production_bibles
    op.create_table(
        'master_production_bibles',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('project_id', sa.CHAR(36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_locked', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by_user_id', sa.CHAR(36), nullable=True),
        sa.Column('style_parameters', sa.JSON(), nullable=False),
        sa.Column('world_rules', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['locked_by_user_id'], ['users.id'], name=op.f('fk_master_production_bibles_locked_by_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_master_production_bibles_project_id_projects'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_master_production_bibles')),
    )

    # 5. scenes
    op.create_table(
        'scenes',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('project_id', sa.CHAR(36), nullable=False),
        sa.Column('act_number', sa.Integer(), nullable=False),
        sa.Column('scene_number', sa.Integer(), nullable=False),
        sa.Column('slugline', sa.String(length=255), nullable=False),
        sa.Column('narrative_goal', sa.Text(), nullable=False),
        sa.Column('duration_target', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PLANNED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_scenes_project_id_projects'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_scenes')),
    )

    # 6. shots
    op.create_table(
        'shots',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('scene_id', sa.CHAR(36), nullable=False),
        sa.Column('shot_number', sa.Integer(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('camera_code', sa.String(length=16), nullable=False, server_default='#Cam 01'),
        sa.Column('lens_code', sa.String(length=16), nullable=False, server_default='#Lens 01'),
        sa.Column('comp_code', sa.String(length=16), nullable=False, server_default='#Comp 01'),
        sa.Column('light_code', sa.String(length=16), nullable=False, server_default='#Light 01'),
        sa.Column('act_code', sa.String(length=16), nullable=False, server_default='#Act 01'),
        sa.Column('speed_code', sa.String(length=16), nullable=False, server_default='#Speed 01'),
        sa.Column('fg_bg_layers', sa.JSON(), nullable=False),
        sa.Column('dialogue', sa.Text(), nullable=True),
        sa.Column('transition_type', sa.String(length=16), nullable=False, server_default='NONE'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PLANNED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], name=op.f('fk_shots_scene_id_scenes'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_shots')),
    )

    # 7. assets
    op.create_table(
        'assets',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('project_id', sa.CHAR(36), nullable=False),
        sa.Column('shot_id', sa.CHAR(36), nullable=True),
        sa.Column('asset_type', sa.String(length=32), nullable=False),
        sa.Column('storage_key', sa.String(length=255), nullable=False),
        sa.Column('sha256_checksum', sa.String(length=64), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=64), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_assets_project_id_projects'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shot_id'], ['shots.id'], name=op.f('fk_assets_shot_id_shots'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_assets')),
    )
    with op.batch_alter_table('assets') as batch_op:
        batch_op.create_index(batch_op.f('ix_assets_sha256_checksum'), ['sha256_checksum'], unique=True)

    # 8. characters
    op.create_table(
        'characters',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('project_id', sa.CHAR(36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('role', sa.String(length=64), nullable=False),
        sa.Column('base_prompt', sa.Text(), nullable=False),
        sa.Column('face_ref_asset_id', sa.CHAR(36), nullable=True),
        sa.Column('voice_ref_asset_id', sa.CHAR(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['face_ref_asset_id'], ['assets.id'], name=op.f('fk_characters_face_ref_asset_id_assets'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_characters_project_id_projects'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['voice_ref_asset_id'], ['assets.id'], name=op.f('fk_characters_voice_ref_asset_id_assets'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_characters')),
    )

    # 9. character_states
    op.create_table(
        'character_states',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('character_id', sa.CHAR(36), nullable=False),
        sa.Column('scene_id', sa.CHAR(36), nullable=True),
        sa.Column('state_code', sa.String(length=16), nullable=False),
        sa.Column('wardrobe', sa.Text(), nullable=False),
        sa.Column('injuries_and_wear', sa.Text(), nullable=False, server_default=''),
        sa.Column('expression_anchor', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], name=op.f('fk_character_states_character_id_characters'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], name=op.f('fk_character_states_scene_id_scenes'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_character_states')),
    )

    # 10. prompt_specifications
    op.create_table(
        'prompt_specifications',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('shot_id', sa.CHAR(36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('provider_target', sa.String(length=64), nullable=False),
        sa.Column('positive_prompt', sa.Text(), nullable=False),
        sa.Column('negative_prompt', sa.Text(), nullable=False, server_default=''),
        sa.Column('compiled_nodes_json', sa.JSON(), nullable=False),
        sa.Column('seed', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['shot_id'], ['shots.id'], name=op.f('fk_prompt_specifications_shot_id_shots'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_prompt_specifications')),
    )

    # 11. production_jobs
    op.create_table(
        'production_jobs',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('shot_id', sa.CHAR(36), nullable=False),
        sa.Column('prompt_spec_id', sa.CHAR(36), nullable=True),
        sa.Column('provider_name', sa.String(length=64), nullable=False),
        sa.Column('external_job_id', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='QUEUED'),
        sa.Column('progress_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['prompt_spec_id'], ['prompt_specifications.id'], name=op.f('fk_production_jobs_prompt_spec_id_prompt_specifications'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['shot_id'], ['shots.id'], name=op.f('fk_production_jobs_shot_id_shots'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_production_jobs')),
    )

    # 12. qc_reports
    op.create_table(
        'qc_reports',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('shot_id', sa.CHAR(36), nullable=False),
        sa.Column('asset_id', sa.CHAR(36), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('face_similarity', sa.Float(), nullable=True),
        sa.Column('clip_score', sa.Float(), nullable=True),
        sa.Column('aesthetic_score', sa.Float(), nullable=True),
        sa.Column('temporal_jitter', sa.Float(), nullable=True),
        sa.Column('audio_snr_db', sa.Float(), nullable=True),
        sa.Column('findings_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], name=op.f('fk_qc_reports_asset_id_assets'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['shot_id'], ['shots.id'], name=op.f('fk_qc_reports_shot_id_shots'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_qc_reports')),
    )


def downgrade() -> None:
    op.drop_table('qc_reports')
    op.drop_table('production_jobs')
    op.drop_table('prompt_specifications')
    op.drop_table('character_states')
    op.drop_table('characters')
    with op.batch_alter_table('assets') as batch_op:
        batch_op.drop_index(batch_op.f('ix_assets_sha256_checksum'))
    op.drop_table('assets')
    op.drop_table('shots')
    op.drop_table('scenes')
    op.drop_table('master_production_bibles')
    op.drop_table('project_members')
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_index(batch_op.f('ix_projects_slug'))
    op.drop_table('projects')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))
    op.drop_table('users')
