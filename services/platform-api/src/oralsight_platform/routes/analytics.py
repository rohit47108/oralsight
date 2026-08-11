"""Explicitly opted-in, allowlisted, short-lived product analytics."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..analytics_schemas import (
    AnalyticsAccepted,
    AnalyticsAggregate,
    AnalyticsBatch,
    AnalyticsConsentResponse,
    AnalyticsConsentUpdate,
    AnalyticsSummary,
)
from ..collaboration_common import append_audit_event
from ..dependencies import Actor, get_current_actor, get_session, require_oidc_roles
from ..errors import ServiceError
from ..models import AnalyticsEvent, User, UserRole, utc_now

router = APIRouter(prefix="/v2", tags=["privacy-safe analytics"])
EVENT_RETENTION = timedelta(days=30)


def _consent(value: User) -> AnalyticsConsentResponse:
    return AnalyticsConsentResponse(
        enabled=value.analytics_enabled,
        policy_version=value.analytics_policy_version,
        updated_at=value.analytics_updated_at,
    )


@router.get("/me/analytics-consent", response_model=AnalyticsConsentResponse)
async def get_analytics_consent(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnalyticsConsentResponse:
    user = await session.get(User, actor.user_id)
    if user is None:
        raise ServiceError(404, "account_not_found", "The account was not found.")
    return _consent(user)


@router.put("/me/analytics-consent", response_model=AnalyticsConsentResponse)
async def update_analytics_consent(
    body: AnalyticsConsentUpdate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnalyticsConsentResponse:
    user = await session.get(User, actor.user_id)
    if user is None:
        raise ServiceError(404, "account_not_found", "The account was not found.")
    now = utc_now()
    changed = user.analytics_enabled != body.enabled
    user.analytics_enabled = body.enabled
    user.analytics_policy_version = body.policy_version
    user.analytics_updated_at = now
    if changed:
        append_audit_event(
            session,
            patient_user_id=user.id,
            actor_user_id=user.id,
            event_type="analytics.consent_changed",
            resource_type="account",
            resource_id=user.id,
            request_id=request.state.request_id,
            details={"enabled": body.enabled, "policyVersion": body.policy_version},
        )
    await session.commit()
    return _consent(user)


@router.post(
    "/analytics/events",
    response_model=AnalyticsAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_analytics(
    body: AnalyticsBatch,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnalyticsAccepted:
    user = await session.get(User, actor.user_id)
    if user is None:
        raise ServiceError(404, "account_not_found", "The account was not found.")
    if not user.analytics_enabled:
        raise ServiceError(
            403,
            "analytics_consent_required",
            "Product analytics is off for this account.",
        )
    now = utc_now()
    session.add_all(
        [
            AnalyticsEvent(
                user_id=user.id,
                event_name=value.name,
                platform=value.platform,
                app_version=value.app_version,
                surface=value.surface,
                outcome=value.outcome,
                received_at=now,
                expires_at=now + EVENT_RETENTION,
            )
            for value in body.events
        ]
    )
    await session.commit()
    return AnalyticsAccepted(accepted=len(body.events))


@router.get("/admin/analytics/summary", response_model=AnalyticsSummary)
async def aggregate_analytics(
    _admin: Annotated[Actor, Depends(require_oidc_roles(UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    days: Annotated[int, Query(ge=1, le=30)] = 30,
) -> AnalyticsSummary:
    now = utc_now()
    rows = (
        await session.execute(
            select(
                AnalyticsEvent.event_name,
                AnalyticsEvent.platform,
                AnalyticsEvent.outcome,
                func.count(AnalyticsEvent.id),
            )
            .where(AnalyticsEvent.received_at >= now - timedelta(days=days))
            .group_by(
                AnalyticsEvent.event_name,
                AnalyticsEvent.platform,
                AnalyticsEvent.outcome,
            )
            .having(func.count(AnalyticsEvent.id) >= 5)
            .order_by(AnalyticsEvent.event_name, AnalyticsEvent.platform)
        )
    ).all()
    return AnalyticsSummary(
        days=days,
        groups=[
            AnalyticsAggregate(
                name=name,
                platform=platform,
                outcome=outcome,
                count=count,
            )
            for name, platform, outcome, count in rows
        ],
        generated_at=now,
    )
