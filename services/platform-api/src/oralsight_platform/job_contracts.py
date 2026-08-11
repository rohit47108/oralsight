"""Worker-v1 queue contracts mirrored at the platform trust boundary."""

from __future__ import annotations

import re
from base64 import b64decode
from binascii import Error as Base64Error
from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from .models import JobType, MouthRegion

JOB_SCHEMA_VERSION = "oralsight.job.v1"
INFERENCE_CONTRACT_VERSION = "1.1.0"
DISCLAIMER = "This result is not a diagnosis."
MAX_INPUT_RETENTION = timedelta(hours=24)
MAX_SUCCESS_RETENTION = timedelta(days=30)
MAX_FAILURE_RETENTION = timedelta(days=7)
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


class AssetPointer(StrictModel):
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
    kind: Literal["analysis"] = "analysis"
    contract_version: Literal["1.1.0"] = INFERENCE_CONTRACT_VERSION
    capture_id: UUID
    image: AssetPointer
    selected_region: MouthRegion
    requested_heads: list[
        Literal[
            "segmentation",
            "anatomy",
            "appearance",
            "disease_research",
            "lesion_reidentification",
            "quality_control",
            "oral_tissue_segmentation",
            "out_of_distribution",
            "secondary_segmentation",
        ]
    ] = Field(min_length=1, max_length=9)
    input_origin: Literal["live_capture"] = "live_capture"
    calibration: CalibrationRequest | None = None

    @field_validator("requested_heads")
    @classmethod
    def heads_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("requestedHeads must be unique")
        return value

    @model_validator(mode="after")
    def inference_image_fits_request_limit(self):
        if self.image.size_bytes > 1_750_000:
            raise ValueError("Analysis images cannot exceed 1,750,000 bytes.")
        return self


class PriorAnalysisMetadata(StrictModel):
    capture_id: UUID
    region: MouthRegion
    status: Literal["complete", "abstained", "unsupported", "failed"]
    analysis_origin: Literal["live_model", "cached_model_result", "unavailable"]
    quality_accepted: bool
    candidate_normalized_area: float | None = Field(default=None, ge=0, le=1)
    model_versions: dict[str, str] = Field(max_length=32)

    @field_validator("model_versions")
    @classmethod
    def safe_versions(cls, value: dict[str, str]) -> dict[str, str]:
        pattern = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
        if any(
            not pattern.fullmatch(key) or not pattern.fullmatch(version)
            for key, version in value.items()
        ):
            raise ValueError("Model versions must contain safe identifiers only.")
        return value


