"""add_composite_indexes_for_scanner_optimization

Revision ID: 9066bd9d27ae
Revises: 014b1562348a
Create Date: 2026-02-18 07:08:35.814498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '9066bd9d27ae'
down_revision: Union[str, Sequence[str], None] = '014b1562348a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Idempotent checks: verify indexes don't exist before creating them
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    # Only proceed if tables exist
    if 'works' not in tables or 'recordings' not in tables or 'albums' not in tables:
        return
    
    # Get existing indexes for each table
    works_indexes = {idx['name'] for idx in inspector.get_indexes('works')}
    recordings_indexes = {idx['name'] for idx in inspector.get_indexes('recordings')}
    albums_indexes = {idx['name'] for idx in inspector.get_indexes('albums')}
    
    # Add composite index on works(title, artist_id) for faster work lookups
    if 'idx_work_title_artist' not in works_indexes:
        op.create_index(
            'idx_work_title_artist',
            'works',
            ['title', 'artist_id'],
            unique=False
        )
    
    # Add composite index on recordings(work_id, title) for faster recording lookups
    if 'idx_recording_work_title' not in recordings_indexes:
        op.create_index(
            'idx_recording_work_title',
            'recordings',
            ['work_id', 'title'],
            unique=False
        )
    
    # Add composite index on albums(title, artist_id) for faster album lookups
    if 'idx_album_title_artist' not in albums_indexes:
        op.create_index(
            'idx_album_title_artist',
            'albums',
            ['title', 'artist_id'],
            unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Idempotent checks: verify indexes exist before dropping them
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    # Only proceed if tables exist
    if 'works' not in tables or 'recordings' not in tables or 'albums' not in tables:
        return
    
    # Get existing indexes for each table
    works_indexes = {idx['name'] for idx in inspector.get_indexes('works')}
    recordings_indexes = {idx['name'] for idx in inspector.get_indexes('recordings')}
    albums_indexes = {idx['name'] for idx in inspector.get_indexes('albums')}
    
    # Drop indexes in reverse order
    if 'idx_album_title_artist' in albums_indexes:
        op.drop_index('idx_album_title_artist', table_name='albums')
    if 'idx_recording_work_title' in recordings_indexes:
        op.drop_index('idx_recording_work_title', table_name='recordings')
    if 'idx_work_title_artist' in works_indexes:
        op.drop_index('idx_work_title_artist', table_name='works')
