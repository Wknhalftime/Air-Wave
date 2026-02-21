"""Phase 4: Drop recording_id columns from identity layer tables.

This migration drops the deprecated recording_id columns from:
- identity_bridge: recording_id -> use work_id instead
- broadcast_logs: recording_id -> use work_id instead
- discovery_queue: suggested_recording_id -> use suggested_work_id instead

CRITICAL: This migration is NOT easily reversible! Before running:
1. Ensure Phase 3 has been stable for at least 2 weeks
2. Verify all work_id columns are populated (backfill complete)
3. Create a full database backup
4. Test in staging environment first

Revision ID: phase4_drop_recording_id
Revises: (manual)
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa


revision = 'phase4_drop_recording_id'
down_revision = 'phase2_backfill_work_ids'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop deprecated recording_id columns.
    
    Phase 4 of Three-Layer Identity Resolution architecture.
    """
    # First, make work_id NOT NULL on identity_bridge
    # This ensures data integrity before dropping recording_id
    op.alter_column(
        'identity_bridge',
        'work_id',
        existing_type=sa.Integer(),
        nullable=False
    )
    
    # Drop recording_id from identity_bridge
    op.drop_constraint(
        'identity_bridge_recording_id_fkey',
        'identity_bridge',
        type_='foreignkey'
    )
    op.drop_column('identity_bridge', 'recording_id')
    
    # Drop recording_id from broadcast_logs
    # First drop the index if it exists
    op.drop_index('idx_broadcast_logs_recording_match_reason', table_name='broadcast_logs')
    op.drop_constraint(
        'broadcast_logs_recording_id_fkey',
        'broadcast_logs',
        type_='foreignkey'
    )
    op.drop_column('broadcast_logs', 'recording_id')
    
    # Drop suggested_recording_id from discovery_queue
    op.drop_constraint(
        'discovery_queue_suggested_recording_id_fkey',
        'discovery_queue',
        type_='foreignkey'
    )
    op.drop_column('discovery_queue', 'suggested_recording_id')


def downgrade() -> None:
    """Re-add recording_id columns.
    
    WARNING: This will lose any data relationships that were stored
    only in work_id. A full database restore may be required.
    """
    # Re-add suggested_recording_id to discovery_queue
    op.add_column(
        'discovery_queue',
        sa.Column('suggested_recording_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'discovery_queue_suggested_recording_id_fkey',
        'discovery_queue',
        'recordings',
        ['suggested_recording_id'],
        ['id']
    )
    
    # Re-add recording_id to broadcast_logs
    op.add_column(
        'broadcast_logs',
        sa.Column('recording_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'broadcast_logs_recording_id_fkey',
        'broadcast_logs',
        'recordings',
        ['recording_id'],
        ['id']
    )
    op.create_index(
        'idx_broadcast_logs_recording_match_reason',
        'broadcast_logs',
        ['recording_id', 'match_reason']
    )
    
    # Re-add recording_id to identity_bridge
    op.add_column(
        'identity_bridge',
        sa.Column('recording_id', sa.Integer(), nullable=False)
    )
    op.create_foreign_key(
        'identity_bridge_recording_id_fkey',
        'identity_bridge',
        'recordings',
        ['recording_id'],
        ['id']
    )
    
    # Make work_id nullable again
    op.alter_column(
        'identity_bridge',
        'work_id',
        existing_type=sa.Integer(),
        nullable=True
    )
