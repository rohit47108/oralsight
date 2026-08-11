"""Versioned, strict job contracts used on the Redis stream."""

from __future__ import annotations

import re
from base64 import b64decode
from binascii import Error as Base64Error
from datetime import datetime, timedelta
from enum import StrEnum
from math import isfinite
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

JOB_SCHEMA_VERSION = "oralsight.job.v1"
INFERENCE_CONTRACT_VERSION = "1.1.0"
MAX_INPUT_RETENTION = timedelta(hours=24)
MAX_SUCCESS_RETENTION = timedelta(days=30)
MAX_FAILURE_RETENTION = timedelta(days=7)


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(piece.capitalize() for piece in rest)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
        validate_assignment=True,
    )


class MouthRegion(StrEnum):
    DORSAL_TONGUE = "dorsal_tongue"
    VENTRAL_TONGUE = "ventral_tongue"
    LEFT_BUCCAL_MUCOSA = "left_buccal_mucosa"
    RIGHT_BUCCAL_MUCOSA = "right_buccal_mucosa"
    UPPER_LIP = "upper_lip"
    LOWER_LIP = "lower_lip"
    UPPER_DENTAL_ARCH = "upper_dental_arch"
    LOWER_DENTAL_ARCH = "lower_dental_arch"


MESH_BY_REGION: dict[MouthRegion, str] = {
    MouthRegion.DORSAL_TONGUE: "tongue_dorsal",
    MouthRegion.VENTRAL_TONGUE: "tongue_ventral",
    MouthRegion.LEFT_BUCCAL_MUCOSA: "buccal_left",
    MouthRegion.RIGHT_BUCCAL_MUCOSA: "buccal_right",
    MouthRegion.UPPER_LIP: "lip_upper",
    MouthRegion.LOWER_LIP: "lip_lower",
    MouthRegion.UPPER_DENTAL_ARCH: "arch_upper",
    MouthRegion.LOWER_DENTAL_ARCH: "arch_lower",
}


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


class AnalysisStatus(StrEnum):
    COMPLETE = "complete"
    ABSTAINED = "abstained"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class AnalysisOrigin(StrEnum):
    LIVE_MODEL = "live_model"
    CACHED_MODEL_RESULT = "cached_model_result"
    UNAVAILABLE = "unavailable"


class JobType(StrEnum):
    ANALYSIS = "analysis"
    COMPARISON = "comparison"
    RECONSTRUCTION = "reconstruction"
    REPORT = "report"
    SUMMARY_VIDEO = "summary_video"
    DATA_EXPORT = "data_export"
    DELETE_ALL = "delete_all"


class CleanupTargetKind(StrEnum):
    SANITIZED_INPUT = "sanitized_input"
    GENERATED_ARTIFACT = "generated_artifact"
    CACHE_ENTRY = "cache_entry"


class CleanupTarget(StrictModel):
    kind: CleanupTargetKind
    resource_id: UUID


class RetentionPolicy(StrictModel):
    """Explicit deletion deadlines; these are ceilings, not promises to retain."""

    input_delete_after: AwareDatetime
    success_delete_after: AwareDatetime
    failure_delete_after: AwareDatetime
    dead_letter_delete_after: AwareDatetime
    cleanup_targets: list[CleanupTarget] = Field(default_factory=list, max_length=128)


class AssetPointer(StrictModel):
    """Opaque platform asset reference; job streams never carry image bytes or URLs."""

    asset_id: UUID
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(ge=1, le=8_000_000)


class CalibrationRequest(StrictModel):
    card_version: Literal["oralsight-calibration-v1"] = "oralsight-calibration-v1"
    marker_id: Literal[17] = 17
    marker_side_mm: Literal[20.0] = 20.0
    plane_confirmed: bool


class AnalyzePayload(StrictModel):
    kind: Literal[JobType.ANALYSIS] = JobType.ANALYSIS
    contract_version: Literal[INFERENCE_CONTRACT_VERSION] = INFERENCE_CONTRACT_VERSION
    capture_id: UUID
    image: AssetPointer
    selected_region: MouthRegion
    requested_heads: list[ModelHead] = Field(min_length=1, max_length=9)
    input_origin: Literal["live_capture"] = "live_capture"
    calibration: CalibrationRequest | None = None

    @field_validator("requested_heads")
    @classmethod
    def heads_are_unique(cls, value: list[ModelHead]) -> list[ModelHead]:
        if len(value) != len(set(value)):
            raise ValueError("requested_heads must be unique")
        return value

    @model_validator(mode="after")
    def inference_image_fits_request_limit(self) -> AnalyzePayload:
        if self.image.size_bytes > 1_750_000:
            raise ValueError("Analysis images cannot exceed 1,750,000 bytes.")
        return self


