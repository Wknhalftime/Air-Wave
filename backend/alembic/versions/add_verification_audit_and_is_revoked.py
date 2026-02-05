"""add verification audit table and is_revoked flag

Revision ID: add_verification_audit_and_is_revoked
Revises: cfc31820018f_add_match_reason
Create Date: 2026-02-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = "add_verification_audit_and_is_revoked"
down_revision: Union[str, None] = "a43de339102a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "identity_bridge" in tables:
        columns = {col["name"] for col in inspector.get_columns("identity_bridge")}
        if "is_revoked" not in columns:
            op.add_column(
                "identity_bridge",
                sa.Column(
                    "is_revoked",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )

    op.create_table(
        "verification_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("raw_artist", sa.String(), nullable=False),
        sa.Column("raw_title", sa.String(), nullable=False),
        sa.Column("recording_id", sa.Integer(), nullable=True),
        sa.Column("log_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("bridge_id", sa.Integer(), nullable=True),
        sa.Column("is_undone", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("performed_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"]),
        sa.ForeignKeyConstraint(["bridge_id"], ["identity_bridge.id"]),
    )

    op.create_index(
        "idx_verification_audit_created_at",
        "verification_audit",
        ["created_at"],
    )
    op.create_index(
        "idx_verification_audit_artist_title",
        "verification_audit",
        ["raw_artist", "raw_title"],
    )
    op.create_index(
        "idx_broadcast_logs_recording_match_reason",
        "broadcast_logs",
        ["recording_id", "match_reason"],
    )


def downgrade() -> None:
    op.drop_index("idx_broadcast_logs_recording_match_reason", table_name="broadcast_logs")
    op.drop_index("idx_verification_audit_artist_title", table_name="verification_audit")
    op.drop_index("idx_verification_audit_created_at", table_name="verification_audit")
    op.drop_table("verification_audit")

    op.drop_column("identity_bridge", "is_revoked")

