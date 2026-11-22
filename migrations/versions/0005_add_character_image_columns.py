"""add_character_image_columns

Revision ID: 0005_add_character_image_columns
Revises: 0004_add_flow_tables
Create Date: 2026-11-21 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_add_character_image_columns'
down_revision: Union[str, None] = '0004_add_flow_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check and add columns safely if not already present
    conn = op.get_bind()
    insp = sa.inspect(conn)
    
    char_cols = [c['name'] for c in insp.get_columns('characters')]
    if 'front_image_url' not in char_cols:
        op.add_column('characters', sa.Column('front_image_url', sa.String(length=512), nullable=True))
    if 'side_image_url' not in char_cols:
        op.add_column('characters', sa.Column('side_image_url', sa.String(length=512), nullable=True))
    if 'three_quarter_image_url' not in char_cols:
        op.add_column('characters', sa.Column('three_quarter_image_url', sa.String(length=512), nullable=True))

    state_cols = [c['name'] for c in insp.get_columns('character_states')]
    if 'image_url' not in state_cols:
        op.add_column('character_states', sa.Column('image_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('characters') as batch_op:
        batch_op.drop_column('three_quarter_image_url')
        batch_op.drop_column('side_image_url')
        batch_op.drop_column('front_image_url')

    with op.batch_alter_table('character_states') as batch_op:
        batch_op.drop_column('image_url')
