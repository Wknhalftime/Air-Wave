"""add mtime to library_files for scan index

Revision ID: add_library_file_mtime
Revises: add_verification_audit_and_is_revoked
Create Date: 2026-02-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = "add_library_file_mtime"
down_revision: Union[str, None] = "add_verification_audit_and_is_revoked"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if "library_files" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("library_files")}
    if "mtime" not in columns:
        op.add_column(
            "library_files",
            sa.Column("mtime", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if "library_files" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("library_files")}
    if "mtime" in columns:
        op.drop_column("library_files", "mtime")
