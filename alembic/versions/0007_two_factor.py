"""two-factor login for staff

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-05 22:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('staff_users', sa.Column('totp_secret', sa.String(length=64), nullable=True))
    op.add_column('staff_users', sa.Column('totp_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('staff_users', sa.Column('totp_last_step', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('staff_users', 'totp_last_step')
    op.drop_column('staff_users', 'totp_enabled')
    op.drop_column('staff_users', 'totp_secret')
