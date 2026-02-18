"""add_indexes_for_navigation

Revision ID: 014b1562348a
Revises: 0eb320d840c1
Create Date: 2026-02-17 20:52:59.263183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '014b1562348a'
down_revision: Union[str, Sequence[str], None] = '0eb320d840c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add index on work.artist_id for faster artist -> works queries
    op.create_index(
        'ix_works_artist_id',
        'works',
        ['artist_id'],
        unique=False
    )

    # Add index on recording.work_id for faster work -> recordings queries
    op.create_index(
        'ix_recordings_work_id',
        'recordings',
        ['work_id'],
        unique=False
    )

    # Add index on recording.is_verified for filtering matched/unmatched recordings
    op.create_index(
        'ix_recordings_is_verified',
        'recordings',
        ['is_verified'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes in reverse order
    op.drop_index('ix_recordings_is_verified', table_name='recordings')
    op.drop_index('ix_recordings_work_id', table_name='recordings')
    op.drop_index('ix_works_artist_id', table_name='works')
