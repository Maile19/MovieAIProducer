"""expand_seven_sheet_character_matrix

Revision ID: 0006_expand_seven_sheet_character_matrix
Revises: 0005_add_character_image_columns
Create Date: 2026-11-21 14:05:00.000000

"""
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_expand_seven_sheet_character_matrix'
down_revision: Union[str, None] = '0005_add_character_image_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    char_cols = [c['name'] for c in insp.get_columns('characters')]

    # 1. 4 New High-Resolution Sheet URL Columns
    if 'back_image_url' not in char_cols:
        op.add_column('characters', sa.Column('back_image_url', sa.String(length=512), nullable=True))
    if 'tpose_image_url' not in char_cols:
        op.add_column('characters', sa.Column('tpose_image_url', sa.String(length=512), nullable=True))
    if 'action_image_url' not in char_cols:
        op.add_column('characters', sa.Column('action_image_url', sa.String(length=512), nullable=True))
    if 'expression_image_url' not in char_cols:
        op.add_column('characters', sa.Column('expression_image_url', sa.String(length=512), nullable=True))

    # 2. Persistent DNA Seed Column
    if 'dna_seed' not in char_cols:
        op.add_column('characters', sa.Column('dna_seed', sa.Integer(), nullable=True))

    # 3. Sheet Metadata (compiled prompts, anchors used, timestamps, provider info)
    if 'sheet_metadata' not in char_cols:
        op.add_column('characters', sa.Column('sheet_metadata', sa.JSON(), nullable=False, server_default='{}'))

    # 4. Deterministic SHA-256 Backfill for existing characters
    result = conn.execute(sa.text("SELECT id, dna_seed FROM characters"))
    rows = result.fetchall()
    for row in rows:
        char_id = str(row[0])
        existing_seed = row[1]
        if existing_seed is None:
            # Deterministic SHA-256 seed generation
            det_seed = int(hashlib.sha256(char_id.encode()).hexdigest()[:8], 16) % 900000 + 100000
            conn.execute(
                sa.text("UPDATE characters SET dna_seed = :seed WHERE id = :cid"),
                {"seed": det_seed, "cid": char_id}
            )


def downgrade() -> None:
    with op.batch_alter_table('characters') as batch_op:
        batch_op.drop_column('sheet_metadata')
        batch_op.drop_column('dna_seed')
        batch_op.drop_column('expression_image_url')
        batch_op.drop_column('action_image_url')
        batch_op.drop_column('tpose_image_url')
        batch_op.drop_column('back_image_url')
