"""Permanently seal first-administrator bootstrap after its first use.

Revision ID: 20260811_0009
Revises: 20260810_0008
Create Date: 2026-08-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260811_0009"
down_revision = "20260810_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_bootstrap_seals",
        sa.Column("seal_key", sa.String(length=64), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("seal_key"),
    )
    # Existing installations that already have an administrator must never be
    # treated as fresh merely because this table was introduced later.
    op.execute(
        sa.text(
            """
            INSERT INTO admin_bootstrap_seals (seal_key, sealed_at)
            SELECT 'first_admin_bootstrap_v1', CURRENT_TIMESTAMP
            WHERE EXISTS (SELECT 1 FROM users WHERE role = 'admin')
            """
        )
    )


def downgrade() -> None:
    op.drop_table("admin_bootstrap_seals")