class ComparePayload(StrictModel):
    kind: Literal["comparison"] = "comparison"
    contract_version: Literal["1.1.0"] = INFERENCE_CONTRACT_VERSION
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
    def references_match(self):
        if self.baseline_capture_id == self.current_capture_id:
            raise ValueError("Comparison captures must differ.")
        for capture_id, analysis in (
            (self.baseline_capture_id, self.baseline_analysis),
            (self.current_capture_id, self.current_analysis),
        ):
            if analysis.capture_id != capture_id or analysis.region != self.region:
                raise ValueError("Prior analysis must match its capture and region.")
        if (
            max(self.baseline_image.size_bytes, self.current_image.size_bytes)
            > 1_750_000
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
    def map_identity_and_measurement_are_coherent(self):
        if self.mesh_name != MESH_BY_REGION[self.region]:
            raise ValueError("A reconstruction pin must use its canonical mesh name.")
        if any(value < 0 or value > 1 for value in self.uv_coordinates):
            raise ValueError("Reconstruction pin UV coordinates must be normalized.")
        if self.estimated_area_mm2 is not None and (
            self.measurement_label != "calibrated estimate"
        ):
            raise ValueError("Millimeter pin area requires valid calibration evidence.")
        if self.status == "professional_review_suggested" and (
            self.guidance_rule_version is None
        ):
            raise ValueError("Review status requires an approved rule version.")
        if self.status != "professional_review_suggested" and (
            self.guidance_rule_version is not None
        ):
            raise ValueError("Only approved review status may name a rule version.")
        return self


class ReconstructionPayload(StrictModel):
    kind: Literal["reconstruction"] = "reconstruction"
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
    def unique_views(cls, value: list[ReconstructionView]) -> list[ReconstructionView]:
        ids = [item.capture_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Reconstruction capture IDs must be unique.")
        return value

    @field_validator("pins")
    @classmethod
    def unique_pins(cls, value: list[ReconstructionPin]) -> list[ReconstructionPin]:
        ids = [item.observation_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Reconstruction observations must be unique.")
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
    kind: Literal["report"] = "report"
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
    disclaimer: Literal[DISCLAIMER] = DISCLAIMER


class VideoCandidateMask(StrictModel):
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=512)
    bounding_box: tuple[float, float, float, float]
    normalized_area: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def normalized_geometry(self):
        if any(value < 0 or value > 1 for point in self.polygon for value in point):
            raise ValueError("Candidate polygon must be normalized.")
        x, y, width, height = self.bounding_box
        if (
            min(x, y) < 0
            or width <= 0
            or height <= 0
            or x + width > 1 + 1e-6
            or y + height > 1 + 1e-6
        ):
            raise ValueError("Candidate bounds must be normalized.")
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
    def progression_fields(self):
        baseline = (
            self.baseline_capture_id,
            self.baseline_observed_at,
            self.baseline_image,
        )
        if any(value is not None for value in baseline) and not all(
            value is not None for value in baseline
        ):
            raise ValueError("Baseline fields must travel together.")
        if self.baseline_candidate_mask is not None and self.baseline_image is None:
            raise ValueError("A baseline mask requires its image.")
        if self.baseline_capture_id == self.current_capture_id:
            raise ValueError("Baseline and current captures must differ.")
        if self.comparable and (
            not self.user_confirmed_match or self.baseline_image is None
        ):
            raise ValueError(
                "Comparable progression requires confirmed baseline evidence."
            )
        if self.normalized_change is not None and (
            not self.comparable or self.registration_confidence is None
        ):
            raise ValueError("Change requires comparable registered evidence.")
        if (
            self.estimated_area_mm2 is not None
            and self.measurement_label != "calibrated estimate"
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
    def approved_guidance_only(self):
        clinical = {
            "professional_review_suggested",
            "prompt_professional_review_suggested",
        }
        if self.code in clinical and (
            self.source != "clinician_approved_rule" or self.rule_version is None
        ):
            raise ValueError("Review guidance requires an approved rule.")
        if (self.source == "clinician_approved_rule") != (
            self.rule_version is not None
        ):
            raise ValueError("Approved rule source and version must travel together.")
        return self


class SummaryVideoPayload(StrictModel):
    kind: Literal["summary_video"] = "summary_video"
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
    disclaimer: Literal[DISCLAIMER] = DISCLAIMER

    @field_validator("selected_observations")
    @classmethod
    def unique_observations(
        cls, value: list[SummaryVideoObservation]
    ) -> list[SummaryVideoObservation]:
        ids = [item.observation_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Summary observations must be unique.")
        return value


class DeleteAllPayload(StrictModel):
    kind: Literal["delete_all"] = "delete_all"
    deletion_request_id: UUID
    subject_account_id: UUID
    scope: Literal["all_oralsight_data"] = "all_oralsight_data"
    rotate_installation_key: Literal[True] = True


class DataExportEncryption(StrictModel):
    scheme: Literal["x25519-hkdf-sha256-aes-256-gcm"] = "x25519-hkdf-sha256-aes-256-gcm"
    recipient_public_key_b64: str = Field(pattern=r"^[A-Za-z0-9+/]{43}=$")

    @field_validator("recipient_public_key_b64")
    @classmethod
    def raw_x25519_key(cls, value: str) -> str:
        try:
            decoded = b64decode(value, validate=True)
        except (ValueError, Base64Error) as exc:
            raise ValueError("The export public key is invalid.") from exc
        if len(decoded) != 32:
            raise ValueError("The export public key must contain 32 raw bytes.")
        return value


class DataExportPayload(StrictModel):
    kind: Literal["data_export"] = "data_export"
    export_request_id: UUID
    scope: Literal["all_portable_data"] = "all_portable_data"
    format: Literal["zip"] = "zip"
    encryption: DataExportEncryption
    include_files: bool = True
    disclaimer: Literal[DISCLAIMER] = DISCLAIMER


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
JOB_PAYLOAD_ADAPTER = TypeAdapter(JobPayload)


class CleanupTarget(StrictModel):
    kind: Literal["sanitized_input", "generated_artifact", "cache_entry"]
    resource_id: UUID


class RetentionPolicy(StrictModel):
    input_delete_after: AwareDatetime
    success_delete_after: AwareDatetime
    failure_delete_after: AwareDatetime
    dead_letter_delete_after: AwareDatetime
    cleanup_targets: list[CleanupTarget] = Field(default_factory=list, max_length=128)


class JobEnvelope(StrictModel):
    schema_version: Literal["oralsight.job.v1"] = JOB_SCHEMA_VERSION
    job_id: UUID
    request_id: UUID
    account_id: UUID
    trace_id: UUID
    job_type: Literal[
        "analysis",
        "comparison",
        "reconstruction",
        "report",
        "summary_video",
        "data_export",
        "delete_all",
    ]
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
    def coherent(self):
        if self.payload.kind != self.job_type:
            raise ValueError("Job type must match payload kind.")
        if (
            isinstance(self.payload, DeleteAllPayload)
            and self.payload.subject_account_id != self.account_id
        ):
            raise ValueError("Deletion subject must match the job account.")
        if self.attempt > self.max_attempts:
            raise ValueError("Attempt cannot exceed max attempts.")
        if self.not_before < self.created_at or self.expires_at <= self.not_before:
            raise ValueError("The job delivery window is invalid.")
        if self.expires_at > self.created_at + MAX_INPUT_RETENTION:
            raise ValueError("Queued jobs cannot remain usable beyond 24 hours.")
        retention = self.retention
        if retention.input_delete_after > self.created_at + MAX_INPUT_RETENTION:
            raise ValueError("Input retention cannot exceed 24 hours.")
        if retention.input_delete_after < self.expires_at:
            raise ValueError("Input deletion cannot precede job expiration.")
        if retention.success_delete_after > self.created_at + MAX_SUCCESS_RETENTION:
            raise ValueError("Successful result retention cannot exceed 30 days.")
        if retention.failure_delete_after > self.created_at + MAX_FAILURE_RETENTION:
            raise ValueError("Failed result retention cannot exceed 7 days.")
        if retention.dead_letter_delete_after > self.created_at + MAX_FAILURE_RETENTION:
            raise ValueError("Dead-letter retention cannot exceed 7 days.")
        if any(
            deadline < self.created_at
            for deadline in (
                retention.input_delete_after,
                retention.success_delete_after,
                retention.failure_delete_after,
                retention.dead_letter_delete_after,
            )
        ):
            raise ValueError("Retention deadlines cannot precede job creation.")
        return self


def validate_job_payload(job_type: JobType, payload: dict) -> JobPayload:
    normalized = {**payload, "kind": job_type.value}
    return JOB_PAYLOAD_ADAPTER.validate_python(normalized)


def queue_json(value: BaseModel) -> str:
    return value.model_dump_json(by_alias=True)
