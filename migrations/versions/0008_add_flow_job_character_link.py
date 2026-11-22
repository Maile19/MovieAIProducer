"""add_flow_job_character_link

Revision ID: 0008_add_flow_job_character_link
Revises: 0007_add_character_closeup_image
Create Date: 2026-11-22 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from backend.app.infrastructure.database.types import GUID


# revision identifiers, used by Alembic.
revision: str = '0008_add_flow_job_character_link'
down_revision: Union[str, None] = '0007_add_character_closeup_image'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    job_cols = [c['name'] for c in insp.get_columns('flow_image_jobs')]

    if 'character_id' not in job_cols:
        op.add_column('flow_image_jobs', sa.Column('character_id', GUID(), nullable=True))
        try:
            op.create_index('ix_flow_image_jobs_character_id', 'flow_image_jobs', ['character_id'])
        except Exception:
            pass

    if 'asset_slot' not in job_cols:
        op.add_column('flow_image_jobs', sa.Column('asset_slot', sa.String(length=32), nullable=True))

    if 'target_type' not in job_cols:
        op.add_column('flow_image_jobs', sa.Column('target_type', sa.String(length=32), nullable=True))

    if 'state_id' not in job_cols:
        op.add_column('flow_image_jobs', sa.Column('state_id', GUID(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    indexes = [idx['name'] for idx in insp.get_indexes('flow_image_jobs')]

    with op.batch_alter_table('flow_image_jobs') as batch_op:
        if 'ix_flow_image_jobs_character_id' in indexes:
            batch_op.drop_index('ix_flow_image_jobs_character_id')
        batch_op.drop_column('state_id')
        batch_op.drop_column('target_type')
        batch_op.drop_column('asset_slot')
        batch_op.drop_column('character_id')
