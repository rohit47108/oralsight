"""Consent-first analytics contracts with no health or content fields."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from .schemas import ApiModel

POLICY_VERSION = "analytics-v1"

AnalyticsName = Literal[
    "app_opened",
    "onboarding_completed",
    "scan_started",
    "scan_completed",
    "capture_retake_requested",
    "analysis_completed",
    "analysis_unavailable",
    "comparison_viewed",
    "observation_map_viewed",
    "report_generated",
    "report_downloaded",
    "summary_video_generated",
    "share_created",
    "share_revoked",
    "clinician_review_requested",
    "learning_section_viewed",
    "notification_permission_changed",
]
AnalyticsSurface = Literal[
    "app",
    "onboarding",
    "scan",
    "result",
    "comparison",
    "map",
    "report",
    "sharing",
    "clinician",
    "learn",
    "settings",
]
AnalyticsOutcome = Literal[
    "started",
    "completed",
    "abstained",
    "cancelled",
    "failed",
    "viewed",
    "generated",
    "shared",
    "revoked",
    "enabled",
    "disabled",
]


class AnalyticsConsentUpdate(ApiModel):
    enabled: bool
    policy_version: Literal["analytics-v1"] = POLICY_VERSION


class AnalyticsConsentResponse(ApiModel):
    enabled: bool
    policy_version: str | None
    updated_at: datetime | None


class AnalyticsEventInput(ApiModel):
    name: AnalyticsName
    platform: Literal["ios", "android", "web"]
    app_version: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._+-]{1,32}$")]
    surface: AnalyticsSurface
    outcome: AnalyticsOutcome


class AnalyticsBatch(ApiModel):
    events: list[AnalyticsEventInput] = Field(min_length=1, max_length=20)


class AnalyticsAccepted(ApiModel):
    accepted: int = Field(ge=1, le=20)
    retention_days: Literal[30] = 30


class AnalyticsAggregate(ApiModel):
    name: AnalyticsName
    platform: Literal["ios", "android", "web"]
    outcome: AnalyticsOutcome
    count: int = Field(ge=5)


class AnalyticsSummary(ApiModel):
    days: int = Field(ge=1, le=30)
    minimum_group_size: Literal[5] = 5
    groups: list[AnalyticsAggregate]
    generated_at: datetime
