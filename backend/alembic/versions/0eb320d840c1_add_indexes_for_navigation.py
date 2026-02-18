"""add_indexes_for_navigation

Revision ID: 0eb320d840c1
Revises: add_artist_musicbrainz_id
Create Date: 2026-02-17 20:52:15.546248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0eb320d840c1'
down_revision: Union[str, Sequence[str], None] = 'add_artist_musicbrainz_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
