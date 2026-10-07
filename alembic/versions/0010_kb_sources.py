"""knowledge-base articles remember an uploaded source file

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-07 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('kb_articles', sa.Column('source_name', sa.String(length=200), nullable=False, server_default=''))
    op.add_column('kb_articles', sa.Column('source_file', sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column('kb_articles', 'source_file')
    op.drop_column('kb_articles', 'source_name')
