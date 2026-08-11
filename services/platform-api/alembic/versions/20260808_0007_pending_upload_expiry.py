"""Bound pending capture uploads independently from data retention.

Revision ID: 20260808_0007
Revises: 20260808_0006
Create Date: 2026-08-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260808_0007"
down_revision = "20260808_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("capture_assets") as batch:
        batch.add_column(
            sa.Column(
                "upload_expires_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.current_timestamp(),
            )
        )
        batch.create_index("ix_capture_assets_upload_expires_at", ["upload_expires_at"])
    with op.batch_alter_table("capture_assets") as batch:
        batch.alter_column("upload_expires_at", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("capture_assets") as batch:
        batch.drop_index("ix_capture_assets_upload_expires_at")
        batch.drop_column("upload_expires_at")
