"""Record the first validated clinician role observation.

Revision ID: 20260810_0008
Revises: 20260808_0007
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260810_0008"
down_revision = "20260808_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clinician_verifications",
        sa.Column(
            "oidc_role_observed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("clinician_verifications", "oidc_role_observed_at")
