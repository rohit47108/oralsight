"""Public version 2 account and deletion schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import DeletionStatus, UserRole, UserStatus


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str


class ReadinessResponse(ApiModel):
    status: Literal["ready", "not_ready"]
    database: Literal["ready", "unavailable"]
    queue: Literal["ready", "unavailable"]
    object_storage: Literal["ready", "unavailable"]


class MeResponse(ApiModel):
    id: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    deletion_pending: bool

    @field_validator("created_at", mode="after")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _as_utc(value)


class DeletionRequestCreate(ApiModel):
    confirmation: Literal["DELETE"]


class DeletionRequestResponse(ApiModel):
    request_id: str
    job_id: str
    status: DeletionStatus
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None

    @field_validator("requested_at", "started_at", "completed_at", mode="after")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value) if value is not None else None


class AcceptedResponse(ApiModel):
    accepted: bool = Field(default=True)


def _as_utc(value: datetime) -> datetime:
    # SQLite has no timezone-aware datetime type; production PostgreSQL does.
    # Stored timestamps are defined as UTC, so restore that marker in test reads.
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
