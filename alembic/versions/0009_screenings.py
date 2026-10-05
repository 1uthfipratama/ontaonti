"""TB symptom screening sessions

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-05 23:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'screenings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('lang', sa.String(length=2), nullable=False),
        sa.Column('step', sa.Integer(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('result', sa.String(length=12), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_screenings_contact_id', 'screenings', ['contact_id'])
    op.create_index('ix_screenings_conversation_id', 'screenings', ['conversation_id'])
    op.create_index('ix_screenings_started_at', 'screenings', ['started_at'])


def downgrade() -> None:
    op.drop_index('ix_screenings_started_at', table_name='screenings')
    op.drop_index('ix_screenings_conversation_id', table_name='screenings')
    op.drop_index('ix_screenings_contact_id', table_name='screenings')
    op.drop_table('screenings')
