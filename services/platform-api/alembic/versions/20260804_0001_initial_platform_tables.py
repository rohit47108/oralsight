"""Initial identity, scan, job, audit, and deletion tables.

Revision ID: 20260804_0001
Revises:
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260804_0001"
down_revision = None
branch_labels = None
depends_on = None

user_role = sa.Enum(
    "patient",
    "share_viewer",
    "clinician_pending",
    "clinician",
    "admin",
    name="user_role",
    native_enum=False,
    length=32,
)
user_status = sa.Enum(
    "active",
    "deletion_pending",
    "suspended",
    name="user_status",
    native_enum=False,
    length=32,
)
scan_status = sa.Enum(
    "draft",
    "capturing",
    "complete",
    "processing",
    "ready",
    "failed",
    "deleted",
    name="scan_status",
    native_enum=False,
    length=32,
)
capture_status = sa.Enum(
    "pending",
    "available",
    "deleted",
    name="capture_status",
    native_enum=False,
    length=32,
)
job_type = sa.Enum(
    "analysis",
    "comparison",
    "reconstruction",
    "report",
    "summary_video",
    "delete_all",
    name="job_type",
    native_enum=False,
    length=32,
)
job_status = sa.Enum(
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    name="job_status",
    native_enum=False,
    length=32,
)
deletion_status = sa.Enum(
    "requested",
    "in_progress",
    "completed",
    "failed",
    name="deletion_status",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("oidc_subject", sa.String(255), nullable=False, unique=True),
        sa.Column("role", user_role, nullable=False),
        sa.Column("status", user_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("installation_id", sa.String(128), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(120)),
        sa.Column("public_key", sa.Text()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "installation_id", name="uq_device_installation"
        ),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"])
    op.create_table(
        "consent_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id", sa.String(36), sa.ForeignKey("devices.id", ondelete="SET NULL")
        ),
        sa.Column("document_id", sa.String(120), nullable=False),
        sa.Column("document_version", sa.String(64), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "user_id", "document_id", "document_version", name="uq_consent_version"
        ),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])
    op.create_index("ix_consent_records_device_id", "consent_records", ["device_id"])
    op.create_table(
        "scan_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id", sa.String(36), sa.ForeignKey("devices.id", ondelete="SET NULL")
        ),
        sa.Column("protocol", sa.String(32), nullable=False),
        sa.Column("status", scan_status, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scan_sessions_user_id", "scan_sessions", ["user_id"])
    op.create_index("ix_scan_sessions_device_id", "scan_sessions", ["device_id"])
    op.create_table(
        "capture_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scan_session_id",
            sa.String(36),
            sa.ForeignKey("scan_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id", sa.String(36), sa.ForeignKey("devices.id", ondelete="SET NULL")
        ),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("capture_angle", sa.String(32), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("media_kind", sa.String(32), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False, unique=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("encryption_key_version", sa.String(100), nullable=False),
        sa.Column("status", capture_status, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "scan_session_id",
            "region",
            "capture_angle",
            "sequence_number",
            name="uq_capture_view_sequence",
        ),
    )
    op.create_index("ix_capture_assets_user_id", "capture_assets", ["user_id"])
    op.create_index(
        "ix_capture_assets_scan_session_id", "capture_assets", ["scan_session_id"]
    )
    op.create_index("ix_capture_assets_device_id", "capture_assets", ["device_id"])
    op.create_index(
        "ix_capture_assets_user_created", "capture_assets", ["user_id", "created_at"]
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scan_session_id",
            sa.String(36),
            sa.ForeignKey("scan_sessions.id", ondelete="CASCADE"),
        ),
        sa.Column("job_type", job_type, nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_scan_session_id", "jobs", ["scan_session_id"])
    op.create_index("ix_jobs_resource_id", "jobs", ["resource_id"])
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "scope", "idempotency_key", name="uq_idempotency_scope_key"
        ),
    )
    op.create_index(
        "ix_idempotency_records_user_id", "idempotency_records", ["user_id"]
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("actor_user_id", sa.String(36)),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_user_created", "audit_events", ["user_id", "created_at"])
    op.create_table(
        "deletion_requests",
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
            unique=True,
        ),
        sa.Column("status", deletion_status, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
    )
    op.create_index("ix_deletion_requests_user_id", "deletion_requests", ["user_id"])
    op.create_index(
        "ix_deletion_user_requested", "deletion_requests", ["user_id", "requested_at"]
    )


def downgrade() -> None:
    op.drop_table("deletion_requests")
    op.drop_table("audit_events")
    op.drop_table("idempotency_records")
    op.drop_table("jobs")
    op.drop_table("capture_assets")
    op.drop_table("scan_sessions")
    op.drop_table("consent_records")
    op.drop_table("devices")
    op.drop_table("users")
