"""add musicbrainz_id to artists

Revision ID: add_artist_musicbrainz_id
Revises: add_library_file_mtime
Create Date: 2026-02-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = "add_artist_musicbrainz_id"
down_revision: Union[str, None] = "add_library_file_mtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if "artists" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("artists")}
    if "musicbrainz_id" not in columns:
        op.add_column(
            "artists",
            sa.Column(
                "musicbrainz_id",
                sa.String(36),
                nullable=True,
            ),
        )
        op.create_index(
            op.f("ix_artists_musicbrainz_id"),
            "artists",
            ["musicbrainz_id"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if "artists" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("artists")}
    if "musicbrainz_id" in columns:
        op.drop_index(
            op.f("ix_artists_musicbrainz_id"),
            table_name="artists",
        )
        op.drop_column("artists", "musicbrainz_id")
