"""Strict clinician collaboration and fragment-secret sharing contracts."""

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

from .models import (
    AccessActorType,
    AccessEventType,
    AccessGrantStatus,
    ClinicianReviewStatus,
    ClinicianVerificationStatus,
    ReviewAnnotationKind,
    ShareLinkStatus,
    ShareResourceType,
)
from .schemas import ApiModel


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(_utc)]
ResourceId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
]


class ClinicianVerificationCreate(ApiModel):
    profession: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)
    ]
    license_jurisdiction: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)
    ]
    license_number: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=4, max_length=80),
    ]
    organization: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)
        ]
        | None
    ) = None
    applicant_evidence_ref: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=4, max_length=160)
    ]


class AdminReviewEvidence(ApiModel):
    source: ShortText
    reference_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=4, max_length=160)
    ]
    checked_at: UtcDateTime
    reviewer_notes: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
        ]
        | None
    ) = None


class ClinicianVerificationDecision(ApiModel):
    status: Literal[
        ClinicianVerificationStatus.VERIFIED,
        ClinicianVerificationStatus.REJECTED,
    ]
    decision_reason: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=2, max_length=500),
        ]
        | None
    ) = None
    evidence: AdminReviewEvidence

    @model_validator(mode="after")
    def rejection_requires_reason(self):
        if (
            self.status is ClinicianVerificationStatus.REJECTED
            and self.decision_reason is None
        ):
            raise ValueError("Rejected verification requires a decision reason.")
        return self


class ClinicianIdentityRoleResponse(ApiModel):
    required_claim: ShortText
    required_value: Literal["clinician"] = "clinician"
    observation_status: Literal[
        "not_applicable",
        "awaiting_token_observation",
        "observed",
    ]
    oidc_role_observed_at: UtcDateTime | None = Field(
        description="Timestamp of the first validated clinician role observation."
    )
    privileged_access_ready: bool


class ClinicianVerificationResponse(ApiModel):
    verification_id: str
    applicant_user_id: str
    status: ClinicianVerificationStatus
    profession: str
    license_jurisdiction: str
    license_number_suffix: str
    organization: str | None
    applicant_evidence_ref: str
    submitted_at: UtcDateTime
    reviewer_user_id: str | None
    reviewer_evidence: AdminReviewEvidence | None
    decision_reason: str | None
    reviewed_at: UtcDateTime | None
    retention_expires_at: UtcDateTime
    identity_role: ClinicianIdentityRoleResponse


class ClinicianVerificationQueue(ApiModel):
    items: list[ClinicianVerificationResponse]
    next_cursor: str | None


class ResourceRef(ApiModel):
    resource_type: ShareResourceType
    resource_id: ResourceId


def _unique_resources(resources: list[ResourceRef]) -> list[ResourceRef]:
    keys = {(item.resource_type, item.resource_id) for item in resources}
    if len(keys) != len(resources):
        raise ValueError("Selected resources must be unique.")
    return resources


class AccessGrantCreate(ApiModel):
    clinician_user_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36)
    ]
    resources: list[ResourceRef] = Field(min_length=1, max_length=32)
    label: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
        ]
        | None
    ) = None
    expires_at: UtcDateTime | None = None

    @field_validator("resources")
    @classmethod
    def resources_are_unique(cls, value: list[ResourceRef]) -> list[ResourceRef]:
        return _unique_resources(value)


class AccessGrantResponse(ApiModel):
    grant_id: str
    patient_user_id: str
    clinician_user_id: str
    status: AccessGrantStatus
    label: str | None
    resources: list[ResourceRef]
    review_id: str
    expires_at: UtcDateTime
    revoked_at: UtcDateTime | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    retention_expires_at: UtcDateTime
    active: bool


class AccessGrantList(ApiModel):
    items: list[AccessGrantResponse]


class ShareCreate(ApiModel):
    resources: list[ResourceRef] = Field(min_length=1, max_length=32)
    expires_in_seconds: int = Field(default=86_400, ge=300, le=604_800)
    max_exchanges: int = Field(default=1, ge=1, le=10)

    @field_validator("resources")
    @classmethod
    def resources_are_unique(cls, value: list[ResourceRef]) -> list[ResourceRef]:
        return _unique_resources(value)


class ShareLinkResponse(ApiModel):
    share_id: str
    patient_user_id: str
    status: ShareLinkStatus
    resources: list[ResourceRef]
    expires_at: UtcDateTime
    max_exchanges: int
    exchange_count: int
    revoked_at: UtcDateTime | None
    created_at: UtcDateTime
    retention_expires_at: UtcDateTime
    active: bool


class ShareCreateResponse(ApiModel):
    share: ShareLinkResponse
    fragment_secret: Annotated[str, StringConstraints(min_length=40, max_length=128)]
    fragment_parameter: Literal["secret"] = "secret"


class ShareList(ApiModel):
    items: list[ShareLinkResponse]


class ShareExchangeCreate(ApiModel):
    share_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36)
    ]
    secret: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=40, max_length=128)
    ]


class ShareExchangeResponse(ApiModel):
    exchange_token: Annotated[str, StringConstraints(min_length=40, max_length=128)]
    authorization_scheme: Literal["Share"] = "Share"
    expires_at: UtcDateTime
    max_uses: int


class ShareViewerScopeResponse(ApiModel):
    share_id: str
    resources: list[ResourceRef]
    share_expires_at: UtcDateTime
    token_expires_at: UtcDateTime
    remaining_uses: int


class ResourceViewResponse(ApiModel):
    resource_type: ShareResourceType
    resource_id: str
    data: dict[str, Any]
    disclaimer: Literal["This result is not a diagnosis."] = (
        "This result is not a diagnosis."
    )


class ClinicianReviewStatusUpdate(ApiModel):
    status: Literal[
        ClinicianReviewStatus.IN_REVIEW,
        ClinicianReviewStatus.COMPLETED,
        ClinicianReviewStatus.DECLINED,
    ]
    summary: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
        ]
        | None
    ) = None


class ReviewAnnotationCreate(ApiModel):
    resource: ResourceRef
    kind: ReviewAnnotationKind
    body: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]


class ReviewAnnotationResponse(ApiModel):
    annotation_id: str
    review_id: str
    clinician_user_id: str
    resource: ResourceRef
    kind: ReviewAnnotationKind
    body: str
    created_at: UtcDateTime
    retention_expires_at: UtcDateTime


class ClinicianReviewResponse(ApiModel):
    review_id: str
    grant_id: str
    patient_user_id: str
    clinician_user_id: str
    status: ClinicianReviewStatus
    summary: str | None
    resources: list[ResourceRef]
    annotations: list[ReviewAnnotationResponse]
    grant_expires_at: UtcDateTime
    grant_revoked_at: UtcDateTime | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    started_at: UtcDateTime | None
    completed_at: UtcDateTime | None
    retention_expires_at: UtcDateTime
    access_active: bool


class ClinicianReviewQueue(ApiModel):
    items: list[ClinicianReviewResponse]
    next_cursor: str | None


class AccessHistoryItem(ApiModel):
    event_id: str
    actor_user_id: str | None
    actor_type: AccessActorType
    event_type: AccessEventType
    resource_type: str
    resource_id: str | None
    grant_id: str | None
    share_id: str | None
    review_id: str | None
    details: dict[str, Any]
    created_at: UtcDateTime
    retention_expires_at: UtcDateTime


class AccessHistoryResponse(ApiModel):
    items: list[AccessHistoryItem]
    next_cursor: str | None
