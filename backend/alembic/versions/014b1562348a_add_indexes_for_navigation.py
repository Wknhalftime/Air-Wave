"""add_indexes_for_navigation

Revision ID: 014b1562348a
Revises: 0eb320d840c1
Create Date: 2026-02-17 20:52:59.263183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '014b1562348a'
down_revision: Union[str, Sequence[str], None] = '0eb320d840c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Idempotent checks: verify indexes don't exist before creating them
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    # Only proceed if tables exist
    if 'works' not in tables or 'recordings' not in tables:
        return
    
    # Get existing indexes for each table
    works_indexes = {idx['name'] for idx in inspector.get_indexes('works')}
    recordings_indexes = {idx['name'] for idx in inspector.get_indexes('recordings')}
    
    # Add index on work.artist_id for faster artist -> works queries
    if 'ix_works_artist_id' not in works_indexes:
        op.create_index(
            'ix_works_artist_id',
            'works',
            ['artist_id'],
            unique=False
        )

    # Add index on recording.work_id for faster work -> recordings queries
    if 'ix_recordings_work_id' not in recordings_indexes:
        op.create_index(
            'ix_recordings_work_id',
            'recordings',
            ['work_id'],
            unique=False
        )

    # Add index on recording.is_verified for filtering matched/unmatched recordings
    if 'ix_recordings_is_verified' not in recordings_indexes:
        op.create_index(
            'ix_recordings_is_verified',
            'recordings',
            ['is_verified'],
            unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Idempotent checks: verify indexes exist before dropping them
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    # Only proceed if tables exist
    if 'works' not in tables or 'recordings' not in tables:
        return
    
    # Get existing indexes for each table
    works_indexes = {idx['name'] for idx in inspector.get_indexes('works')}
    recordings_indexes = {idx['name'] for idx in inspector.get_indexes('recordings')}
    
    # Drop indexes in reverse order
    if 'ix_recordings_is_verified' in recordings_indexes:
        op.drop_index('ix_recordings_is_verified', table_name='recordings')
    if 'ix_recordings_work_id' in recordings_indexes:
        op.drop_index('ix_recordings_work_id', table_name='recordings')
    if 'ix_works_artist_id' in works_indexes:
        op.drop_index('ix_works_artist_id', table_name='works')
