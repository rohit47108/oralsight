"""Add product capture, analysis, tracking, report, job, and sync state.

Revision ID: 20260804_0002
Revises: 20260804_0001
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260804_0002"
down_revision = "20260804_0001"
branch_labels = None
depends_on = None


def _enum(*values: str, name: str, length: int = 32) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=length)


mouth_region = _enum(
    "dorsal_tongue",
    "ventral_tongue",
    "left_buccal_mucosa",
    "right_buccal_mucosa",
    "upper_lip",
    "lower_lip",
    "upper_dental_arch",
    "lower_dental_arch",
    name="mouth_region",
    length=64,
)
capture_protocol = _enum(
    "standard_eight_region",
    "detailed_multi_angle",
    "guided_video_sweep",
    name="capture_protocol",
)
capture_angle = _enum(
    "primary",
    "straight",
    "left_oblique",
    "right_oblique",
    "superior",
    "inferior",
    name="capture_angle_v2",
)
input_origin = _enum("live_capture", "bundled_demo", name="input_origin")
analysis_status = _enum(
    "complete",
    "abstained",
    "unsupported",
    "failed",
    name="analysis_status_v2",
)
analysis_input_origin = _enum(
    "live_capture", "bundled_demo", name="analysis_input_origin"
)
analysis_origin = _enum(
    "live_model",
    "cached_model_result",
    "manual_fixture",
    "unavailable",
    name="analysis_origin_v2",
)
calibration_status = _enum(
    "not_attempted", "valid", "invalid", name="calibration_status"
)
observation_region = _enum(
    *[value for value in mouth_region.enums], name="observation_region", length=64
)
lesion_region = _enum(
    *[value for value in mouth_region.enums], name="lesion_region", length=64
)
lesion_status = _enum("tracking", "archived", name="lesion_status")
match_decision_value = _enum(
    "confirmed", "rejected", "deferred", name="match_decision_value"
)
report_format = _enum(
    "pdf",
    "html",
    "fhir_r4_bundle",
    "summary_video",
    "transcript",
    name="report_format",
)
sync_entity_values = (
    "scan_session",
    "capture_set",
    "capture_view",
    "analysis_run",
    "observation",
    "lesion",
    "match_decision",
    "report",
)
sync_entity_type = _enum(*sync_entity_values, name="sync_entity_type")
tombstone_entity_type = _enum(*sync_entity_values, name="tombstone_entity_type")
sync_change_entity_type = _enum(*sync_entity_values, name="sync_change_entity_type")
sync_operation_kind = _enum("upsert", "delete", name="sync_operation_kind")
sync_apply_status = _enum(
    "applied",
    "stale_ignored",
    "tombstone_wins",
    "duplicate",
    name="sync_apply_status",
)


def upgrade() -> None:
    with op.batch_alter_table("capture_assets") as batch:
        batch.add_column(sa.Column("width_px", sa.Integer()))
        batch.add_column(sa.Column("height_px", sa.Integer()))
        batch.add_column(sa.Column("duration_ms", sa.Integer()))
        batch.add_column(
            sa.Column(
                "input_origin",
                input_origin,
                nullable=False,
                server_default="live_capture",
            )
        )
        batch.add_column(
            sa.Column(
                "encrypted", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )
        batch.add_column(sa.Column("retention_expires_at", sa.DateTime(timezone=True)))

    with op.batch_alter_table("jobs") as batch:
        batch.add_column(
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3")
        )
        batch.add_column(
            sa.Column("input_refs", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.add_column(
            sa.Column("output_refs", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.add_column(sa.Column("error_message", sa.String(1000)))
        batch.add_column(sa.Column("expires_at", sa.DateTime(timezone=True)))

    op.create_table(
        "capture_sets",
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
        sa.Column("region", mouth_region, nullable=False),
        sa.Column("protocol", capture_protocol, nullable=False),
        sa.Column("primary_view_id", sa.String(36)),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scan_session_id", "region", name="uq_capture_set_region"),
    )
    op.create_index("ix_capture_sets_user_id", "capture_sets", ["user_id"])
    op.create_index(
        "ix_capture_sets_scan_session_id", "capture_sets", ["scan_session_id"]
    )
    op.create_index(
        "ix_capture_sets_primary_view_id", "capture_sets", ["primary_view_id"]
    )

    op.create_table(
        "capture_views",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capture_set_id",
            sa.String(36),
            sa.ForeignKey("capture_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            sa.String(36),
            sa.ForeignKey("capture_assets.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "region",
            _enum(*mouth_region.enums, name="capture_view_region", length=64),
            nullable=False,
        ),
        sa.Column("anatomical_site", sa.String(64)),
        sa.Column("angle", capture_angle, nullable=False),
        sa.Column(
            "source_video_asset_id",
            sa.String(36),
            sa.ForeignKey("capture_assets.id", ondelete="SET NULL"),
        ),
        sa.Column("quality_accepted", sa.Boolean(), nullable=False),
        sa.Column("quality_reasons", sa.JSON(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "capture_set_id", "ordinal", name="uq_capture_view_ordinal"
        ),
    )
    op.create_index("ix_capture_views_user_id", "capture_views", ["user_id"])
    op.create_index(
        "ix_capture_views_capture_set_id", "capture_views", ["capture_set_id"]
    )
    op.create_index(
        "ix_capture_views_source_video_asset_id",
        "capture_views",
        ["source_video_asset_id"],
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capture_set_id",
            sa.String(36),
            sa.ForeignKey("capture_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requested_heads", sa.JSON(), nullable=False),
        sa.Column("status", analysis_status, nullable=False),
        sa.Column("input_origin", analysis_input_origin, nullable=False),
        sa.Column("analysis_origin", analysis_origin, nullable=False),
        sa.Column("source_asset_sha256", sa.JSON(), nullable=False),
        sa.Column("model_versions", sa.JSON(), nullable=False),
        sa.Column("artifact_hashes", sa.JSON(), nullable=False),
        sa.Column("abstention_reasons", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("persisted", sa.Boolean(), nullable=False),
        sa.Column("signed_envelope_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_analysis_runs_user_id", "analysis_runs", ["user_id"])
    op.create_index(
        "ix_analysis_runs_capture_set_id", "analysis_runs", ["capture_set_id"]
    )
    op.create_index(
        "ix_analysis_user_started", "analysis_runs", ["user_id", "started_at"]
    )

    op.create_table(
        "candidate_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_run_id",
            sa.String(36),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capture_view_id",
            sa.String(36),
            sa.ForeignKey("capture_views.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("region", observation_region, nullable=False),
        sa.Column("anatomical_site", sa.String(64)),
        sa.Column("candidate_mask", sa.JSON(), nullable=False),
        sa.Column("descriptors", sa.JSON(), nullable=False),
        sa.Column("uncertainty", sa.JSON(), nullable=False),
        sa.Column("appearance_output", sa.JSON()),
        sa.Column("disease_research_output", sa.JSON()),
        sa.Column("calibration_status", calibration_status, nullable=False),
        sa.Column("calibration_evidence", sa.JSON()),
        sa.Column("calibration_evidence_sha256", sa.String(64)),
        sa.Column("estimated_width_mm", sa.Float()),
        sa.Column("estimated_height_mm", sa.Float()),
        sa.Column("estimated_area_mm2", sa.Float()),
        sa.Column("named_mesh", sa.String(128)),
        sa.Column("uv_u", sa.Float()),
        sa.Column("uv_v", sa.Float()),
        sa.Column("asset_version", sa.String(128)),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "(calibration_status = 'valid' AND calibration_evidence_sha256 IS NOT NULL) "
            "OR (calibration_status != 'valid' AND estimated_width_mm IS NULL "
            "AND estimated_height_mm IS NULL AND estimated_area_mm2 IS NULL)",
            name="ck_observation_calibrated_measurements",
        ),
        sa.CheckConstraint(
            "(named_mesh IS NULL AND uv_u IS NULL AND uv_v IS NULL AND asset_version IS NULL) "
            "OR (named_mesh IS NOT NULL AND uv_u IS NOT NULL AND uv_v IS NOT NULL "
            "AND asset_version IS NOT NULL)",
            name="ck_observation_mapping_complete",
        ),
    )
    op.create_index(
        "ix_candidate_observations_user_id", "candidate_observations", ["user_id"]
    )
    op.create_index(
        "ix_candidate_observations_analysis_run_id",
        "candidate_observations",
        ["analysis_run_id"],
    )
    op.create_index(
        "ix_candidate_observations_capture_view_id",
        "candidate_observations",
        ["capture_view_id"],
    )

    op.create_table(
        "lesion_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("region", lesion_region, nullable=False),
        sa.Column("anatomical_site", sa.String(64)),
        sa.Column("label", sa.String(128)),
        sa.Column("status", lesion_status, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lesion_records_user_id", "lesion_records", ["user_id"])

    op.create_table(
        "match_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "current_observation_id",
            sa.String(36),
            sa.ForeignKey("candidate_observations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_prior_observation_id",
            sa.String(36),
            sa.ForeignKey("candidate_observations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_lesion_id",
            sa.String(36),
            sa.ForeignKey("lesion_records.id", ondelete="SET NULL"),
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("model_versions", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "user_id",
            "current_observation_id",
            "candidate_prior_observation_id",
            name="uq_match_candidate_pair",
        ),
    )
    op.create_index("ix_match_proposals_user_id", "match_proposals", ["user_id"])
    op.create_index(
        "ix_match_proposals_current_observation_id",
        "match_proposals",
        ["current_observation_id"],
    )
    op.create_index(
        "ix_match_proposals_candidate_prior_observation_id",
        "match_proposals",
        ["candidate_prior_observation_id"],
    )
    op.create_index(
        "ix_match_proposals_candidate_lesion_id",
        "match_proposals",
        ["candidate_lesion_id"],
    )

    op.create_table(
        "match_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("match_proposals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", match_decision_value, nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("rationale", sa.String(1000)),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "lesion_id",
            sa.String(36),
            sa.ForeignKey("lesion_records.id", ondelete="SET NULL"),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "proposal_id", "sequence", name="uq_match_decision_sequence"
        ),
    )
    op.create_index("ix_match_decisions_user_id", "match_decisions", ["user_id"])
    op.create_index(
        "ix_match_decisions_proposal_id", "match_decisions", ["proposal_id"]
    )
    op.create_index("ix_match_decisions_lesion_id", "match_decisions", ["lesion_id"])

    op.create_table(
        "lesion_observation_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lesion_id",
            sa.String(36),
            sa.ForeignKey("lesion_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "observation_id",
            sa.String(36),
            sa.ForeignKey("candidate_observations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "decision_id",
            sa.String(36),
            sa.ForeignKey("match_decisions.id", ondelete="SET NULL"),
            unique=True,
        ),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_lesion_observation_links_user_id",
        "lesion_observation_links",
        ["user_id"],
    )
    op.create_index(
        "ix_lesion_observation_links_lesion_id",
        "lesion_observation_links",
        ["lesion_id"],
    )

    op.create_table(
        "report_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scan_session_ids", sa.JSON(), nullable=False),
        sa.Column("report_format", report_format, nullable=False),
        sa.Column("asset_id", sa.String(128), nullable=False, unique=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("locale", sa.String(35), nullable=False),
        sa.Column("accessible", sa.Boolean(), nullable=False),
        sa.Column("input_origins", sa.JSON(), nullable=False),
        sa.Column("analysis_origins", sa.JSON(), nullable=False),
        sa.Column("model_versions", sa.JSON(), nullable=False),
        sa.Column("signed_envelope_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_report_artifacts_user_id", "report_artifacts", ["user_id"])

    op.create_table(
        "sync_entity_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sync_entity_type, nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("last_server_sequence", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "entity_type", "entity_id", name="uq_sync_entity"
        ),
    )
    op.create_index("ix_sync_entity_states_user_id", "sync_entity_states", ["user_id"])

    op.create_table(
        "entity_tombstones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", tombstone_entity_type, nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("deleted_version", sa.Integer(), nullable=False),
        sa.Column("server_sequence", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "entity_type", "entity_id", name="uq_tombstone_entity"
        ),
    )
    op.create_index("ix_entity_tombstones_user_id", "entity_tombstones", ["user_id"])

    op.create_table(
        "sync_changes",
        sa.Column(
            "server_sequence", sa.Integer(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation_id", sa.String(128), nullable=False),
        sa.Column("client_idempotency_key", sa.String(256), nullable=False),
        sa.Column(
            "device_id",
            sa.String(36),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sync_change_entity_type, nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("entity_version", sa.Integer(), nullable=False),
        sa.Column("client_sequence", sa.Integer(), nullable=False),
        sa.Column("operation", sync_operation_kind, nullable=False),
        sa.Column("encrypted_payload", sa.Text()),
        sa.Column("tombstone", sa.Boolean(), nullable=False),
        sa.Column("apply_status", sync_apply_status, nullable=False),
        sa.Column("applied", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "operation_id", name="uq_sync_operation"),
        sa.UniqueConstraint(
            "user_id", "client_idempotency_key", name="uq_sync_client_key"
        ),
    )
    op.create_index("ix_sync_changes_user_id", "sync_changes", ["user_id"])
    op.create_index("ix_sync_changes_device_id", "sync_changes", ["device_id"])
    op.create_index("ix_sync_pull", "sync_changes", ["user_id", "server_sequence"])

    op.create_table(
        "sync_cursors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("high_watermark", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sync_cursors_user_id", "sync_cursors", ["user_id"])


def downgrade() -> None:
    op.drop_table("sync_cursors")
    op.drop_table("sync_changes")
    op.drop_table("entity_tombstones")
    op.drop_table("sync_entity_states")
    op.drop_table("report_artifacts")
    op.drop_table("lesion_observation_links")
    op.drop_table("match_decisions")
    op.drop_table("match_proposals")
    op.drop_table("lesion_records")
    op.drop_table("candidate_observations")
    op.drop_table("analysis_runs")
    op.drop_table("capture_views")
    op.drop_table("capture_sets")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("expires_at")
        batch.drop_column("error_message")
        batch.drop_column("output_refs")
        batch.drop_column("input_refs")
        batch.drop_column("max_attempts")
    with op.batch_alter_table("capture_assets") as batch:
        batch.drop_column("retention_expires_at")
        batch.drop_column("encrypted")
        batch.drop_column("input_origin")
        batch.drop_column("duration_ms")
        batch.drop_column("height_px")
        batch.drop_column("width_px")
