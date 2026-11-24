"""add_character_narrative_and_state_label

Revision ID: 0009_add_character_narrative_and_state_label
Revises: 0008_add_flow_job_character_link
Create Date: 2026-11-23 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_add_character_narrative_and_state_label'
down_revision: Union[str, None] = '0008_add_flow_job_character_link'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    char_cols = [c['name'] for c in insp.get_columns('characters')]
    if 'narrative_summary' not in char_cols:
        op.add_column('characters', sa.Column('narrative_summary', sa.Text(), nullable=True))
    if 'voice_dna_profile' not in char_cols:
        op.add_column('characters', sa.Column('voice_dna_profile', sa.Text(), nullable=True))

    state_cols = [c['name'] for c in insp.get_columns('character_states')]
    if 'state_label' not in state_cols:
        op.add_column('character_states', sa.Column('state_label', sa.String(length=128), nullable=True))

    # Purge static Cipher Vance records from SQLite
    try:
        conn.execute(sa.text("DELETE FROM character_states WHERE character_id IN (SELECT id FROM characters WHERE name = 'Cipher Vance')"))
        conn.execute(sa.text("DELETE FROM characters WHERE name = 'Cipher Vance'"))
    except Exception:
        pass


def downgrade() -> None:
    with op.batch_alter_table('character_states') as batch_op:
        batch_op.drop_column('state_label')

    with op.batch_alter_table('characters') as batch_op:
        batch_op.drop_column('voice_dna_profile')
        batch_op.drop_column('narrative_summary')
