"""add_flow_job_shot_id_and_dialogue_cache

Revision ID: 0010_add_flow_job_shot_id_and_dialogue_cache
Revises: 0009_add_character_narrative_and_state_label
Create Date: 2026-11-24 20:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from backend.app.infrastructure.database.types import GUID


# revision identifiers, used by Alembic.
revision: str = '0010_add_flow_job_shot_id_and_dialogue_cache'
down_revision: Union[str, None] = '0009_add_character_narrative_and_state_label'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # 1. Add shot_id to flow_image_jobs if missing
    job_cols = [c['name'] for c in insp.get_columns('flow_image_jobs')]
    if 'shot_id' not in job_cols:
        op.add_column('flow_image_jobs', sa.Column('shot_id', GUID(), nullable=True))
        try:
            op.create_index('ix_flow_image_jobs_shot_id', 'flow_image_jobs', ['shot_id'])
        except Exception:
            pass

    # 2. Create dialogue_calibration_cache table if missing
    tables = insp.get_table_names()
    if 'dialogue_calibration_cache' not in tables:
        op.create_table(
            'dialogue_calibration_cache',
            sa.Column('cache_key', sa.String(length=64), primary_key=True),
            sa.Column('scene_id', GUID(), nullable=True),
            sa.Column('raw_text_hash', sa.String(length=64), nullable=False),
            sa.Column('max_seconds', sa.Float(), nullable=False),
            sa.Column('result_json', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        try:
            op.create_index('ix_dialogue_calibration_cache_scene_id', 'dialogue_calibration_cache', ['scene_id'])
        except Exception:
            pass


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()
    if 'dialogue_calibration_cache' in tables:
        op.drop_table('dialogue_calibration_cache')

    job_cols = [c['name'] for c in insp.get_columns('flow_image_jobs')]
    if 'shot_id' in job_cols:
        indexes = [idx['name'] for idx in insp.get_indexes('flow_image_jobs')]
        with op.batch_alter_table('flow_image_jobs') as batch_op:
            if 'ix_flow_image_jobs_shot_id' in indexes:
                batch_op.drop_index('ix_flow_image_jobs_shot_id')
            batch_op.drop_column('shot_id')
