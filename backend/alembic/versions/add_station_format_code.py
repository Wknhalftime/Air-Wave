"""Add format_code column to stations table.

This enables format-based recording preferences in the Policy Layer.
Stations can be assigned format codes like 'AC', 'CHR', 'ROCK' which
the RecordingResolver uses to select appropriate recordings.

Revision ID: add_station_format_code
Revises: drop_recording_id_columns_phase4
Create Date: 2026-02-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import reflection

# revision identifiers
revision: str = "add_station_format_code"
down_revision: Union[str, None] = "phase4_drop_recording_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add format_code column to stations table."""
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    
    columns = [c["name"] for c in inspector.get_columns("stations")]
    
    if "format_code" not in columns:
        op.add_column(
            "stations",
            sa.Column("format_code", sa.String(), nullable=True),
        )
        op.create_index(
            "ix_stations_format_code",
            "stations",
            ["format_code"],
        )


def downgrade() -> None:
    """Remove format_code column from stations table."""
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    
    columns = [c["name"] for c in inspector.get_columns("stations")]
    indexes = {idx["name"] for idx in inspector.get_indexes("stations")}
    
    if "ix_stations_format_code" in indexes:
        op.drop_index("ix_stations_format_code", table_name="stations")
    
    if "format_code" in columns:
        op.drop_column("stations", "format_code")
