"""Track issued upload capabilities through delete-all quiescence.

Revision ID: 20260813_0010
Revises: 20260811_0009
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260813_0010"
down_revision = "20260811_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capture_assets",
        sa.Column(
            "upload_capability_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_capture_assets_upload_capability_expires_at",
        "capture_assets",
        ["upload_capability_expires_at"],
        unique=False,
    )
    # A pre-upgrade asset of any status may still have an issued PUT URL. In
    # particular, finalize cleared upload_expires_at while the signed URL could
    # remain usable. Conservatively drain every non-deleted asset for the maximum
    # supported signed-upload lifetime plus maximum supported completion quiet
    # period (900 + 900 seconds) from migration time. Pending rows with a later
    # upload deadline still receive the completion allowance.
    op.execute(
        sa.text(
            """
            UPDATE capture_assets
            SET upload_capability_expires_at = CASE
                WHEN upload_expires_at IS NOT NULL
                     AND upload_expires_at > CURRENT_TIMESTAMP
                    THEN upload_expires_at + INTERVAL '900 seconds'
                ELSE CURRENT_TIMESTAMP + INTERVAL '1800 seconds'
            END
            WHERE deleted_at IS NULL
            """
        )
    )
    op.add_column(
        "deletion_requests",
        sa.Column(
            "upload_quiescence_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_deletion_requests_upload_quiescence_until",
        "deletion_requests",
        ["upload_quiescence_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deletion_requests_upload_quiescence_until",
        table_name="deletion_requests",
    )
    op.drop_column("deletion_requests", "upload_quiescence_until")
    op.drop_index(
        "ix_capture_assets_upload_capability_expires_at",
        table_name="capture_assets",
    )
    op.drop_column("capture_assets", "upload_capability_expires_at")
