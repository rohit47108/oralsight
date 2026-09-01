"""Strict contracts for authenticated worker artifact publication."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .models import GeneratedArtifactPurpose
from .schemas import ApiModel
from .job_contracts import (
    ReportIntakeSummary,
    ReportPatientProfile,
    RetentionPolicy,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(_utc)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class GeneratedArtifactMetadata(ApiModel):
    job_id: Annotated[
        str, StringConstraints(pattern=r"^[a-f0-9-]{36}$", min_length=36, max_length=36)
    ]
    purpose: GeneratedArtifactPurpose
    filename: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$",
        ),
    ]
    media_type: Literal["model/gltf-binary", "video/mp4"]
    sha256: Sha256
    size_bytes: int = Field(ge=1, le=100_000_000)
    manifest: dict[str, Any]

    @field_validator("filename")
    @classmethod
    def filename_is_not_pathlike(cls, value: str) -> str:
        if ".." in value:
            raise ValueError("Filename cannot contain a parent-path segment.")
        return value

    @model_validator(mode="after")
    def purpose_matches_media(self):
        expected = {
            GeneratedArtifactPurpose.RECONSTRUCTION: ("model/gltf-binary", ".glb"),
            GeneratedArtifactPurpose.SUMMARY_VIDEO: ("video/mp4", ".mp4"),
        }[self.purpose]
        if self.media_type != expected[0] or not self.filename.lower().endswith(
            expected[1]
        ):
            raise ValueError("Artifact purpose, media type, and extension must agree.")
        return self


class GeneratedArtifactResponse(ApiModel):
    artifact_id: str
    owner_id: str
    job_id: str
    purpose: GeneratedArtifactPurpose
    filename: str
    media_type: str
    sha256: Sha256
    size_bytes: int
    object_key: str
    manifest: dict[str, Any]
    created_at: UtcDateTime
    retention_expires_at: UtcDateTime


class GeneratedArtifactList(ApiModel):
    items: list[GeneratedArtifactResponse]
    next_cursor: str | None = None


class WorkerResultNotification(ApiModel):
    schema_version: Literal["stoma3d.job.v1"]
    job_id: str
    outcome: Literal["complete", "unavailable", "cancelled", "failed"]
    completed_at: UtcDateTime
    result: dict[str, Any] = Field(default_factory=dict, max_length=128)
    reason_code: (
        Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{3,64}$")] | None
    ) = None

    @model_validator(mode="after")
    def result_shape(self):
        if self.outcome == "complete" and self.reason_code is not None:
            raise ValueError("Completed jobs cannot have a reason code.")
        if self.outcome != "complete" and self.reason_code is None:
            raise ValueError("Non-complete jobs require a reason code.")
        return self


class WorkerRetentionRegistration(ApiModel):
    outcome: Literal["complete", "unavailable", "cancelled", "failed"]
    retention: RetentionPolicy


class DeletionExecuteRequest(ApiModel):
    job_id: str
    subject_account_id: str
    scope: Literal["all_stoma3d_data"]
    rotate_installation_key: Literal[True]


class DeletionExecuteResponse(ApiModel):
    deletion_request_id: str
    status: Literal["complete"]
    rotate_installation_key: Literal[True]


class ReportRenderRequest(ApiModel):
    job_id: str
    scan_session_id: str
    consent_record_id: str
    observation_ids: list[str] = Field(min_length=1, max_length=256)
    comparison_ids: list[str] = Field(default_factory=list, max_length=256)
    patient_profile: ReportPatientProfile | None = None
    intake_summary: ReportIntakeSummary | None = None
    appointment_questions: list[
        Annotated[str, StringConstraints(min_length=1, max_length=240)]
    ] = Field(default_factory=list, max_length=8)
    locale: Literal["en-US"]
    include_experimental_research_output: bool
    disclaimer: Literal["This result is not a diagnosis."]


class ReportRenderResponse(ApiModel):
    artifact_id: str
    media_type: Literal["application/pdf"] = "application/pdf"
    sha256: Sha256
    byte_size: int = Field(gt=0, le=100_000_000)
    disclaimer: Literal["This result is not a diagnosis."] = (
        "This result is not a diagnosis."
    )


class ExportEncryptionRequest(ApiModel):
    scheme: Literal["x25519-hkdf-sha256-aes-256-gcm"]
    recipient_public_key_b64: Annotated[
        str, StringConstraints(pattern=r"^[A-Za-z0-9+/]{43}=$")
    ]


class ExportRenderRequest(ApiModel):
    job_id: str
    export_request_id: str
    scope: Literal["all_portable_data"]
    format: Literal["zip"]
    encryption: ExportEncryptionRequest
    include_files: bool
    disclaimer: Literal["This result is not a diagnosis."]


class ExportEncryptionResponse(ApiModel):
    scheme: Literal["x25519-hkdf-sha256-aes-256-gcm"]
    ephemeral_public_key_b64: str
    salt_b64: str
    nonce_b64: str


class ExportRenderResponse(ApiModel):
    export_request_id: str
    status: Literal["complete"]
    artifact_id: str
    media_type: Literal["application/vnd.stoma3d.export"]
    sha256: Sha256
    byte_size: int = Field(gt=0, le=2_147_483_647)
    encryption: ExportEncryptionResponse


class DataExportArtifactResponse(ApiModel):
    artifact_id: str
    export_request_id: str
    job_id: str
    media_type: Literal["application/vnd.stoma3d.export"] = (
        "application/vnd.stoma3d.export"
    )
    sha256: Sha256
    byte_size: int
    included_files: bool
    encryption: ExportEncryptionResponse
    created_at: UtcDateTime
    retention_expires_at: UtcDateTime


class DataExportArtifactList(ApiModel):
    items: list[DataExportArtifactResponse]
    next_cursor: str | None = None
