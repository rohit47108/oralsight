"""Add bounded, non-provisioning deletion polling receipts.

Revision ID: 20260808_0006
Revises: 20260808_0005
Create Date: 2026-08-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260808_0006"
down_revision = "20260808_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("deletion_requests") as batch:
        batch.add_column(sa.Column("subject_fingerprint", sa.String(64)))
        batch.add_column(sa.Column("retention_expires_at", sa.DateTime(timezone=True)))
        batch.create_index(
            "ix_deletion_requests_subject_fingerprint", ["subject_fingerprint"]
        )
        batch.create_index(
            "ix_deletion_requests_retention_expires_at", ["retention_expires_at"]
        )


def downgrade() -> None:
    with op.batch_alter_table("deletion_requests") as batch:
        batch.drop_index("ix_deletion_requests_retention_expires_at")
        batch.drop_index("ix_deletion_requests_subject_fingerprint")
        batch.drop_column("retention_expires_at")
        batch.drop_column("subject_fingerprint")
