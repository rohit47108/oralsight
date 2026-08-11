"""Add clinician verification, scoped grants, reviews, sharing, and access history.

Revision ID: 20260804_0003
Revises: 20260804_0002
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260804_0003"
down_revision = "20260804_0002"
branch_labels = None
depends_on = None


def _enum(*values: str, name: str, length: int = 32) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=length)


verification_status = _enum(
    "pending", "verified", "rejected", name="clinician_verification_status"
)
access_grant_status = _enum("active", "revoked", name="access_grant_status")
resource_values = ("scan_session", "report", "lesion", "analysis_run")
grant_resource_type = _enum(*resource_values, name="grant_resource_type")
share_link_status = _enum("active", "revoked", name="share_link_status")
share_resource_type = _enum(*resource_values, name="share_resource_type")
review_status = _enum(
    "pending", "in_review", "completed", "declined", name="clinician_review_status"
)
annotation_resource_type = _enum(*resource_values, name="annotation_resource_type")
annotation_kind = _enum(
    "note",
    "question",
    "follow_up",
    "measurement_context",
    name="review_annotation_kind",
)
access_actor_type = _enum(
    "patient", "clinician", "share_viewer", "admin", "system", name="access_actor_type"
)
access_event_type = _enum(
    "grant_created",
    "grant_revoked",
    "share_created",
    "share_revoked",
    "share_exchanged",
    "resource_viewed",
    "review_status_changed",
    "annotation_created",
    name="access_event_type",
)
generated_artifact_purpose = _enum(
    "reconstruction", "summary_video", name="generated_artifact_purpose"
)


def upgrade() -> None:
    op.add_column(
        "audit_events",
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "clinician_verifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", verification_status, nullable=False),
        sa.Column("profession", sa.String(length=80), nullable=False),
        sa.Column("license_jurisdiction", sa.String(length=80), nullable=False),
        sa.Column("license_number_sha256", sa.String(length=64), nullable=False),
        sa.Column("license_number_suffix", sa.String(length=4), nullable=False),
        sa.Column("organization", sa.String(length=160), nullable=True),
        sa.Column("applicant_evidence_ref", sa.String(length=160), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("reviewer_evidence", sa.JSON(), nullable=True),
        sa.Column("decision_reason", sa.String(length=500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clinician_verification_status_submitted",
        "clinician_verifications",
        ["status", "submitted_at"],
    )
    op.create_index(
        "ix_clinician_verification_user_submitted",
        "clinician_verifications",
        ["user_id", "submitted_at"],
    )
    op.create_index(
        op.f("ix_clinician_verifications_reviewer_user_id"),
        "clinician_verifications",
        ["reviewer_user_id"],
    )
    op.create_index(
        op.f("ix_clinician_verifications_user_id"),
        "clinician_verifications",
        ["user_id"],
    )

    op.create_table(
        "clinician_access_grants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_user_id", sa.String(length=36), nullable=False),
        sa.Column("clinician_user_id", sa.String(length=36), nullable=False),
        sa.Column("status", access_grant_status, nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "patient_user_id <> clinician_user_id",
            name="ck_access_grant_distinct_users",
        ),
        sa.ForeignKeyConstraint(
            ["clinician_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["patient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_access_grant_clinician_created",
        "clinician_access_grants",
        ["clinician_user_id", "created_at"],
    )
    op.create_index(
        "ix_access_grant_patient_created",
        "clinician_access_grants",
        ["patient_user_id", "created_at"],
    )
    op.create_index(
        op.f("ix_clinician_access_grants_clinician_user_id"),
        "clinician_access_grants",
        ["clinician_user_id"],
    )
    op.create_index(
        op.f("ix_clinician_access_grants_patient_user_id"),
        "clinician_access_grants",
        ["patient_user_id"],
    )

    op.create_table(
        "access_grant_resources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("grant_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", grant_resource_type, nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["clinician_access_grants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "grant_id", "resource_type", "resource_id", name="uq_access_grant_resource"
        ),
    )
    op.create_index(
        op.f("ix_access_grant_resources_grant_id"),
        "access_grant_resources",
        ["grant_id"],
    )

    op.create_table(
        "share_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_user_id", sa.String(length=36), nullable=False),
        sa.Column("secret_sha256", sa.String(length=64), nullable=False),
        sa.Column("create_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", share_link_status, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_exchanges", sa.Integer(), nullable=False),
        sa.Column("exchange_count", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "exchange_count >= 0", name="ck_share_exchange_count_nonnegative"
        ),
        sa.CheckConstraint(
            "max_exchanges >= 1", name="ck_share_max_exchanges_positive"
        ),
        sa.ForeignKeyConstraint(["patient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret_sha256"),
        sa.UniqueConstraint(
            "patient_user_id", "create_idempotency_key", name="uq_share_create_key"
        ),
    )
    op.create_index(
        "ix_share_patient_created", "share_links", ["patient_user_id", "created_at"]
    )
    op.create_index(
        op.f("ix_share_links_patient_user_id"), "share_links", ["patient_user_id"]
    )

    op.create_table(
        "share_link_resources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("share_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", share_resource_type, nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["share_id"], ["share_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "share_id", "resource_type", "resource_id", name="uq_share_link_resource"
        ),
    )
    op.create_index(
        op.f("ix_share_link_resources_share_id"),
        "share_link_resources",
        ["share_id"],
    )

    op.create_table(
        "share_exchange_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("share_id", sa.String(length=36), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=False),
        sa.Column("exchange_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("max_uses >= 1", name="ck_share_token_max_uses_positive"),
        sa.CheckConstraint(
            "use_count >= 0", name="ck_share_token_use_count_nonnegative"
        ),
        sa.ForeignKeyConstraint(["share_id"], ["share_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_sha256"),
        sa.UniqueConstraint(
            "share_id", "exchange_idempotency_key", name="uq_share_exchange_key"
        ),
    )
    op.create_index(
        op.f("ix_share_exchange_tokens_share_id"),
        "share_exchange_tokens",
        ["share_id"],
    )

    op.create_table(
        "clinician_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("grant_id", sa.String(length=36), nullable=False),
        sa.Column("patient_user_id", sa.String(length=36), nullable=False),
        sa.Column("clinician_user_id", sa.String(length=36), nullable=False),
        sa.Column("status", review_status, nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinician_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["clinician_access_grants.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["patient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grant_id", name="uq_clinician_review_grant"),
    )
    op.create_index(
        "ix_review_clinician_status_created",
        "clinician_reviews",
        ["clinician_user_id", "status", "created_at"],
    )
    op.create_index(
        "ix_review_patient_created",
        "clinician_reviews",
        ["patient_user_id", "created_at"],
    )
    op.create_index(
        op.f("ix_clinician_reviews_clinician_user_id"),
        "clinician_reviews",
        ["clinician_user_id"],
    )
    op.create_index(
        op.f("ix_clinician_reviews_patient_user_id"),
        "clinician_reviews",
        ["patient_user_id"],
    )

    op.create_table(
        "review_annotations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("clinician_user_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", annotation_resource_type, nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("kind", annotation_kind, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinician_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["clinician_reviews.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_annotation_review_created",
        "review_annotations",
        ["review_id", "created_at"],
    )
    op.create_index(
        op.f("ix_review_annotations_clinician_user_id"),
        "review_annotations",
        ["clinician_user_id"],
    )
    op.create_index(
        op.f("ix_review_annotations_review_id"),
        "review_annotations",
        ["review_id"],
    )

    op.create_table(
        "access_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_user_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("actor_type", access_actor_type, nullable=False),
        sa.Column("event_type", access_event_type, nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("grant_id", sa.String(length=36), nullable=True),
        sa.Column("share_id", sa.String(length=36), nullable=True),
        sa.Column("review_id", sa.String(length=36), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["clinician_access_grants.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["patient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["review_id"], ["clinician_reviews.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["share_id"], ["share_links.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_access_event_patient_created",
        "access_events",
        ["patient_user_id", "created_at"],
    )
    op.create_index(
        op.f("ix_access_events_actor_user_id"),
        "access_events",
        ["actor_user_id"],
    )
    op.create_index(op.f("ix_access_events_grant_id"), "access_events", ["grant_id"])
    op.create_index(
        op.f("ix_access_events_patient_user_id"),
        "access_events",
        ["patient_user_id"],
    )
    op.create_index(op.f("ix_access_events_review_id"), "access_events", ["review_id"])
    op.create_index(op.f("ix_access_events_share_id"), "access_events", ["share_id"])

    op.create_table(
        "generated_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", generated_artifact_purpose, nullable=False),
        sa.Column("filename", sa.String(length=120), nullable=False),
        sa.Column("media_type", sa.String(length=80), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id", "purpose", name="uq_generated_artifact_job_purpose"
        ),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index(
        "ix_generated_artifact_user_created",
        "generated_artifacts",
        ["user_id", "created_at"],
    )
    op.create_index(
        op.f("ix_generated_artifacts_job_id"), "generated_artifacts", ["job_id"]
    )
    op.create_index(
        op.f("ix_generated_artifacts_user_id"), "generated_artifacts", ["user_id"]
    )

    op.create_table(
        "service_request_nonces",
        sa.Column("nonce_sha256", sa.String(length=64), nullable=False),
        sa.Column("service_id", sa.String(length=80), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("nonce_sha256"),
    )
    op.create_index(
        "ix_service_nonce_expires", "service_request_nonces", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_service_nonce_expires", table_name="service_request_nonces")
    op.drop_table("service_request_nonces")
    op.drop_index(
        op.f("ix_generated_artifacts_user_id"), table_name="generated_artifacts"
    )
    op.drop_index(
        op.f("ix_generated_artifacts_job_id"), table_name="generated_artifacts"
    )
    op.drop_index(
        "ix_generated_artifact_user_created", table_name="generated_artifacts"
    )
    op.drop_table("generated_artifacts")
    op.drop_index(op.f("ix_access_events_share_id"), table_name="access_events")
    op.drop_index(op.f("ix_access_events_review_id"), table_name="access_events")
    op.drop_index(op.f("ix_access_events_patient_user_id"), table_name="access_events")
    op.drop_index(op.f("ix_access_events_grant_id"), table_name="access_events")
    op.drop_index(op.f("ix_access_events_actor_user_id"), table_name="access_events")
    op.drop_index("ix_access_event_patient_created", table_name="access_events")
    op.drop_table("access_events")
    op.drop_index(
        op.f("ix_review_annotations_review_id"), table_name="review_annotations"
    )
    op.drop_index(
        op.f("ix_review_annotations_clinician_user_id"),
        table_name="review_annotations",
    )
    op.drop_index("ix_annotation_review_created", table_name="review_annotations")
    op.drop_table("review_annotations")
    op.drop_index(
        op.f("ix_clinician_reviews_patient_user_id"), table_name="clinician_reviews"
    )
    op.drop_index(
        op.f("ix_clinician_reviews_clinician_user_id"), table_name="clinician_reviews"
    )
    op.drop_index("ix_review_patient_created", table_name="clinician_reviews")
    op.drop_index("ix_review_clinician_status_created", table_name="clinician_reviews")
    op.drop_table("clinician_reviews")
    op.drop_index(
        op.f("ix_share_exchange_tokens_share_id"), table_name="share_exchange_tokens"
    )
    op.drop_table("share_exchange_tokens")
    op.drop_index(
        op.f("ix_share_link_resources_share_id"), table_name="share_link_resources"
    )
    op.drop_table("share_link_resources")
    op.drop_index(op.f("ix_share_links_patient_user_id"), table_name="share_links")
    op.drop_index("ix_share_patient_created", table_name="share_links")
    op.drop_table("share_links")
    op.drop_index(
        op.f("ix_access_grant_resources_grant_id"), table_name="access_grant_resources"
    )
    op.drop_table("access_grant_resources")
    op.drop_index(
        op.f("ix_clinician_access_grants_patient_user_id"),
        table_name="clinician_access_grants",
    )
    op.drop_index(
        op.f("ix_clinician_access_grants_clinician_user_id"),
        table_name="clinician_access_grants",
    )
    op.drop_index(
        "ix_access_grant_patient_created", table_name="clinician_access_grants"
    )
    op.drop_index(
        "ix_access_grant_clinician_created", table_name="clinician_access_grants"
    )
    op.drop_table("clinician_access_grants")
    op.drop_index(
        op.f("ix_clinician_verifications_user_id"),
        table_name="clinician_verifications",
    )
    op.drop_index(
        op.f("ix_clinician_verifications_reviewer_user_id"),
        table_name="clinician_verifications",
    )
    op.drop_index(
        "ix_clinician_verification_user_submitted",
        table_name="clinician_verifications",
    )
    op.drop_index(
        "ix_clinician_verification_status_submitted",
        table_name="clinician_verifications",
    )
    op.drop_table("clinician_verifications")
    op.drop_column("audit_events", "retention_expires_at")