class PriorAnalysisMetadata(StrictModel):
    capture_id: UUID
    region: MouthRegion
    status: AnalysisStatus
    analysis_origin: AnalysisOrigin
    quality_accepted: bool
    candidate_normalized_area: float | None = Field(default=None, ge=0, le=1)
    model_versions: dict[str, str] = Field(max_length=32)

    @field_validator("model_versions")
    @classmethod
    def model_versions_are_identifiers(cls, value: dict[str, str]) -> dict[str, str]:
        pattern = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
        if any(
            not pattern.fullmatch(key) or not pattern.fullmatch(version)
            for key, version in value.items()
        ):
            raise ValueError("Model versions must contain safe identifiers only.")
        return value


class ComparePayload(StrictModel):
    kind: Literal[JobType.COMPARISON] = JobType.COMPARISON
    contract_version: Literal[INFERENCE_CONTRACT_VERSION] = INFERENCE_CONTRACT_VERSION
    baseline_capture_id: UUID
    current_capture_id: UUID
    baseline_image: AssetPointer
    current_image: AssetPointer
    region: MouthRegion
    user_confirmed_match: bool
    input_origin: Literal["live_capture"] = "live_capture"
    baseline_analysis: PriorAnalysisMetadata
    current_analysis: PriorAnalysisMetadata

    @model_validator(mode="after")
    def references_match(self) -> ComparePayload:
        if self.baseline_capture_id == self.current_capture_id:
            raise ValueError("Comparison captures must differ.")
        for capture_id, analysis in (
            (self.baseline_capture_id, self.baseline_analysis),
            (self.current_capture_id, self.current_analysis),
        ):
            if analysis.capture_id != capture_id or analysis.region != self.region:
                raise ValueError("Prior analysis must match its capture and region.")
        if (
            self.baseline_image.size_bytes > 1_750_000
            or self.current_image.size_bytes > 1_750_000
        ):
            raise ValueError("Comparison images cannot exceed 1,750,000 bytes.")
        return self


class ReconstructionView(StrictModel):
    capture_id: UUID
    image: AssetPointer
    region: MouthRegion
    angle_label: Literal["center", "left", "right", "up", "down", "sweep_frame"]
    camera_pose_id: UUID | None = None


class ReconstructionPin(StrictModel):
    observation_id: UUID
    region: MouthRegion
    mesh_name: str = Field(pattern=r"^[A-Za-z0-9._-]{1,128}$")
    uv_coordinates: tuple[float, float]
    asset_version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,128}$")
    observed_at: AwareDatetime
    status: Literal[
        "tracking",
        "retake_required",
        "stable",
        "visually_changed",
        "review_unavailable",
        "professional_review_suggested",
        "clinician_reviewed",
    ]
    user_confirmed: Literal[True] = True
    estimated_area_mm2: float | None = Field(default=None, ge=0, le=100_000)
    measurement_label: Literal["approximate", "calibrated estimate"] = "approximate"
    guidance_rule_version: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9._:/-]{1,128}$"
    )

    @model_validator(mode="after")
    def map_identity_and_measurement_are_coherent(self) -> ReconstructionPin:
        if self.mesh_name != MESH_BY_REGION[self.region]:
            raise ValueError("A reconstruction pin must use its canonical mesh name.")
        if any(
            not isfinite(value) or value < 0 or value > 1
            for value in self.uv_coordinates
        ):
            raise ValueError("Reconstruction pin UV coordinates must be normalized.")
        if self.estimated_area_mm2 is not None and (
            self.measurement_label != "calibrated estimate"
        ):
            raise ValueError("Millimeter pin area requires valid calibration evidence.")
        if self.status == "professional_review_suggested" and (
            self.guidance_rule_version is None
        ):
            raise ValueError(
                "Review status requires a clinician-approved rule version."
            )
        if self.status != "professional_review_suggested" and (
            self.guidance_rule_version is not None
        ):
            raise ValueError("Only approved review status may name a guidance rule.")
        return self


