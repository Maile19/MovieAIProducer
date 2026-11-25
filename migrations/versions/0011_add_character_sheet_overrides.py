"""add_character_sheet_overrides

Revision ID: 0011_add_character_sheet_overrides
Revises: 0010_add_flow_job_shot_id_and_dialogue_cache
Create Date: 2026-11-25 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011_add_character_sheet_overrides'
down_revision: Union[str, None] = '0010_add_flow_job_shot_id_and_dialogue_cache'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if 'characters' not in insp.get_table_names():
        return

    char_cols = [c['name'] for c in insp.get_columns('characters')]
    if 'sheet_overrides' not in char_cols:
        op.add_column(
            'characters',
            sa.Column(
                'sheet_overrides',
                sa.JSON(),
                nullable=False,
                server_default='{}',
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if 'characters' not in insp.get_table_names():
        return

    char_cols = [c['name'] for c in insp.get_columns('characters')]
    if 'sheet_overrides' in char_cols:
        with op.batch_alter_table('characters') as batch_op:
            batch_op.drop_column('sheet_overrides')
