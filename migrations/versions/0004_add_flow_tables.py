"""add_flow_tables

Revision ID: 0004_add_flow_tables
Revises: 0003_add_production_presets
Create Date: 2026-11-21 00:50:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from backend.app.infrastructure.database.types import GUID, UTCDateTime


# revision identifiers, used by Alembic.
revision: str = '0004_add_flow_tables'
down_revision: Union[str, None] = '0003_add_production_presets'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create flow_accounts table
    flow_accounts = op.create_table(
        'flow_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=64), nullable=False),
        sa.Column('profile_dir', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('cooldown_until', UTCDateTime(), nullable=True),
        sa.Column('daily_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_reset_date', sa.String(length=10), nullable=False),
        sa.Column('total_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_used_at', UTCDateTime(), nullable=True),
        sa.Column('updated_at', UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_flow_accounts')),
    )

    # 2. Create flow_image_jobs table
    op.create_table(
        'flow_image_jobs',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('project_id', GUID(), nullable=True),
        sa.Column('scene_id', GUID(), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('aspect_ratio', sa.String(length=10), nullable=False, server_default='16:9'),
        sa.Column('reference_image_paths', sa.JSON(), nullable=True),
        sa.Column('preferred_account_id', sa.Integer(), nullable=True),
        sa.Column('assigned_account_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='queued'),
        sa.Column('output_filename', sa.String(length=255), nullable=True),
        sa.Column('image_url', sa.String(length=512), nullable=True),
        sa.Column('debug_screenshot_url', sa.String(length=512), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('started_at', UTCDateTime(), nullable=True),
        sa.Column('completed_at', UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_flow_image_jobs')),
    )

    # 3. Create flow_settings table
    flow_settings = op.create_table(
        'flow_settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('key', name=op.f('pk_flow_settings')),
    )

    # 4. Seed 6 Accounts
    now = datetime.now(timezone.utc)
    today_str = now.strftime('%Y-%m-%d')
    accounts_seed = [
        {
            'id': i,
            'label': f'Akun Pro {i}',
            'profile_dir': f'/opt/flow-profiles/akun_{i}',
            'status': 'active',
            'cooldown_until': None,
            'daily_count': 0,
            'last_reset_date': today_str,
            'total_count': 0,
            'consecutive_failures': 0,
            'last_error': None,
            'last_used_at': None,
            'updated_at': now,
        }
        for i in range(1, 7)
    ]
    op.bulk_insert(flow_accounts, accounts_seed)

    # 5. Seed default flow settings
    settings_seed = [
        {'key': 'socks5_proxy', 'value': 'socks5://127.0.0.1:1080'},
        {'key': 'batch_size_per_account', 'value': '4'},
        {'key': 'min_delay_sec', 'value': '5'},
        {'key': 'max_delay_sec', 'value': '12'},
        {'key': 'cooldown_minutes', 'value': '15'},
        {'key': 'worker_enabled', 'value': 'true'},
    ]
    op.bulk_insert(flow_settings, settings_seed)


def downgrade() -> None:
    op.drop_table('flow_settings')
    op.drop_table('flow_image_jobs')
    op.drop_table('flow_accounts')
