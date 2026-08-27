"""Align unique indexes with the SQLAlchemy model metadata."""

from alembic import op

revision = "20260815_0012"
down_revision = "20260814_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_index("ix_analysis_runs_worker_job_id")
        batch.drop_constraint("uq_analysis_runs_worker_job_id", type_="unique")
        batch.create_index(
            "ix_analysis_runs_worker_job_id", ["worker_job_id"], unique=True
        )

    op.drop_index(
        "ix_deleted_subject_tombstones_subject_fingerprint",
        table_name="deleted_subject_tombstones",
    )


def downgrade() -> None:
    op.create_index(
        "ix_deleted_subject_tombstones_subject_fingerprint",
        "deleted_subject_tombstones",
        ["subject_fingerprint"],
        unique=True,
    )

    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_index("ix_analysis_runs_worker_job_id")
        batch.create_unique_constraint(
            "uq_analysis_runs_worker_job_id", ["worker_job_id"]
        )
        batch.create_index(
            "ix_analysis_runs_worker_job_id", ["worker_job_id"], unique=False
        )
