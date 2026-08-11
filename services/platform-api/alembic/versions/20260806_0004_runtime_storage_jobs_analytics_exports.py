"""Add runtime job delivery, stored report, analytics, and export state.

Revision ID: 20260806_0004
Revises: 20260804_0003
Create Date: 2026-08-06
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260806_0004"
down_revision = "20260804_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "analytics_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("analytics_policy_version", sa.String(64)))
        batch.add_column(sa.Column("analytics_updated_at", sa.DateTime(timezone=True)))

    with op.batch_alter_table("consent_records") as batch:
        batch.drop_constraint("uq_consent_version", type_="unique")
        batch.add_column(sa.Column("document_sha256", sa.String(64)))

    with op.batch_alter_table("scan_sessions") as batch:
        batch.add_column(sa.Column("consent_record_id", sa.String(36)))
        batch.create_foreign_key(
            "fk_scan_sessions_consent_record_id",
            "consent_records",
            ["consent_record_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_scan_sessions_consent_record_id", ["consent_record_id"])

    with op.batch_alter_table("jobs") as batch:
        batch.add_column(
            sa.Column("request_payload", sa.JSON(), nullable=False, server_default="{}")
        )
        batch.add_column(sa.Column("queue_envelope", sa.Text()))
        batch.add_column(sa.Column("queue_message_id", sa.String(128)))
        batch.add_column(sa.Column("queue_published_at", sa.DateTime(timezone=True)))
        batch.add_column(
            sa.Column("cancellation_requested_at", sa.DateTime(timezone=True))
        )
        batch.add_column(sa.Column("result_outcome", sa.String(32)))
        batch.add_column(sa.Column("result_payload", sa.JSON()))
        batch.add_column(sa.Column("reason_code", sa.String(100)))
        batch.add_column(sa.Column("retention_policy", sa.JSON()))

    with op.batch_alter_table("analysis_runs") as batch:
        batch.add_column(sa.Column("worker_job_id", sa.String(36)))
        batch.create_foreign_key(
            "fk_analysis_runs_worker_job_id_jobs",
            "jobs",
            ["worker_job_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_unique_constraint(
            "uq_analysis_runs_worker_job_id", ["worker_job_id"]
        )
        batch.create_index("ix_analysis_runs_worker_job_id", ["worker_job_id"])

    with op.batch_alter_table("report_artifacts") as batch:
        batch.add_column(sa.Column("object_key", sa.String(512)))
        batch.add_column(
            sa.Column(
                "media_type",
                sa.String(80),
                nullable=False,
                server_default="application/pdf",
            )
        )
        batch.create_unique_constraint("uq_report_artifacts_object_key", ["object_key"])

    op.create_table(
        "analytics_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_name", sa.String(80), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("app_version", sa.String(32), nullable=False),
        sa.Column("surface", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analytics_events_user_id", "analytics_events", ["user_id"])
    op.create_index("ix_analytics_event_received", "analytics_events", ["received_at"])
    op.create_index(
        "ix_analytics_event_aggregate",
        "analytics_events",
        ["event_name", "platform", "outcome"],
    )

    op.create_table(
        "data_export_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("export_request_id", sa.String(36), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False, unique=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("included_files", sa.Boolean(), nullable=False),
        sa.Column("encryption_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", name="uq_data_export_job"),
        sa.UniqueConstraint("export_request_id", name="uq_data_export_request"),
    )
    op.create_index(
        "ix_data_export_artifacts_user_id", "data_export_artifacts", ["user_id"]
    )
    op.create_index(
        "ix_data_export_artifacts_job_id", "data_export_artifacts", ["job_id"]
    )
    op.create_index(
        "ix_data_export_user_created",
        "data_export_artifacts",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("data_export_artifacts")
    op.drop_table("analytics_events")

    with op.batch_alter_table("report_artifacts") as batch:
        batch.drop_constraint("uq_report_artifacts_object_key", type_="unique")
        batch.drop_column("media_type")
        batch.drop_column("object_key")

    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_index("ix_analysis_runs_worker_job_id")
        batch.drop_constraint("uq_analysis_runs_worker_job_id", type_="unique")
        batch.drop_constraint("fk_analysis_runs_worker_job_id_jobs", type_="foreignkey")
        batch.drop_column("worker_job_id")

    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("retention_policy")
        batch.drop_column("reason_code")
        batch.drop_column("result_payload")
        batch.drop_column("result_outcome")
        batch.drop_column("cancellation_requested_at")
        batch.drop_column("queue_published_at")
        batch.drop_column("queue_message_id")
        batch.drop_column("queue_envelope")
        batch.drop_column("request_payload")

    with op.batch_alter_table("scan_sessions") as batch:
        batch.drop_index("ix_scan_sessions_consent_record_id")
        batch.drop_constraint("fk_scan_sessions_consent_record_id", type_="foreignkey")
        batch.drop_column("consent_record_id")

    with op.batch_alter_table("consent_records") as batch:
        batch.drop_column("document_sha256")
        batch.create_unique_constraint(
            "uq_consent_version", ["user_id", "document_id", "document_version"]
        )

    with op.batch_alter_table("users") as batch:
        batch.drop_column("analytics_updated_at")
        batch.drop_column("analytics_policy_version")
        batch.drop_column("analytics_enabled")
