"""Initial stateful product tables.

The metadata in this module is the source imported by Alembic. Identifiers are
application-generated UUID strings so the same models work in PostgreSQL and tests.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserRole(StrEnum):
    PATIENT = "patient"
    SHARE_VIEWER = "share_viewer"
    CLINICIAN_PENDING = "clinician_pending"
    CLINICIAN = "clinician"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DELETION_PENDING = "deletion_pending"
    SUSPENDED = "suspended"


class ScanStatus(StrEnum):
    DRAFT = "draft"
    CAPTURING = "capturing"
    COMPLETE = "complete"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class CaptureStatus(StrEnum):
    PENDING = "pending"
    AVAILABLE = "available"
    DELETED = "deleted"


class MouthRegion(StrEnum):
    DORSAL_TONGUE = "dorsal_tongue"
    VENTRAL_TONGUE = "ventral_tongue"
    LEFT_BUCCAL_MUCOSA = "left_buccal_mucosa"
    RIGHT_BUCCAL_MUCOSA = "right_buccal_mucosa"
    UPPER_LIP = "upper_lip"
    LOWER_LIP = "lower_lip"
    UPPER_DENTAL_ARCH = "upper_dental_arch"
    LOWER_DENTAL_ARCH = "lower_dental_arch"


class CaptureProtocol(StrEnum):
    STANDARD = "standard_eight_region"
    DETAILED = "detailed_multi_angle"
    VIDEO_SWEEP = "guided_video_sweep"


class CaptureAngle(StrEnum):
    PRIMARY = "primary"
    STRAIGHT = "straight"
    LEFT_OBLIQUE = "left_oblique"
    RIGHT_OBLIQUE = "right_oblique"
    SUPERIOR = "superior"
    INFERIOR = "inferior"


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    VIDEO_FRAME = "video_frame"


class InputOrigin(StrEnum):
    LIVE_CAPTURE = "live_capture"
    BUNDLED_DEMO = "bundled_demo"


class AnalysisOrigin(StrEnum):
    LIVE_MODEL = "live_model"
    CACHED_MODEL_RESULT = "cached_model_result"
    MANUAL_FIXTURE = "manual_fixture"
    UNAVAILABLE = "unavailable"


class AnalysisStatus(StrEnum):
    COMPLETE = "complete"
    ABSTAINED = "abstained"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class CalibrationStatus(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    VALID = "valid"
    INVALID = "invalid"


class MatchDecisionValue(StrEnum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class MatchProposalOrigin(StrEnum):
    AUTOMATIC_MODEL = "automatic_model"
    USER_SELECTED = "user_selected"


class LesionStatus(StrEnum):
    TRACKING = "tracking"
    ARCHIVED = "archived"


class ReportFormat(StrEnum):
    PDF = "pdf"
    HTML = "html"
    FHIR_R4_BUNDLE = "fhir_r4_bundle"
    SUMMARY_VIDEO = "summary_video"
    TRANSCRIPT = "transcript"


class SyncEntityType(StrEnum):
    SCAN_SESSION = "scan_session"
    CAPTURE_SET = "capture_set"
    CAPTURE_VIEW = "capture_view"
    ANALYSIS_RUN = "analysis_run"
    OBSERVATION = "observation"
    LESION = "lesion"
    MATCH_DECISION = "match_decision"
    REPORT = "report"


class SyncOperationKind(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


class SyncApplyStatus(StrEnum):
    APPLIED = "applied"
    STALE_IGNORED = "stale_ignored"
    TOMBSTONE_WINS = "tombstone_wins"
    DUPLICATE = "duplicate"


class ClinicianVerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ShareResourceType(StrEnum):
    SCAN_SESSION = "scan_session"
    REPORT = "report"
    LESION = "lesion"
    ANALYSIS_RUN = "analysis_run"


class AccessGrantStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class ShareLinkStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class ClinicianReviewStatus(StrEnum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    DECLINED = "declined"


class ReviewAnnotationKind(StrEnum):
    NOTE = "note"
    QUESTION = "question"
    FOLLOW_UP = "follow_up"
    MEASUREMENT_CONTEXT = "measurement_context"
    OUTLINE_ADJUSTMENT = "outline_adjustment"
    LOCATION_CORRECTION = "location_correction"
    INSUFFICIENT_SCAN = "insufficient_scan"
    DATE_COMPARISON = "date_comparison"


class AccessActorType(StrEnum):
    PATIENT = "patient"
    CLINICIAN = "clinician"
    SHARE_VIEWER = "share_viewer"
    ADMIN = "admin"
    SYSTEM = "system"


class AccessEventType(StrEnum):
    GRANT_CREATED = "grant_created"
    GRANT_REVOKED = "grant_revoked"
    SHARE_CREATED = "share_created"
    SHARE_REVOKED = "share_revoked"
    SHARE_EXCHANGED = "share_exchanged"
    RESOURCE_VIEWED = "resource_viewed"
    REVIEW_STATUS_CHANGED = "review_status_changed"
    ANNOTATION_CREATED = "annotation_created"


class GeneratedArtifactPurpose(StrEnum):
    RECONSTRUCTION = "reconstruction"
    SUMMARY_VIDEO = "summary_video"


class JobType(StrEnum):
    ANALYSIS = "analysis"
    COMPARISON = "comparison"
    RECONSTRUCTION = "reconstruction"
    REPORT = "report"
    SUMMARY_VIDEO = "summary_video"
    DATA_EXPORT = "data_export"
    ACCOUNT_DELETION = "account_deletion"
    DELETE_ALL = "delete_all"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class DeletionStatus(StrEnum):
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


def enum_column(enum_class, *, name: str, length: int = 32) -> Enum:
    """Store public enum values, not Python member names, on every database."""

    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        length=length,
        values_callable=lambda members: [member.value for member in members],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AdminBootstrapSeal(Base):
    """Permanent marker that first-administrator bootstrap has been consumed."""

    __tablename__ = "admin_bootstrap_seals"

    seal_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    sealed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    oidc_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, name="user_role"),
        default=UserRole.PATIENT,
        nullable=False,
    )
    status: Mapped[UserStatus] = mapped_column(
        enum_column(UserStatus, name="user_status"),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    analytics_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    analytics_policy_version: Mapped[str | None] = mapped_column(String(64))
    analytics_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    devices: Mapped[list[Device]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    consents: Mapped[list[ConsentRecord]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    scan_sessions: Mapped[list[ScanSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class Device(TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("user_id", "installation_id", name="uq_device_installation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    installation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    public_key: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="devices")


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    document_id: Mapped[str] = mapped_column(String(120), nullable=False)
    document_version: Mapped[str] = mapped_column(String(64), nullable=False)
    document_sha256: Mapped[str | None] = mapped_column(String(64))
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="consents")


class ScanSession(TimestampMixin, Base):
    __tablename__ = "scan_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    consent_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("consent_records.id", ondelete="RESTRICT"), index=True
    )
    protocol: Mapped[str] = mapped_column(
        String(32), default="standard", nullable=False
    )
    status: Mapped[ScanStatus] = mapped_column(
        enum_column(ScanStatus, name="scan_status"),
        default=ScanStatus.DRAFT,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="scan_sessions")
    capture_assets: Mapped[list[CaptureAsset]] = relationship(
        back_populates="scan_session", cascade="all, delete-orphan"
    )


class CaptureAsset(TimestampMixin, Base):
    __tablename__ = "capture_assets"
    __table_args__ = (
        UniqueConstraint(
            "scan_session_id",
            "region",
            "capture_angle",
            "sequence_number",
            name="uq_capture_view_sequence",
        ),
        Index("ix_capture_assets_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scan_session_id: Mapped[str] = mapped_column(
        ForeignKey("scan_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    capture_angle: Mapped[str] = mapped_column(
        String(32), default="primary", nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    media_kind: Mapped[str] = mapped_column(String(32), default="image", nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    encryption_key_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[CaptureStatus] = mapped_column(
        enum_column(CaptureStatus, name="capture_status"),
        default=CaptureStatus.PENDING,
        nullable=False,
    )
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    input_origin: Mapped[InputOrigin] = mapped_column(
        enum_column(InputOrigin, name="input_origin"),
        default=InputOrigin.LIVE_CAPTURE,
        nullable=False,
    )
    encrypted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    upload_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    upload_capability_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    scan_session: Mapped[ScanSession] = relationship(back_populates="capture_assets")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scan_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("scan_sessions.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[JobType] = mapped_column(
        enum_column(JobType, name="job_type"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        enum_column(JobStatus, name="job_status"),
        default=JobStatus.QUEUED,
        nullable=False,
    )
    resource_id: Mapped[str | None] = mapped_column(String(36), index=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    input_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    output_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    queue_envelope: Mapped[str | None] = mapped_column(Text)
    queue_message_id: Mapped[str | None] = mapped_column(String(128))
    queue_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    result_outcome: Mapped[str | None] = mapped_column(String(32))
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason_code: Mapped[str | None] = mapped_column(String(100))
    retention_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class CaptureSet(TimestampMixin, Base):
    __tablename__ = "capture_sets"
    __table_args__ = (
        UniqueConstraint("scan_session_id", "region", name="uq_capture_set_region"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scan_session_id: Mapped[str] = mapped_column(
        ForeignKey("scan_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    region: Mapped[MouthRegion] = mapped_column(
        enum_column(MouthRegion, name="mouth_region", length=64), nullable=False
    )
    protocol: Mapped[CaptureProtocol] = mapped_column(
        enum_column(CaptureProtocol, name="capture_protocol", length=32),
        nullable=False,
    )
    primary_view_id: Mapped[str | None] = mapped_column(String(36), index=True)
    complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaptureView(Base):
    __tablename__ = "capture_views"
    __table_args__ = (
        UniqueConstraint("capture_set_id", "ordinal", name="uq_capture_view_ordinal"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    capture_set_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("capture_assets.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    region: Mapped[MouthRegion] = mapped_column(
        enum_column(MouthRegion, name="capture_view_region", length=64), nullable=False
    )
    anatomical_site: Mapped[str | None] = mapped_column(String(64))
    angle: Mapped[CaptureAngle] = mapped_column(
        enum_column(CaptureAngle, name="capture_angle_v2", length=32), nullable=False
    )
    source_video_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("capture_assets.id", ondelete="SET NULL"), index=True
    )
    quality_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality_reasons: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_analysis_user_started", "user_id", "started_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    capture_set_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requested_heads: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(
        enum_column(AnalysisStatus, name="analysis_status_v2", length=32),
        nullable=False,
    )
    input_origin: Mapped[InputOrigin] = mapped_column(
        enum_column(InputOrigin, name="analysis_input_origin", length=32),
        nullable=False,
    )
    analysis_origin: Mapped[AnalysisOrigin] = mapped_column(
        enum_column(AnalysisOrigin, name="analysis_origin_v2", length=32),
        nullable=False,
    )
    source_asset_sha256: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    model_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    artifact_hashes: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    abstention_reasons: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    persisted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    signed_envelope_id: Mapped[str] = mapped_column(String(128), nullable=False)
    worker_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidateObservation(Base):
    __tablename__ = "candidate_observations"
    __table_args__ = (
        CheckConstraint(
            "(calibration_status = 'valid' AND calibration_evidence_sha256 IS NOT NULL) "
            "OR (calibration_status != 'valid' AND estimated_width_mm IS NULL "
            "AND estimated_height_mm IS NULL AND estimated_area_mm2 IS NULL)",
            name="ck_observation_calibrated_measurements",
        ),
        CheckConstraint(
            "(named_mesh IS NULL AND uv_u IS NULL AND uv_v IS NULL AND asset_version IS NULL) "
            "OR (named_mesh IS NOT NULL AND uv_u IS NOT NULL AND uv_v IS NOT NULL "
            "AND asset_version IS NOT NULL)",
            name="ck_observation_mapping_complete",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    capture_view_id: Mapped[str] = mapped_column(
        ForeignKey("capture_views.id", ondelete="CASCADE"), index=True, nullable=False
    )
    region: Mapped[MouthRegion] = mapped_column(
        enum_column(MouthRegion, name="observation_region", length=64), nullable=False
    )
    anatomical_site: Mapped[str | None] = mapped_column(String(64))
    candidate_mask: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    descriptors: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    uncertainty: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    appearance_output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    disease_research_output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    calibration_status: Mapped[CalibrationStatus] = mapped_column(
        enum_column(CalibrationStatus, name="calibration_status", length=32),
        default=CalibrationStatus.NOT_ATTEMPTED,
        nullable=False,
    )
    calibration_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    calibration_evidence_sha256: Mapped[str | None] = mapped_column(String(64))
    estimated_width_mm: Mapped[float | None] = mapped_column(Float)
    estimated_height_mm: Mapped[float | None] = mapped_column(Float)
    estimated_area_mm2: Mapped[float | None] = mapped_column(Float)
    named_mesh: Mapped[str | None] = mapped_column(String(128))
    uv_u: Mapped[float | None] = mapped_column(Float)
    uv_v: Mapped[float | None] = mapped_column(Float)
    asset_version: Mapped[str | None] = mapped_column(String(128))
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MatchProposal(Base):
    __tablename__ = "match_proposals"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "current_observation_id",
            "candidate_prior_observation_id",
            name="uq_match_candidate_pair",
        ),
        CheckConstraint(
            "(proposal_origin = 'automatic_model' AND score IS NOT NULL AND rank IS NOT NULL) "
            "OR (proposal_origin = 'user_selected' AND score IS NULL AND rank IS NULL)",
            name="ck_match_proposal_origin_evidence",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    current_observation_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_observations.id", ondelete="CASCADE"), index=True
    )
    candidate_prior_observation_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_observations.id", ondelete="CASCADE"), index=True
    )
    candidate_lesion_id: Mapped[str | None] = mapped_column(
        ForeignKey("lesion_records.id", ondelete="SET NULL"), index=True
    )
    proposal_origin: Mapped[MatchProposalOrigin] = mapped_column(
        enum_column(MatchProposalOrigin, name="match_proposal_origin", length=32),
        default=MatchProposalOrigin.AUTOMATIC_MODEL,
        nullable=False,
    )
    score: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    model_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MatchDecision(Base):
    __tablename__ = "match_decisions"
    __table_args__ = (
        UniqueConstraint("proposal_id", "sequence", name="uq_match_decision_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("match_proposals.id", ondelete="CASCADE"), index=True, nullable=False
    )
    decision: Mapped[MatchDecisionValue] = mapped_column(
        enum_column(MatchDecisionValue, name="match_decision_value", length=32),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    rationale: Mapped[str | None] = mapped_column(String(1000))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    lesion_id: Mapped[str | None] = mapped_column(
        ForeignKey("lesion_records.id", ondelete="SET NULL"), index=True
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class LesionRecord(TimestampMixin, Base):
    __tablename__ = "lesion_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    region: Mapped[MouthRegion] = mapped_column(
        enum_column(MouthRegion, name="lesion_region", length=64), nullable=False
    )
    anatomical_site: Mapped[str | None] = mapped_column(String(64))
    label: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[LesionStatus] = mapped_column(
        enum_column(LesionStatus, name="lesion_status", length=32),
        default=LesionStatus.TRACKING,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LesionObservationLink(Base):
    __tablename__ = "lesion_observation_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesion_id: Mapped[str] = mapped_column(
        ForeignKey("lesion_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_observations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("match_decisions.id", ondelete="SET NULL"), unique=True
    )
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ReportArtifact(Base):
    __tablename__ = "report_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scan_session_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    report_format: Mapped[ReportFormat] = mapped_column(
        enum_column(ReportFormat, name="report_format", length=32), nullable=False
    )
    asset_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(512), unique=True)
    media_type: Mapped[str] = mapped_column(
        String(80), default="application/pdf", nullable=False
    )
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    locale: Mapped[str] = mapped_column(String(35), nullable=False)
    accessible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    input_origins: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    analysis_origins: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    model_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    signed_envelope_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncEntityState(Base):
    __tablename__ = "sync_entity_states"
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_sync_entity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entity_type: Mapped[SyncEntityType] = mapped_column(
        enum_column(SyncEntityType, name="sync_entity_type", length=32),
        nullable=False,
    )
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    last_server_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class EntityTombstone(Base):
    __tablename__ = "entity_tombstones"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "entity_type", "entity_id", name="uq_tombstone_entity"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entity_type: Mapped[SyncEntityType] = mapped_column(
        enum_column(SyncEntityType, name="tombstone_entity_type", length=32),
        nullable=False,
    )
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    deleted_version: Mapped[int] = mapped_column(Integer, nullable=False)
    server_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SyncChange(Base):
    __tablename__ = "sync_changes"
    __table_args__ = (
        UniqueConstraint("user_id", "operation_id", name="uq_sync_operation"),
        UniqueConstraint(
            "user_id", "client_idempotency_key", name="uq_sync_client_key"
        ),
        Index("ix_sync_pull", "user_id", "server_sequence"),
    )

    server_sequence: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    operation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entity_type: Mapped[SyncEntityType] = mapped_column(
        enum_column(SyncEntityType, name="sync_change_entity_type", length=32),
        nullable=False,
    )
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    client_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[SyncOperationKind] = mapped_column(
        enum_column(SyncOperationKind, name="sync_operation_kind", length=32),
        nullable=False,
    )
    encrypted_payload: Mapped[str | None] = mapped_column(Text)
    tombstone: Mapped[bool] = mapped_column(Boolean, nullable=False)
    apply_status: Mapped[SyncApplyStatus] = mapped_column(
        enum_column(SyncApplyStatus, name="sync_apply_status", length=32),
        nullable=False,
    )
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class SyncCursor(Base):
    __tablename__ = "sync_cursors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    high_watermark: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ClinicianVerification(Base):
    __tablename__ = "clinician_verifications"
    __table_args__ = (
        Index("ix_clinician_verification_status_submitted", "status", "submitted_at"),
        Index("ix_clinician_verification_user_submitted", "user_id", "submitted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[ClinicianVerificationStatus] = mapped_column(
        enum_column(
            ClinicianVerificationStatus,
            name="clinician_verification_status",
        ),
        default=ClinicianVerificationStatus.PENDING,
        nullable=False,
    )
    profession: Mapped[str] = mapped_column(String(80), nullable=False)
    license_jurisdiction: Mapped[str] = mapped_column(String(80), nullable=False)
    license_number_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    license_number_suffix: Mapped[str] = mapped_column(String(4), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(160))
    applicant_evidence_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    reviewer_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewer_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    decision_reason: Mapped[str | None] = mapped_column(String(500))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    oidc_role_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ClinicianAccessGrant(TimestampMixin, Base):
    __tablename__ = "clinician_access_grants"
    __table_args__ = (
        CheckConstraint(
            "patient_user_id <> clinician_user_id",
            name="ck_access_grant_distinct_users",
        ),
        Index("ix_access_grant_patient_created", "patient_user_id", "created_at"),
        Index("ix_access_grant_clinician_created", "clinician_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    clinician_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[AccessGrantStatus] = mapped_column(
        enum_column(AccessGrantStatus, name="access_grant_status"),
        default=AccessGrantStatus.ACTIVE,
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(String(120))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AccessGrantResource(Base):
    __tablename__ = "access_grant_resources"
    __table_args__ = (
        UniqueConstraint(
            "grant_id", "resource_type", "resource_id", name="uq_access_grant_resource"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grant_id: Mapped[str] = mapped_column(
        ForeignKey("clinician_access_grants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    resource_type: Mapped[ShareResourceType] = mapped_column(
        enum_column(ShareResourceType, name="grant_resource_type"), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ShareLink(Base):
    __tablename__ = "share_links"
    __table_args__ = (
        UniqueConstraint(
            "patient_user_id", "create_idempotency_key", name="uq_share_create_key"
        ),
        CheckConstraint("max_exchanges >= 1", name="ck_share_max_exchanges_positive"),
        CheckConstraint(
            "exchange_count >= 0", name="ck_share_exchange_count_nonnegative"
        ),
        Index("ix_share_patient_created", "patient_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    secret_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    create_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ShareLinkStatus] = mapped_column(
        enum_column(ShareLinkStatus, name="share_link_status"),
        default=ShareLinkStatus.ACTIVE,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    max_exchanges: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    exchange_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ShareLinkResource(Base):
    __tablename__ = "share_link_resources"
    __table_args__ = (
        UniqueConstraint(
            "share_id", "resource_type", "resource_id", name="uq_share_link_resource"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    share_id: Mapped[str] = mapped_column(
        ForeignKey("share_links.id", ondelete="CASCADE"), index=True, nullable=False
    )
    resource_type: Mapped[ShareResourceType] = mapped_column(
        enum_column(ShareResourceType, name="share_resource_type"), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ShareExchangeToken(Base):
    __tablename__ = "share_exchange_tokens"
    __table_args__ = (
        UniqueConstraint(
            "share_id",
            "exchange_idempotency_key",
            name="uq_share_exchange_key",
        ),
        CheckConstraint("max_uses >= 1", name="ck_share_token_max_uses_positive"),
        CheckConstraint("use_count >= 0", name="ck_share_token_use_count_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    share_id: Mapped[str] = mapped_column(
        ForeignKey("share_links.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    exchange_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ClinicianReview(TimestampMixin, Base):
    __tablename__ = "clinician_reviews"
    __table_args__ = (
        UniqueConstraint("grant_id", name="uq_clinician_review_grant"),
        Index(
            "ix_review_clinician_status_created",
            "clinician_user_id",
            "status",
            "created_at",
        ),
        Index("ix_review_patient_created", "patient_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grant_id: Mapped[str] = mapped_column(
        ForeignKey("clinician_access_grants.id", ondelete="CASCADE"), nullable=False
    )
    patient_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    clinician_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[ClinicianReviewStatus] = mapped_column(
        enum_column(ClinicianReviewStatus, name="clinician_review_status"),
        default=ClinicianReviewStatus.PENDING,
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ReviewAnnotation(Base):
    __tablename__ = "review_annotations"
    __table_args__ = (Index("ix_annotation_review_created", "review_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(
        ForeignKey("clinician_reviews.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    clinician_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    resource_type: Mapped[ShareResourceType] = mapped_column(
        enum_column(ShareResourceType, name="annotation_resource_type"), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[ReviewAnnotationKind] = mapped_column(
        enum_column(ReviewAnnotationKind, name="review_annotation_kind"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AccessEvent(Base):
    __tablename__ = "access_events"
    __table_args__ = (
        Index("ix_access_event_patient_created", "patient_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_type: Mapped[AccessActorType] = mapped_column(
        enum_column(AccessActorType, name="access_actor_type"), nullable=False
    )
    event_type: Mapped[AccessEventType] = mapped_column(
        enum_column(AccessEventType, name="access_event_type"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    grant_id: Mapped[str | None] = mapped_column(
        ForeignKey("clinician_access_grants.id", ondelete="SET NULL"), index=True
    )
    share_id: Mapped[str | None] = mapped_column(
        ForeignKey("share_links.id", ondelete="SET NULL"), index=True
    )
    review_id: Mapped[str | None] = mapped_column(
        ForeignKey("clinician_reviews.id", ondelete="SET NULL"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"
    __table_args__ = (
        UniqueConstraint("job_id", "purpose", name="uq_generated_artifact_job_purpose"),
        Index("ix_generated_artifact_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    purpose: Mapped[GeneratedArtifactPurpose] = mapped_column(
        enum_column(GeneratedArtifactPurpose, name="generated_artifact_purpose"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(120), nullable=False)
    media_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DataExportArtifact(Base):
    __tablename__ = "data_export_artifacts"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_data_export_job"),
        UniqueConstraint("export_request_id", name="uq_data_export_request"),
        Index("ix_data_export_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    export_request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    included_files: Mapped[bool] = mapped_column(Boolean, nullable=False)
    encryption_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ServiceRequestNonce(Base):
    __tablename__ = "service_request_nonces"
    __table_args__ = (Index("ix_service_nonce_expires", "expires_at"),)

    nonce_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    service_id: Mapped[str] = mapped_column(String(80), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_analytics_event_received", "received_at"),
        Index("ix_analytics_event_aggregate", "event_name", "platform", "outcome"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_name: Mapped[str] = mapped_column(String(80), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    surface: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "scope", "idempotency_key", name="uq_idempotency_scope_key"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36))
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class DeletedSubjectTombstone(Base):
    """Minimal non-expiring marker that prevents silent account recreation."""

    __tablename__ = "deleted_subject_tombstones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_fingerprint: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    fingerprint_key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    first_deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DeletionRequest(Base):
    __tablename__ = "deletion_requests"
    __table_args__ = (Index("ix_deletion_user_requested", "user_id", "requested_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    subject_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[DeletionStatus] = mapped_column(
        enum_column(DeletionStatus, name="deletion_status"),
        default=DeletionStatus.REQUESTED,
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    upload_quiescence_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
