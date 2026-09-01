"""Strict platform-v2 product and encrypted-sync request/response schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .models import (
    AnalysisOrigin,
    AnalysisStatus,
    CalibrationStatus,
    CaptureAngle,
    CaptureProtocol,
    CaptureStatus,
    InputOrigin,
    JobStatus,
    JobType,
    LesionStatus,
    MatchDecisionValue,
    MatchProposalOrigin,
    MediaKind,
    MouthRegion,
    ReportFormat,
    ScanStatus,
    SyncApplyStatus,
    SyncEntityType,
    SyncOperationKind,
)
from .schemas import ApiModel

PLATFORM_CONTRACT_VERSION = "2.0.0"
DISCLAIMER = "This result is not a diagnosis."


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(_utc)]
PlatformId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
EncryptedPayload = Annotated[
    str, StringConstraints(min_length=16, max_length=1_000_000)
]


class AnatomicalSite(StrEnum):
    DORSAL_TONGUE = "dorsal_tongue"
    VENTRAL_TONGUE = "ventral_tongue"
    LEFT_LATERAL_TONGUE = "left_lateral_tongue"
    RIGHT_LATERAL_TONGUE = "right_lateral_tongue"
    FLOOR_OF_MOUTH = "floor_of_mouth"
    HARD_PALATE = "hard_palate"
    SOFT_PALATE = "soft_palate"
    OROPHARYNX = "oropharynx"
    LEFT_BUCCAL_MUCOSA = "left_buccal_mucosa"
    RIGHT_BUCCAL_MUCOSA = "right_buccal_mucosa"
    UPPER_LABIAL_MUCOSA = "upper_labial_mucosa"
    LOWER_LABIAL_MUCOSA = "lower_labial_mucosa"
    UPPER_GINGIVA = "upper_gingiva"
    LOWER_GINGIVA = "lower_gingiva"
    UPPER_TEETH = "upper_teeth"
    LOWER_TEETH = "lower_teeth"
    OTHER_VISIBLE_ORAL_TISSUE = "other_visible_oral_tissue"


class ModelHead(StrEnum):
    SEGMENTATION = "segmentation"
    ANATOMY = "anatomy"
    APPEARANCE = "appearance"
    DISEASE_RESEARCH = "disease_research"
    LESION_REIDENTIFICATION = "lesion_reidentification"
    QUALITY_CONTROL = "quality_control"
    ORAL_TISSUE_SEGMENTATION = "oral_tissue_segmentation"
    OUT_OF_DISTRIBUTION = "out_of_distribution"
    SECONDARY_SEGMENTATION = "secondary_segmentation"


class DeviceCreate(ApiModel):
    installation_id: Annotated[str, StringConstraints(min_length=16, max_length=128)]
    platform: Literal["ios", "android", "web"]
    display_name: (
        Annotated[str, StringConstraints(min_length=1, max_length=120)] | None
    ) = None
    public_key: (
        Annotated[str, StringConstraints(min_length=32, max_length=8192)] | None
    ) = None


class DeviceResponse(ApiModel):
    device_id: PlatformId
    platform: str
    display_name: str | None
    created_at: UtcDateTime
    revoked_at: UtcDateTime | None


class DeviceList(ApiModel):
    items: list[DeviceResponse]


class ScanSessionCreate(ApiModel):
    protocol: CaptureProtocol = CaptureProtocol.STANDARD
    device_id: PlatformId | None = None
    consent_record_id: PlatformId


class ScanSessionResponse(ApiModel):
    contract_version: Literal["2.0.0"] = PLATFORM_CONTRACT_VERSION
    scan_session_id: PlatformId
    consent_record_id: PlatformId | None
    protocol: CaptureProtocol
    status: ScanStatus
    created_at: UtcDateTime
    updated_at: UtcDateTime
    completed_at: UtcDateTime | None


class CaptureSetCreate(ApiModel):
    region: MouthRegion
    protocol: CaptureProtocol


class CaptureAssetInput(ApiModel):
    media_kind: MediaKind
    mime_type: Annotated[str, StringConstraints(min_length=3, max_length=128)]
    byte_size: int = Field(gt=0, le=2_147_483_647)
    sha256: Sha256
    width_px: int = Field(gt=0, le=32_768)
    height_px: int = Field(gt=0, le=32_768)
    duration_ms: int | None = Field(default=None, gt=0, le=60_000)
    input_origin: InputOrigin
    encrypted: Literal[True] = True
    retention_expires_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def validate_media(self):
        if (self.media_kind is MediaKind.VIDEO) != (self.duration_ms is not None):
            raise ValueError("Exactly video assets require durationMs.")
        return self


class CaptureAssetResponse(ApiModel):
    asset_id: PlatformId
    media_kind: MediaKind
    mime_type: str
    byte_size: int
    sha256: Sha256
    width_px: int
    height_px: int
    duration_ms: int | None
    input_origin: InputOrigin
    encrypted: Literal[True]
    created_at: UtcDateTime
    retention_expires_at: UtcDateTime | None
    upload_status: CaptureStatus


class AssetTransferIntentResponse(ApiModel):
    asset_id: PlatformId
    method: Literal["PUT", "GET"]
    url: Annotated[str, StringConstraints(min_length=1, max_length=8192)]
    headers: dict[str, str]
    expires_at: UtcDateTime


class AssetFinalizeResponse(ApiModel):
    asset: CaptureAssetResponse
    checksum_verified: Literal[True] = True


class ScanSessionList(ApiModel):
    items: list[ScanSessionResponse]
    next_cursor: str | None = None


class CaptureSetList(ApiModel):
    items: list["CaptureSetResponse"]
    next_cursor: str | None = None


class CaptureViewCreate(ApiModel):
    angle: CaptureAngle
    anatomical_site: AnatomicalSite | None = None
    asset: CaptureAssetInput
    source_video_asset_id: PlatformId | None = None
    quality_accepted: Literal[True] = True
    quality_reasons: list[
        Annotated[str, StringConstraints(min_length=1, max_length=256)]
    ] = Field(default_factory=list, max_length=32)
    ordinal: int = Field(ge=0, le=31)
    captured_at: UtcDateTime
    make_primary: bool = False

    @model_validator(mode="after")
    def validate_capture_view(self):
        if self.asset.media_kind is MediaKind.VIDEO:
            raise ValueError("A capture view must be an image or extracted frame.")
        if (self.asset.media_kind is MediaKind.VIDEO_FRAME) != (
            self.source_video_asset_id is not None
        ):
            raise ValueError("Extracted frames require a source video asset.")
        return self


class CaptureViewResponse(ApiModel):
    capture_view_id: PlatformId
    capture_set_id: PlatformId
    region: MouthRegion
    anatomical_site: AnatomicalSite | None
    angle: CaptureAngle
    asset: CaptureAssetResponse
    source_video_asset_id: PlatformId | None
    quality_accepted: bool
    quality_reasons: list[str]
    ordinal: int
    captured_at: UtcDateTime


class CaptureSetResponse(ApiModel):
    contract_version: Literal["2.0.0"] = PLATFORM_CONTRACT_VERSION
    capture_set_id: PlatformId
    scan_session_id: PlatformId
    region: MouthRegion
    protocol: CaptureProtocol
    primary_view_id: PlatformId | None
    views: list[CaptureViewResponse]
    complete: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class CandidateMask(ApiModel):
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=4096)
    bounding_box: tuple[float, float, float, float]
    normalized_area: float = Field(ge=0, le=1)

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, value: list[tuple[float, float]]):
        if any(
            coordinate < 0 or coordinate > 1 for point in value for coordinate in point
        ):
            raise ValueError("Polygon coordinates must be normalized.")
        return value

    @field_validator("bounding_box")
    @classmethod
    def validate_bounding_box(cls, value: tuple[float, float, float, float]):
        x, y, width, height = value
        if (
            min(x, y) < 0
            or width <= 0
            or height <= 0
            or x + width > 1
            or y + height > 1
        ):
            raise ValueError("Bounding box must stay within normalized image bounds.")
        return value


class VisualDescriptors(ApiModel):
    normalized_area: float = Field(ge=0, le=1)
    perimeter: float = Field(ge=0)
    border_irregularity: float = Field(ge=0)
    mean_redness: float = Field(ge=0, le=1)
    mean_brightness: float = Field(ge=0, le=1)
    texture_contrast: float = Field(ge=0, le=1)
    measurement_label: Literal["approximate"] = "approximate"


class Uncertainty(ApiModel):
    overall_confidence: float = Field(ge=0, le=1)
    image_quality_confidence: float = Field(ge=0, le=1)
    dataset_similarity: float | None = Field(default=None, ge=0, le=1)
    model_agreement: float | None = Field(default=None, ge=0, le=1)
    limitations: list[
        Annotated[str, StringConstraints(min_length=1, max_length=512)]
    ] = Field(default_factory=list, max_length=64)


class ClassScore(ApiModel):
    label: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    probability: float = Field(ge=0, le=1)


class ModelOutput(ApiModel):
    enabled: bool
    gate_passed: bool
    top_label: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None
    confidence: float | None = Field(default=None, ge=0, le=1)
    scores: list[ClassScore] = Field(max_length=128)
    limitation: Annotated[str, StringConstraints(min_length=1, max_length=1000)]

    @model_validator(mode="after")
    def validate_release_gate(self):
        if self.enabled and not self.gate_passed:
            raise ValueError(
                "A model output cannot be enabled before its release gate passes."
            )
        if not self.enabled and (
            self.top_label is not None or self.confidence is not None or self.scores
        ):
            raise ValueError("Disabled model outputs cannot expose predictions.")
        return self


class CalibrationEvidence(ApiModel):
    status: CalibrationStatus
    method: Literal["versioned_reference_card"] = "versioned_reference_card"
    card_version: (
        Annotated[str, StringConstraints(min_length=1, max_length=64)] | None
    ) = None
    marker_id: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None = (
        None
    )
    reference_width_mm: float | None = Field(default=None, gt=0, le=1000)
    millimeters_per_pixel: float | None = Field(default=None, gt=0, le=100)
    estimated_width_mm: float | None = Field(default=None, ge=0, le=1000)
    estimated_height_mm: float | None = Field(default=None, ge=0, le=1000)
    estimated_area_mm2: float | None = Field(default=None, ge=0, le=1_000_000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    gate_reasons: list[
        Annotated[str, StringConstraints(min_length=1, max_length=256)]
    ] = Field(default_factory=list, max_length=32)
    calibrated_at: UtcDateTime | None = None
    model_versions: dict[
        Annotated[str, StringConstraints(min_length=1, max_length=128)],
        Annotated[str, StringConstraints(min_length=1, max_length=128)],
    ] = Field(default_factory=dict, max_length=64)
    measurement_label: Literal["calibrated estimate"] = "calibrated estimate"

    @model_validator(mode="after")
    def validate_calibration_gate(self):
        measurements = [
            self.reference_width_mm,
            self.millimeters_per_pixel,
            self.estimated_width_mm,
            self.estimated_height_mm,
            self.estimated_area_mm2,
        ]
        if self.status is not CalibrationStatus.VALID and any(
            value is not None for value in measurements
        ):
            raise ValueError("Millimeter values require valid calibration evidence.")
        if self.status is CalibrationStatus.VALID and (
            self.card_version is None
            or self.marker_id is None
            or self.reference_width_mm is None
            or self.millimeters_per_pixel is None
            or self.confidence is None
            or self.calibrated_at is None
            or self.gate_reasons
            or not self.model_versions
        ):
            raise ValueError("Valid calibration requires complete passing evidence.")
        if self.status is CalibrationStatus.INVALID and not self.gate_reasons:
            raise ValueError("Invalid calibration must include failed gate reasons.")
        return self


class CandidateObservationCreate(ApiModel):
    capture_view_id: PlatformId
    anatomical_site: AnatomicalSite | None = None
    candidate_mask: CandidateMask
    descriptors: VisualDescriptors
    calibration: CalibrationEvidence | None = None
    appearance_output: ModelOutput | None = None
    disease_research_output: ModelOutput | None = None
    uncertainty: Uncertainty
    named_mesh: (
        Annotated[str, StringConstraints(min_length=1, max_length=128)] | None
    ) = None
    uv_coordinates: tuple[float, float] | None = None
    asset_version: (
        Annotated[str, StringConstraints(min_length=1, max_length=128)] | None
    ) = None
    limitations: list[
        Annotated[str, StringConstraints(min_length=1, max_length=512)]
    ] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def validate_observation(self):
        if (
            abs(self.candidate_mask.normalized_area - self.descriptors.normalized_area)
            > 1e-6
        ):
            raise ValueError("Candidate mask and descriptor area must match.")
        mapping = [self.named_mesh, self.uv_coordinates, self.asset_version]
        if sum(value is not None for value in mapping) not in {0, 3}:
            raise ValueError(
                "A 3D mapping requires mesh, UV coordinates, and asset version."
            )
        if self.uv_coordinates and any(
            value < 0 or value > 1 for value in self.uv_coordinates
        ):
            raise ValueError("UV coordinates must be normalized.")
        return self


class CandidateObservationResponse(CandidateObservationCreate):
    observation_id: PlatformId
    analysis_run_id: PlatformId
    region: MouthRegion
    created_at: UtcDateTime


class AnalysisRunCreate(ApiModel):
    requested_heads: list[ModelHead] = Field(min_length=1, max_length=9)
    status: AnalysisStatus
    observations: list[CandidateObservationCreate] = Field(
        default_factory=list, max_length=128
    )
    input_origin: InputOrigin
    analysis_origin: AnalysisOrigin
    source_asset_sha256: list[Sha256] = Field(min_length=1, max_length=12)
    model_versions: dict[
        str, Annotated[str, StringConstraints(min_length=1, max_length=128)]
    ] = Field(min_length=1, max_length=64)
    artifact_hashes: dict[str, Sha256] = Field(default_factory=dict, max_length=64)
    abstention_reasons: list[
        Annotated[str, StringConstraints(min_length=1, max_length=512)]
    ] = Field(default_factory=list, max_length=64)
    started_at: UtcDateTime
    completed_at: UtcDateTime | None = None
    signed_envelope_id: PlatformId

    @model_validator(mode="after")
    def validate_analysis_provenance(self):
        if self.analysis_origin is AnalysisOrigin.UNAVAILABLE:
            raise ValueError("Unavailable analysis cannot be persisted as a result.")
        if self.input_origin is InputOrigin.LIVE_CAPTURE and self.analysis_origin in {
            AnalysisOrigin.CACHED_MODEL_RESULT,
            AnalysisOrigin.MANUAL_FIXTURE,
        }:
            raise ValueError("Fixture output cannot be attached to live capture.")
        if (
            self.analysis_origin is AnalysisOrigin.LIVE_MODEL
            and not self.artifact_hashes
        ):
            raise ValueError("Persistent live analysis requires artifact hashes.")
        if self.status is AnalysisStatus.COMPLETE and self.completed_at is None:
            raise ValueError("Complete analysis requires a completion timestamp.")
        if self.status is not AnalysisStatus.COMPLETE and self.observations:
            raise ValueError("Only complete analysis may contain observations.")
        if self.status is not AnalysisStatus.COMPLETE and not self.abstention_reasons:
            raise ValueError(
                "Non-complete analysis must explain why no result is available."
            )
        return self


class AnalysisRunResponse(ApiModel):
    contract_version: Literal["2.0.0"] = PLATFORM_CONTRACT_VERSION
    analysis_run_id: PlatformId
    capture_set_id: PlatformId
    requested_heads: list[ModelHead]
    status: AnalysisStatus
    observations: list[CandidateObservationResponse]
    input_origin: InputOrigin
    analysis_origin: AnalysisOrigin
    source_asset_sha256: list[Sha256]
    model_versions: dict[str, str]
    artifact_hashes: dict[str, Sha256]
    abstention_reasons: list[str]
    started_at: UtcDateTime
    completed_at: UtcDateTime | None
    persisted: Literal[True] = True
    signed_envelope_id: PlatformId
    disclaimer: Literal["This result is not a diagnosis."] = DISCLAIMER


class MatchProposalCreate(ApiModel):
    current_observation_id: PlatformId
    candidate_prior_observation_id: PlatformId
    candidate_lesion_id: PlatformId | None = None
    proposal_origin: MatchProposalOrigin = MatchProposalOrigin.AUTOMATIC_MODEL
    score: float | None = Field(default=None, ge=0, le=1)
    rank: int | None = Field(default=None, gt=0, le=100)
    model_versions: dict[
        str, Annotated[str, StringConstraints(min_length=1, max_length=128)]
    ] = Field(default_factory=dict, max_length=64)
    expires_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def distinct_observations(self):
        if self.current_observation_id == self.candidate_prior_observation_id:
            raise ValueError("A proposal requires two distinct observations.")
        automatic = self.proposal_origin is MatchProposalOrigin.AUTOMATIC_MODEL
        if automatic and (
            self.score is None or self.rank is None or not self.model_versions
        ):
            raise ValueError(
                "An automatic proposal requires a score, rank, and model versions."
            )
        if not automatic and (
            self.score is not None or self.rank is not None or self.model_versions
        ):
            raise ValueError(
                "A user-selected pair cannot claim an automatic score, rank, or model version."
            )
        return self


class MatchProposalResponse(ApiModel):
    proposal_id: PlatformId
    current_observation_id: PlatformId
    candidate_prior_observation_id: PlatformId
    candidate_lesion_id: PlatformId | None
    proposal_origin: MatchProposalOrigin
    score: float | None
    rank: int | None
    state: Literal["proposed"] = "proposed"
    automatically_confirmed: Literal[False] = False
    model_versions: dict[str, str]
    generated_at: UtcDateTime
    expires_at: UtcDateTime | None


class MatchDecisionCreate(ApiModel):
    decision: MatchDecisionValue
    rationale: (
        Annotated[str, StringConstraints(min_length=1, max_length=1000)] | None
    ) = None


class MatchDecisionResponse(ApiModel):
    decision_id: PlatformId
    proposal_id: PlatformId
    decision: MatchDecisionValue
    decided_by: Literal["patient"] = "patient"
    actor_id: PlatformId
    rationale: str | None
    decided_at: UtcDateTime
    lesion_id: PlatformId | None


class LesionCreate(ApiModel):
    first_observation_id: PlatformId
    label: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None


class LesionResponse(ApiModel):
    lesion_id: PlatformId
    region: MouthRegion
    anatomical_site: AnatomicalSite | None
    label: str | None
    status: LesionStatus
    confirmed_observation_ids: list[PlatformId]
    match_decision_ids: list[PlatformId]
    version: int
    created_at: UtcDateTime
    updated_at: UtcDateTime


class ReportCreate(ApiModel):
    scan_session_ids: list[PlatformId] = Field(min_length=1, max_length=64)
    format: ReportFormat
    asset_id: PlatformId
    sha256: Sha256
    byte_size: int = Field(gt=0, le=2_147_483_647)
    locale: Annotated[str, StringConstraints(min_length=2, max_length=35)]
    accessible: bool
    input_origins: list[InputOrigin] = Field(min_length=1, max_length=8)
    analysis_origins: list[AnalysisOrigin] = Field(min_length=1, max_length=8)
    model_versions: dict[
        str, Annotated[str, StringConstraints(min_length=1, max_length=128)]
    ] = Field(min_length=1, max_length=64)
    signed_envelope_id: PlatformId
    retention_expires_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def validate_report_provenance(self):
        fixture = any(
            value in {AnalysisOrigin.CACHED_MODEL_RESULT, AnalysisOrigin.MANUAL_FIXTURE}
            for value in self.analysis_origins
        )
        if fixture and any(
            value is not InputOrigin.BUNDLED_DEMO for value in self.input_origins
        ):
            raise ValueError("Fixture analysis cannot be mixed with live input.")
        if len(set(self.scan_session_ids)) != len(self.scan_session_ids):
            raise ValueError("Report scan session IDs must be unique.")
        return self


class ReportResponse(ReportCreate):
    contract_version: Literal["2.0.0"] = PLATFORM_CONTRACT_VERSION
    report_artifact_id: PlatformId
    patient_id: PlatformId
    created_at: UtcDateTime
    disclaimer: Literal["This result is not a diagnosis."] = DISCLAIMER


class ReportList(ApiModel):
    items: list[ReportResponse]
    next_cursor: str | None = None


class JobCreate(ApiModel):
    type: JobType
    input_refs: list[PlatformId] = Field(default_factory=list, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict, max_length=128)
    max_attempts: int = Field(default=5, gt=0, le=8)

    @field_validator("type")
    @classmethod
    def forbid_internal_deletion_job(cls, value: JobType):
        if value in {JobType.ACCOUNT_DELETION, JobType.DELETE_ALL}:
            raise ValueError(
                "Account deletion jobs are created by the delete-all endpoint."
            )
        return value


class JobResponse(ApiModel):
    job_id: PlatformId
    owner_id: PlatformId
    type: JobType
    status: JobStatus
    input_refs: list[PlatformId]
    output_refs: list[PlatformId]
    progress: float = Field(ge=0, le=1)
    attempt: int
    max_attempts: int
    error_code: str | None
    error_message: str | None
    created_at: UtcDateTime
    started_at: UtcDateTime | None
    completed_at: UtcDateTime | None
    expires_at: UtcDateTime
    outcome: Literal["complete", "unavailable", "cancelled", "failed"] | None = None
    reason_code: str | None = None
    result: dict[str, Any] | None = None
    cancellation_requested: bool = False

    @model_validator(mode="after")
    def validate_job_state(self):
        terminal = {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.EXPIRED,
        }
        if (self.status in terminal) != (self.completed_at is not None):
            raise ValueError("Exactly terminal jobs require a completion timestamp.")
        if self.status is JobStatus.SUCCEEDED and self.progress != 1:
            raise ValueError("Succeeded jobs must report complete progress.")
        if self.status is not JobStatus.FAILED and (
            self.error_code is not None or self.error_message is not None
        ):
            raise ValueError("Only failed jobs may expose error details.")
        return self


class JobList(ApiModel):
    items: list[JobResponse]
    next_cursor: str | None = None


class SyncOperationInput(ApiModel):
    contract_version: Literal["2.0.0"] = PLATFORM_CONTRACT_VERSION
    operation_id: PlatformId
    idempotency_key: Annotated[str, StringConstraints(min_length=16, max_length=256)]
    device_id: PlatformId
    entity_type: SyncEntityType
    entity_id: PlatformId
    version: int = Field(gt=0)
    sequence: int = Field(ge=0)
    occurred_at: UtcDateTime
    operation: SyncOperationKind
    encrypted_payload: EncryptedPayload | None
    tombstone: bool

    @model_validator(mode="after")
    def validate_operation_shape(self):
        if self.operation is SyncOperationKind.UPSERT and (
            self.encrypted_payload is None or self.tombstone
        ):
            raise ValueError(
                "Upsert requires encrypted payload and cannot be a tombstone."
            )
        if self.operation is SyncOperationKind.DELETE and (
            self.encrypted_payload is not None or not self.tombstone
        ):
            raise ValueError("Delete requires a tombstone and no payload.")
        return self


class SyncPushRequest(ApiModel):
    operations: list[SyncOperationInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_operations(self):
        if len({value.operation_id for value in self.operations}) != len(
            self.operations
        ):
            raise ValueError("Operation IDs must be unique in one push.")
        return self


class SyncApplyResult(ApiModel):
    operation_id: PlatformId
    status: SyncApplyStatus
    server_sequence: int | None


class SyncCursorResponse(ApiModel):
    contract_version: Literal["2.0.0"] = PLATFORM_CONTRACT_VERSION
    cursor: Annotated[str, StringConstraints(min_length=16, max_length=2048)]
    high_watermark: int = Field(ge=0)
    issued_at: UtcDateTime
    expires_at: UtcDateTime


class SyncPushResponse(ApiModel):
    results: list[SyncApplyResult]
    cursor: SyncCursorResponse


class SyncOperationOutput(SyncOperationInput):
    server_sequence: int = Field(gt=0)


class SyncPullResponse(ApiModel):
    operations: list[SyncOperationOutput]
    cursor: SyncCursorResponse
    has_more: bool


class StoredReplay(ApiModel):
    payload: dict[str, Any]
    status_code: int
