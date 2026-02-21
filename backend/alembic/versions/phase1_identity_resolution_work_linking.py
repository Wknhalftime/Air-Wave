"""Phase 1: Identity Resolution - Add work_id columns and policy tables

This migration implements Phase 1 of the Three-Layer Identity Resolution architecture:
1. Adds work_id column to identity_bridge (nullable)
2. Adds work_id column to broadcast_logs (nullable)
3. Adds suggested_work_id column to discovery_queue (nullable)
4. Creates station_preferences table
5. Creates format_preferences table
6. Creates work_default_recordings table

This is a non-breaking migration - all new columns are nullable and existing
recording_id columns are preserved for backward compatibility.

Revision ID: phase1_work_linking
Revises: add_artist_display_name
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = "phase1_work_linking"
down_revision: Union[str, Sequence[str], None] = "add_artist_display_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add work_id columns and create policy tables."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # 1. Add work_id to identity_bridge (using batch for SQLite FK support)
    if "identity_bridge" in tables:
        identity_bridge_cols = {
            col["name"] for col in inspector.get_columns("identity_bridge")
        }
        if "work_id" not in identity_bridge_cols:
            with op.batch_alter_table("identity_bridge") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "work_id",
                        sa.Integer(),
                        nullable=True,
                    )
                )
            # Create index separately after batch operation
            op.create_index(
                "ix_identity_bridge_work_id",
                "identity_bridge",
                ["work_id"],
                unique=False,
            )

    # 2. Add work_id to broadcast_logs (using batch for SQLite FK support)
    if "broadcast_logs" in tables:
        broadcast_logs_cols = {
            col["name"] for col in inspector.get_columns("broadcast_logs")
        }
        if "work_id" not in broadcast_logs_cols:
            with op.batch_alter_table("broadcast_logs") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "work_id",
                        sa.Integer(),
                        nullable=True,
                    )
                )
            # Create index separately after batch operation
            op.create_index(
                "ix_broadcast_logs_work_id",
                "broadcast_logs",
                ["work_id"],
                unique=False,
            )

    # 3. Add suggested_work_id to discovery_queue (using batch for SQLite FK support)
    if "discovery_queue" in tables:
        discovery_queue_cols = {
            col["name"] for col in inspector.get_columns("discovery_queue")
        }
        if "suggested_work_id" not in discovery_queue_cols:
            with op.batch_alter_table("discovery_queue") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "suggested_work_id",
                        sa.Integer(),
                        nullable=True,
                    )
                )

    # 4. Create station_preferences table
    if "station_preferences" not in tables:
        op.create_table(
            "station_preferences",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("station_id", sa.Integer(), nullable=False),
            sa.Column("work_id", sa.Integer(), nullable=False),
            sa.Column("preferred_recording_id", sa.Integer(), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["station_id"],
                ["stations.id"],
            ),
            sa.ForeignKeyConstraint(
                ["work_id"],
                ["works.id"],
            ),
            sa.ForeignKeyConstraint(
                ["preferred_recording_id"],
                ["recordings.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_station_preferences_station_id",
            "station_preferences",
            ["station_id"],
            unique=False,
        )
        op.create_index(
            "ix_station_preferences_work_id",
            "station_preferences",
            ["work_id"],
            unique=False,
        )
        op.create_index(
            "idx_station_pref_lookup",
            "station_preferences",
            ["station_id", "work_id"],
            unique=False,
        )

    # 5. Create format_preferences table
    if "format_preferences" not in tables:
        op.create_table(
            "format_preferences",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("format_code", sa.String(), nullable=False),
            sa.Column("work_id", sa.Integer(), nullable=False),
            sa.Column("preferred_recording_id", sa.Integer(), nullable=False),
            sa.Column("exclude_tags", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["work_id"],
                ["works.id"],
            ),
            sa.ForeignKeyConstraint(
                ["preferred_recording_id"],
                ["recordings.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_format_preferences_format_code",
            "format_preferences",
            ["format_code"],
            unique=False,
        )
        op.create_index(
            "ix_format_preferences_work_id",
            "format_preferences",
            ["work_id"],
            unique=False,
        )
        op.create_index(
            "idx_format_pref_lookup",
            "format_preferences",
            ["format_code", "work_id"],
            unique=False,
        )

    # 6. Create work_default_recordings table
    if "work_default_recordings" not in tables:
        op.create_table(
            "work_default_recordings",
            sa.Column("work_id", sa.Integer(), nullable=False),
            sa.Column("default_recording_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["work_id"],
                ["works.id"],
            ),
            sa.ForeignKeyConstraint(
                ["default_recording_id"],
                ["recordings.id"],
            ),
            sa.PrimaryKeyConstraint("work_id"),
        )


def downgrade() -> None:
    """Remove work_id columns and policy tables."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # Drop policy tables
    if "work_default_recordings" in tables:
        op.drop_table("work_default_recordings")

    if "format_preferences" in tables:
        op.drop_index("idx_format_pref_lookup", table_name="format_preferences")
        op.drop_index("ix_format_preferences_work_id", table_name="format_preferences")
        op.drop_index(
            "ix_format_preferences_format_code", table_name="format_preferences"
        )
        op.drop_table("format_preferences")

    if "station_preferences" in tables:
        op.drop_index("idx_station_pref_lookup", table_name="station_preferences")
        op.drop_index("ix_station_preferences_work_id", table_name="station_preferences")
        op.drop_index(
            "ix_station_preferences_station_id", table_name="station_preferences"
        )
        op.drop_table("station_preferences")

    # Remove columns from existing tables using batch for SQLite
    if "discovery_queue" in tables:
        discovery_queue_cols = {
            col["name"] for col in inspector.get_columns("discovery_queue")
        }
        if "suggested_work_id" in discovery_queue_cols:
            with op.batch_alter_table("discovery_queue") as batch_op:
                batch_op.drop_column("suggested_work_id")

    if "broadcast_logs" in tables:
        broadcast_logs_cols = {
            col["name"] for col in inspector.get_columns("broadcast_logs")
        }
        if "work_id" in broadcast_logs_cols:
            broadcast_logs_indexes = {
                idx["name"] for idx in inspector.get_indexes("broadcast_logs")
            }
            if "ix_broadcast_logs_work_id" in broadcast_logs_indexes:
                op.drop_index("ix_broadcast_logs_work_id", table_name="broadcast_logs")
            with op.batch_alter_table("broadcast_logs") as batch_op:
                batch_op.drop_column("work_id")

    if "identity_bridge" in tables:
        identity_bridge_cols = {
            col["name"] for col in inspector.get_columns("identity_bridge")
        }
        if "work_id" in identity_bridge_cols:
            identity_bridge_indexes = {
                idx["name"] for idx in inspector.get_indexes("identity_bridge")
            }
            if "ix_identity_bridge_work_id" in identity_bridge_indexes:
                op.drop_index("ix_identity_bridge_work_id", table_name="identity_bridge")
            with op.batch_alter_table("identity_bridge") as batch_op:
                batch_op.drop_column("work_id")
