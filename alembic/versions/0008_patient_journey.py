"""patient journey, medication reminders, tasks

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-05 22:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('contacts', sa.Column('journey_stage', sa.String(length=12), nullable=True))
    op.add_column('contacts', sa.Column('treatment_start', sa.Date(), nullable=True))
    op.add_column('contacts', sa.Column('treatment_months', sa.Integer(), nullable=False, server_default='6'))
    op.add_column('contacts', sa.Column('puskesmas', sa.String(length=120), nullable=False, server_default=''))
    op.add_column('contacts', sa.Column('kader_id', sa.Integer(), nullable=True))
    op.add_column('contacts', sa.Column('reminder_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('contacts', sa.Column('reminder_time', sa.String(length=5), nullable=False, server_default='07:00'))
    op.create_index('ix_contacts_journey_stage', 'contacts', ['journey_stage'])
    with op.batch_alter_table('contacts') as batch:
        batch.create_foreign_key('fk_contacts_kader', 'staff_users', ['kader_id'], ['id'], ondelete='SET NULL')

    op.create_table(
        'dose_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('followup_sent', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contact_id', 'day', name='uq_dose_contact_day'),
    )
    op.create_index('ix_dose_logs_contact_id', 'dose_logs', ['contact_id'])

    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('due', sa.Date(), nullable=True),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=8), nullable=False),
        sa.Column('outcome', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['assigned_to'], ['staff_users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['staff_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tasks_contact_id', 'tasks', ['contact_id'])
    op.create_index('ix_tasks_due', 'tasks', ['due'])
    op.create_index('ix_tasks_assigned_to', 'tasks', ['assigned_to'])


def downgrade() -> None:
    op.drop_index('ix_tasks_assigned_to', table_name='tasks')
    op.drop_index('ix_tasks_due', table_name='tasks')
    op.drop_index('ix_tasks_contact_id', table_name='tasks')
    op.drop_table('tasks')
    op.drop_index('ix_dose_logs_contact_id', table_name='dose_logs')
    op.drop_table('dose_logs')
    with op.batch_alter_table('contacts') as batch:
        batch.drop_constraint('fk_contacts_kader', type_='foreignkey')
    op.drop_index('ix_contacts_journey_stage', table_name='contacts')
    for col in ('reminder_time', 'reminder_enabled', 'kader_id', 'puskesmas', 'treatment_months',
                'treatment_start', 'journey_stage'):
        op.drop_column('contacts', col)
