"""Phase 2: Identity Resolution - Backfill work_id from recording_id

This migration backfills the work_id columns added in Phase 1:
1. identity_bridge.work_id from recordings.work_id via recording_id
2. broadcast_logs.work_id from recordings.work_id via recording_id
3. discovery_queue.suggested_work_id from recordings.work_id via suggested_recording_id

This is an idempotent migration - it only updates rows where work_id is NULL
and recording_id is NOT NULL. It can safely be re-run.

Revision ID: phase2_backfill_work_ids
Revises: phase1_work_linking
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = "phase2_backfill_work_ids"
down_revision: Union[str, Sequence[str], None] = "phase1_work_linking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill work_id columns from recording_id relationships."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # Backfill identity_bridge.work_id
    if "identity_bridge" in tables:
        identity_bridge_cols = {
            col["name"] for col in inspector.get_columns("identity_bridge")
        }
        if "work_id" in identity_bridge_cols and "recording_id" in identity_bridge_cols:
            op.execute(
                """
                UPDATE identity_bridge
                SET work_id = (
                    SELECT r.work_id 
                    FROM recordings r 
                    WHERE r.id = identity_bridge.recording_id
                )
                WHERE work_id IS NULL AND recording_id IS NOT NULL
                """
            )

    # Backfill broadcast_logs.work_id
    if "broadcast_logs" in tables:
        broadcast_logs_cols = {
            col["name"] for col in inspector.get_columns("broadcast_logs")
        }
        if "work_id" in broadcast_logs_cols and "recording_id" in broadcast_logs_cols:
            op.execute(
                """
                UPDATE broadcast_logs
                SET work_id = (
                    SELECT r.work_id 
                    FROM recordings r 
                    WHERE r.id = broadcast_logs.recording_id
                )
                WHERE work_id IS NULL AND recording_id IS NOT NULL
                """
            )

    # Backfill discovery_queue.suggested_work_id
    if "discovery_queue" in tables:
        discovery_queue_cols = {
            col["name"] for col in inspector.get_columns("discovery_queue")
        }
        if (
            "suggested_work_id" in discovery_queue_cols
            and "suggested_recording_id" in discovery_queue_cols
        ):
            op.execute(
                """
                UPDATE discovery_queue
                SET suggested_work_id = (
                    SELECT r.work_id 
                    FROM recordings r 
                    WHERE r.id = discovery_queue.suggested_recording_id
                )
                WHERE suggested_work_id IS NULL AND suggested_recording_id IS NOT NULL
                """
            )


def downgrade() -> None:
    """Clear backfilled work_id data (original recording_id data remains intact)."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # Clear identity_bridge.work_id
    if "identity_bridge" in tables:
        identity_bridge_cols = {
            col["name"] for col in inspector.get_columns("identity_bridge")
        }
        if "work_id" in identity_bridge_cols:
            op.execute("UPDATE identity_bridge SET work_id = NULL")

    # Clear broadcast_logs.work_id
    if "broadcast_logs" in tables:
        broadcast_logs_cols = {
            col["name"] for col in inspector.get_columns("broadcast_logs")
        }
        if "work_id" in broadcast_logs_cols:
            op.execute("UPDATE broadcast_logs SET work_id = NULL")

    # Clear discovery_queue.suggested_work_id
    if "discovery_queue" in tables:
        discovery_queue_cols = {
            col["name"] for col in inspector.get_columns("discovery_queue")
        }
        if "suggested_work_id" in discovery_queue_cols:
            op.execute("UPDATE discovery_queue SET suggested_work_id = NULL")
