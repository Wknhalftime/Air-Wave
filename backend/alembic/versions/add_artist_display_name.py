"""add display_name to artists

Revision ID: add_artist_display_name
Revises: add_artist_musicbrainz_id
Create Date: 2026-02-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = "add_artist_display_name"
down_revision: Union[str, None] = "9066bd9d27ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add display_name column to artists table."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    if "artists" not in inspector.get_table_names():
        return
    
    columns = {col["name"] for col in inspector.get_columns("artists")}
    
    if "display_name" not in columns:
        # Add the display_name column
        op.add_column(
            "artists",
            sa.Column(
                "display_name",
                sa.String(),
                nullable=True,
            ),
        )
        
        # Backfill display_name with name for existing artists
        # This ensures all artists have a display_name
        op.execute(
            """
            UPDATE artists
            SET display_name = name
            WHERE display_name IS NULL
            """
        )


def downgrade() -> None:
    """Remove display_name column from artists table."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    if "artists" not in inspector.get_table_names():
        return
    
    columns = {col["name"] for col in inspector.get_columns("artists")}
    
    if "display_name" in columns:
        # Use batch_alter_table for SQLite (doesn't support DROP COLUMN directly)
        with op.batch_alter_table("artists") as batch_op:
            batch_op.drop_column("display_name")

