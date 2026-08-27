"""Persist account-deletion tombstones beyond receipt retention."""

from alembic import op
import sqlalchemy as sa

revision = "20260814_0011"
down_revision = "20260813_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deleted_subject_tombstones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_fingerprint", sa.String(64), nullable=False),
        sa.Column("fingerprint_key_version", sa.String(64), nullable=False),
        sa.Column("first_deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "subject_fingerprint", name="uq_deleted_subject_tombstone_fingerprint"
        ),
    )
    op.create_index(
        "ix_deleted_subject_tombstones_subject_fingerprint",
        "deleted_subject_tombstones",
        ["subject_fingerprint"],
        unique=True,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO deleted_subject_tombstones
                (id, subject_fingerprint, fingerprint_key_version, first_deleted_at, last_deleted_at)
            SELECT md5(subject_fingerprint || :legacy_suffix),
                   subject_fingerprint,
                   :legacy_key_version,
                   min(requested_at),
                   max(coalesce(completed_at, requested_at))
            FROM deletion_requests
            WHERE subject_fingerprint IS NOT NULL
            GROUP BY subject_fingerprint
            ON CONFLICT (subject_fingerprint) DO NOTHING
            """
        ).bindparams(
            legacy_suffix=":legacy-share-v1",
            legacy_key_version="legacy-share-v1",
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deleted_subject_tombstones_subject_fingerprint",
        table_name="deleted_subject_tombstones",
    )
    op.drop_table("deleted_subject_tombstones")
