"""Versioned product-consent contracts separate from analytics consent."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from .schemas import ApiModel

ConsentIdentifier = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{1,120}$")
]


class ConsentCreate(ApiModel):
    document_id: ConsentIdentifier
    document_version: Annotated[
        str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{1,64}$")
    ]
    document_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    accepted: Literal[True]
    device_id: str | None = Field(default=None, max_length=36)


class ConsentResponse(ApiModel):
    consent_record_id: str
    document_id: str
    document_version: str
    document_sha256: str | None
    accepted: bool
    accepted_at: datetime
    revoked_at: datetime | None
    active: bool


class ConsentList(ApiModel):
    items: list[ConsentResponse]


class ConsentDocumentResponse(ApiModel):
    document_id: str
    document_version: str
    document_sha256: str
    title: str
    body: str
    withdrawal_effect: Literal[
        "blocks_new_cloud_work_revokes_access_preserves_existing_data"
    ] = "blocks_new_cloud_work_revokes_access_preserves_existing_data"


class ConsentRevoke(ApiModel):
    confirmation: Literal["REVOKE"]
