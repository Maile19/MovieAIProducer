"""add_character_closeup_image

Revision ID: 0007_add_character_closeup_image
Revises: 0006_expand_seven_sheet_character_matrix
Create Date: 2026-11-22 05:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007_add_character_closeup_image'
down_revision: Union[str, None] = '0006_expand_seven_sheet_character_matrix'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    char_cols = [c['name'] for c in insp.get_columns('characters')]

    # Slot 1 Master Anchor Close-Up Image Column
    if 'closeup_image_url' not in char_cols:
        op.add_column('characters', sa.Column('closeup_image_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('characters') as batch_op:
        batch_op.drop_column('closeup_image_url')