class ReconstructionPayload(StrictModel):
    kind: Literal[JobType.RECONSTRUCTION] = JobType.RECONSTRUCTION
    capture_set_id: UUID
    views: list[ReconstructionView] = Field(min_length=3, max_length=64)
    pins: list[ReconstructionPin] = Field(default_factory=list, max_length=256)
    calibration_id: UUID | None = None
    requested_format: Literal["glb"] = "glb"
    approximation_label: Literal["oral observation surface"] = (
        "oral observation surface"
    )

    @field_validator("views")
    @classmethod
    def view_captures_are_unique(
        cls, value: list[ReconstructionView]
    ) -> list[ReconstructionView]:
        identifiers = [view.capture_id for view in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Reconstruction views must use unique capture IDs.")
        return value

    @field_validator("pins")
    @classmethod
    def pin_observations_are_unique(
        cls, value: list[ReconstructionPin]
    ) -> list[ReconstructionPin]:
        identifiers = [pin.observation_id for pin in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Reconstruction pins must use unique observations.")
        return value


class ReportPatientProfile(StrictModel):
    age_range: Literal["under_18", "18_39", "40_64", "65_plus", "prefer_not_to_say"]
    assisted: bool


class ReportIntakeSummary(StrictModel):
    first_noticed: str = Field(max_length=500)
    duration_days: int | None = Field(default=None, ge=0, le=36_500)
    symptoms: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=30
    )
    bleeding_frequency: Literal["once", "occasionally", "often"] | None = None
    bleeding_duration: str | None = Field(default=None, max_length=500)
    change: Literal["not_sure", "no_change", "slow_change", "rapid_change"]
    tobacco_exposure: Literal["none", "past", "current", "prefer_not_to_say"]
    alcohol_exposure: Literal["none", "some", "frequent", "prefer_not_to_say"]
    previous_conditions: str = Field(max_length=2_000)
    professionally_examined: bool


class ReportPayload(StrictModel):
    kind: Literal[JobType.REPORT] = JobType.REPORT
    scan_session_id: UUID
    consent_record_id: UUID
    observation_ids: list[UUID] = Field(min_length=1, max_length=256)
    comparison_ids: list[UUID] = Field(default_factory=list, max_length=256)
    patient_profile: ReportPatientProfile | None = None
    intake_summary: ReportIntakeSummary | None = None
    appointment_questions: list[Annotated[str, Field(min_length=1, max_length=240)]] = (
        Field(default_factory=list, max_length=8)
    )
    locale: Literal["en-US"] = "en-US"
    include_experimental_research_output: bool = False
    disclaimer: Literal["This result is not a diagnosis."] = (
        "This result is not a diagnosis."
    )


class VideoCandidateMask(StrictModel):
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=512)
    bounding_box: tuple[float, float, float, float]
    normalized_area: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def normalized_geometry_is_valid(self) -> VideoCandidateMask:
        if any(
            coordinate < 0 or coordinate > 1
            for point in self.polygon
            for coordinate in point
        ):
            raise ValueError("Candidate polygon coordinates must be normalized.")
        x, y, width, height = self.bounding_box
        if (
            min(x, y) < 0
            or width <= 0
            or height <= 0
            or x + width > 1 + 1e-6
            or y + height > 1 + 1e-6
        ):
            raise ValueError("Candidate bounds must be positive and normalized.")
        return self


class SummaryVideoObservation(StrictModel):
    observation_id: UUID
    region: MouthRegion
    current_capture_id: UUID
    current_observed_at: AwareDatetime
    current_image: AssetPointer
    current_candidate_mask: VideoCandidateMask | None = None
    baseline_capture_id: UUID | None = None
    baseline_observed_at: AwareDatetime | None = None
    baseline_image: AssetPointer | None = None
    baseline_candidate_mask: VideoCandidateMask | None = None
    user_confirmed_match: bool = False
    comparable: bool = False
    normalized_change: float | None = Field(default=None, ge=-1, le=10)
    registration_confidence: float | None = Field(default=None, ge=0, le=1)
    appearance_label: (
        Literal[
            "red-patch",
            "white-patch",
            "ulcer-like",
            "mixed",
            "pigmented",
            "none-detected",
            "unsupported",
        ]
        | None
    ) = None
    quality_score: float = Field(ge=0, le=1)
    estimated_area_mm2: float | None = Field(default=None, ge=0, le=100_000)
    measurement_label: Literal["approximate", "calibrated estimate"] = "approximate"

    @model_validator(mode="after")
    def progression_fields_are_coherent(self) -> SummaryVideoObservation:
        baseline_values = (
            self.baseline_capture_id,
            self.baseline_observed_at,
            self.baseline_image,
        )
        if any(value is not None for value in baseline_values) and not all(
            value is not None for value in baseline_values
        ):
            raise ValueError("Baseline capture, date, and image must travel together.")
        if self.baseline_candidate_mask is not None and self.baseline_image is None:
            raise ValueError("A baseline mask requires its baseline image.")
        if self.baseline_capture_id == self.current_capture_id:
            raise ValueError("Baseline and current captures must differ.")
        if self.comparable and not self.user_confirmed_match:
            raise ValueError("Comparable progression requires user confirmation.")
        if self.comparable and self.baseline_image is None:
            raise ValueError("Comparable progression requires baseline evidence.")
        if self.normalized_change is not None and (
            not self.comparable or self.registration_confidence is None
        ):
            raise ValueError("Change requires comparable registered evidence.")
        if self.estimated_area_mm2 is not None and (
            self.measurement_label != "calibrated estimate"
        ):
            raise ValueError("Millimeter area requires valid calibration evidence.")
        return self


class SummaryVideoGuidance(StrictModel):
    code: Literal[
        "neutral_seek_care_information",
        "retake_for_image_quality",
        "continue_user_selected_tracking",
        "professional_review_suggested",
        "prompt_professional_review_suggested",
    ]
    source: Literal["neutral", "quality_policy", "clinician_approved_rule"]
    rule_version: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:/-]{1,128}$")

    @model_validator(mode="after")
    def clinical_guidance_requires_approved_rule(self) -> SummaryVideoGuidance:
        clinical_codes = {
            "professional_review_suggested",
            "prompt_professional_review_suggested",
        }
        if self.code in clinical_codes and (
            self.source != "clinician_approved_rule" or self.rule_version is None
        ):
            raise ValueError("Review guidance requires a clinician-approved rule.")
        if self.source == "clinician_approved_rule" and self.rule_version is None:
            raise ValueError("Approved guidance requires its rule version.")
        if self.source != "clinician_approved_rule" and self.rule_version is not None:
            raise ValueError("Only approved guidance may name a rule version.")
        return self


class SummaryVideoPayload(StrictModel):
    kind: Literal[JobType.SUMMARY_VIDEO] = JobType.SUMMARY_VIDEO
    scan_session_id: UUID
    report_id: UUID
    template_version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")
    selected_observations: list[SummaryVideoObservation] = Field(
        min_length=1, max_length=3
    )
    guidance: SummaryVideoGuidance
    duration_seconds: int = Field(default=30, ge=10, le=90)
    captions_required: Literal[True] = True
    include_audio: Literal[False] = False
    disclaimer: Literal["This result is not a diagnosis."] = (
        "This result is not a diagnosis."
    )

    @field_validator("selected_observations")
    @classmethod
    def selected_observations_are_unique(
        cls, value: list[SummaryVideoObservation]
    ) -> list[SummaryVideoObservation]:
        identifiers = [observation.observation_id for observation in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Summary observations must be unique.")
        return value


class DataExportEncryption(StrictModel):
    scheme: Literal["x25519-hkdf-sha256-aes-256-gcm"] = "x25519-hkdf-sha256-aes-256-gcm"
    recipient_public_key_b64: str = Field(pattern=r"^[A-Za-z0-9+/]{43}=$")

    @field_validator("recipient_public_key_b64")
    @classmethod
    def recipient_key_is_raw_x25519(cls, value: str) -> str:
        try:
            decoded = b64decode(value, validate=True)
        except (ValueError, Base64Error) as exc:
            raise ValueError("The export recipient key is not valid base64.") from exc
        if len(decoded) != 32:
            raise ValueError("The export recipient key must contain 32 raw bytes.")
        return value


class DataExportPayload(StrictModel):
    kind: Literal[JobType.DATA_EXPORT] = JobType.DATA_EXPORT
    export_request_id: UUID
    scope: Literal["all_portable_data"] = "all_portable_data"
    format: Literal["zip"] = "zip"
    encryption: DataExportEncryption
    include_files: bool = True
    disclaimer: Literal["This result is not a diagnosis."] = (
        "This result is not a diagnosis."
    )


class DeleteAllPayload(StrictModel):
    kind: Literal[JobType.DELETE_ALL] = JobType.DELETE_ALL
    deletion_request_id: UUID
    subject_account_id: UUID
    scope: Literal["all_oralsight_data"] = "all_oralsight_data"
    rotate_installation_key: Literal[True] = True


JobPayload = Annotated[
    AnalyzePayload
    | ComparePayload
    | ReconstructionPayload
    | ReportPayload
    | SummaryVideoPayload
    | DataExportPayload
    | DeleteAllPayload,
    Field(discriminator="kind"),
]


class JobEnvelope(StrictModel):
    schema_version: Literal[JOB_SCHEMA_VERSION] = JOB_SCHEMA_VERSION
    job_id: UUID
    request_id: UUID
    account_id: UUID
    trace_id: UUID
    job_type: JobType
    created_at: AwareDatetime
    not_before: AwareDatetime
    expires_at: AwareDatetime
    idempotency_key: str = Field(
        min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    attempt: int = Field(default=1, ge=1, le=8)
    max_attempts: int = Field(default=5, ge=1, le=8)
    retention: RetentionPolicy
    payload: JobPayload

    @model_validator(mode="after")
    def envelope_is_coherent(self) -> JobEnvelope:
        if self.payload.kind != self.job_type:
            raise ValueError("job_type must match payload.kind")
        if (
            isinstance(self.payload, DeleteAllPayload)
            and self.payload.subject_account_id != self.account_id
        ):
            raise ValueError("Deletion subject must match the envelope account.")
        if self.attempt > self.max_attempts:
            raise ValueError("attempt cannot exceed max_attempts")
        if self.not_before < self.created_at:
            raise ValueError("not_before cannot precede created_at")
        if self.expires_at <= self.not_before:
            raise ValueError("expires_at must follow not_before")
        if self.expires_at > self.created_at + MAX_INPUT_RETENTION:
            raise ValueError(
                "A queued job cannot remain usable for more than 24 hours."
            )
        deadlines = self.retention
        if deadlines.input_delete_after > self.created_at + MAX_INPUT_RETENTION:
            raise ValueError("Input retention cannot exceed 24 hours.")
        if deadlines.input_delete_after < self.expires_at:
            raise ValueError("Input deletion cannot precede job expiration.")
        if deadlines.success_delete_after > self.created_at + MAX_SUCCESS_RETENTION:
            raise ValueError("Successful result retention cannot exceed 30 days.")
        if deadlines.failure_delete_after > self.created_at + MAX_FAILURE_RETENTION:
            raise ValueError("Failed result retention cannot exceed 7 days.")
        if deadlines.dead_letter_delete_after > self.created_at + MAX_FAILURE_RETENTION:
            raise ValueError("Dead-letter retention cannot exceed 7 days.")
        if any(
            deadline < self.created_at
            for deadline in (
                deadlines.input_delete_after,
                deadlines.success_delete_after,
                deadlines.failure_delete_after,
                deadlines.dead_letter_delete_after,
            )
        ):
            raise ValueError("Retention deadlines cannot precede job creation.")
        return self

    def next_attempt(self, *, not_before: datetime) -> JobEnvelope:
        return JobEnvelope.model_validate(
            {
                **self.model_dump(mode="python"),
                "attempt": self.attempt + 1,
                "not_before": not_before,
            }
        )


class JobOutcome(StrEnum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ProcessorResult(StrictModel):
    outcome: Literal[JobOutcome.COMPLETE, JobOutcome.UNAVAILABLE]
    result: dict[str, JsonValue] = Field(default_factory=dict)
    reason_code: str | None = Field(default=None, pattern=r"^[a-z0-9_]{3,64}$")

    @model_validator(mode="after")
    def unavailable_has_reason(self) -> ProcessorResult:
        if self.outcome is JobOutcome.UNAVAILABLE and self.reason_code is None:
            raise ValueError("Unavailable results require a reason code.")
        if self.outcome is JobOutcome.COMPLETE and self.reason_code is not None:
            raise ValueError("Completed results cannot include an unavailable reason.")
        return self


class ResultNotification(StrictModel):
    schema_version: Literal[JOB_SCHEMA_VERSION] = JOB_SCHEMA_VERSION
    job_id: UUID
    outcome: JobOutcome
    completed_at: AwareDatetime
    result: dict[str, JsonValue] = Field(default_factory=dict)
    reason_code: str | None = Field(default=None, pattern=r"^[a-z0-9_]{3,64}$")

    @model_validator(mode="after")
    def terminal_details_are_coherent(self) -> ResultNotification:
        non_complete = {
            JobOutcome.FAILED,
            JobOutcome.CANCELLED,
            JobOutcome.UNAVAILABLE,
        }
        if self.outcome in non_complete and self.reason_code is None:
            raise ValueError("Non-complete outcomes require a reason code.")
        if self.outcome is JobOutcome.COMPLETE and self.reason_code is not None:
            raise ValueError("Completed outcomes cannot include a reason code.")
        return self
