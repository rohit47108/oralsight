"""Patient-issued fragment-secret shares and limited share-viewer access."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..collaboration_common import (
    SHARE_RECORD_RETENTION,
    SHARE_TOKEN_LIFETIME,
    append_access_event,
    as_utc,
    derive_urlsafe_secret,
    require_owned_resource,
    resource_view_response,
    secret_hash,
    secret_matches,
    share_resources,
    share_response,
)
from ..artifact_files import report_filename
from ..collaboration_schemas import (
    ResourceRef,
    ResourceViewResponse,
    ShareCreate,
    ShareCreateResponse,
    ShareExchangeCreate,
    ShareExchangeResponse,
    ShareLinkResponse,
    ShareList,
    ShareViewerScopeResponse,
)
from ..dependencies import Actor, get_current_actor, get_session
from ..errors import ServiceError
from ..idempotency import (
    commit_idempotent,
    find_replay,
    request_sha256,
    validate_idempotency_key,
)
from ..models import (
    AccessActorType,
    AccessEventType,
    ShareExchangeToken,
    ShareLink,
    ShareLinkResource,
    ShareLinkStatus,
    ShareResourceType,
    ReportArtifact,
    new_id,
    utc_now,
)
from ..object_storage import StorageError, StorageNotFound

router = APIRouter(prefix="/v2", tags=["patient sharing"])


def _share_unavailable() -> ServiceError:
    return ServiceError(404, "share_unavailable", "This share is not available.")


async def _owned_share(
    session: AsyncSession, share_id: str, patient_user_id: str
) -> ShareLink:
    value = await session.get(ShareLink, share_id)
    if value is None or value.patient_user_id != patient_user_id:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    return value


async def _create_replay(
    session: AsyncSession,
    *,
    request: Request,
    patient_user_id: str,
    key: str,
    digest: str,
) -> ShareCreateResponse | None:
    existing = await session.scalar(
        select(ShareLink).where(
            ShareLink.patient_user_id == patient_user_id,
            ShareLink.create_idempotency_key == key,
        )
    )
    if existing is None:
        return None
    if existing.request_sha256 != digest:
        raise ServiceError(
            409,
            "idempotency_conflict",
            "This idempotency key was already used for a different request.",
        )
    fragment_secret = derive_urlsafe_secret(
        request.app.state.settings, "share-link", existing.id
    )
    if not secret_matches(fragment_secret, existing.secret_sha256):
        raise ServiceError(
            500, "share_key_unavailable", "The share cannot be reconstructed."
        )
    return ShareCreateResponse(
        share=await share_response(session, existing),
        fragment_secret=fragment_secret,
    )


@router.post(
    "/shares",
    response_model=ShareCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_share(
    body: ShareCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ShareCreateResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    replay = await _create_replay(
        session,
        request=request,
        patient_user_id=actor.user_id,
        key=key,
        digest=digest,
    )
    if replay:
        return replay
    for resource in body.resources:
        await require_owned_resource(
            session, patient_user_id=actor.user_id, resource=resource
        )
    now = utc_now()
    expires_at = now + timedelta(seconds=body.expires_in_seconds)
    share_id = new_id()
    fragment_secret = derive_urlsafe_secret(
        request.app.state.settings, "share-link", share_id
    )
    value = ShareLink(
        id=share_id,
        patient_user_id=actor.user_id,
        secret_sha256=secret_hash(fragment_secret),
        create_idempotency_key=key,
        request_sha256=digest,
        status=ShareLinkStatus.ACTIVE,
        expires_at=expires_at,
        max_exchanges=body.max_exchanges,
        exchange_count=0,
        created_at=now,
        retention_expires_at=expires_at + SHARE_RECORD_RETENTION,
    )
    session.add(value)
    session.add_all(
        [
            ShareLinkResource(
                share_id=share_id,
                resource_type=resource.resource_type,
                resource_id=resource.resource_id,
            )
            for resource in body.resources
        ]
    )
    await session.flush()
    append_access_event(
        session,
        patient_user_id=actor.user_id,
        actor_user_id=actor.user_id,
        actor_type=AccessActorType.PATIENT,
        event_type=AccessEventType.SHARE_CREATED,
        resource_type="share_link",
        resource_id=value.id,
        share_id=value.id,
        request_id=request.state.request_id,
        details={
            "resourceCount": len(body.resources),
            "maxExchanges": body.max_exchanges,
        },
    )
    response = ShareCreateResponse(
        share=await share_response(session, value), fragment_secret=fragment_secret
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        replay = await _create_replay(
            session,
            request=request,
            patient_user_id=actor.user_id,
            key=key,
            digest=digest,
        )
        if replay:
            return replay
        raise ServiceError(
            409, "request_conflict", "The share conflicted with another request."
        ) from exc
    return response


@router.get("/shares", response_model=ShareList)
async def list_shares(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ShareList:
    rows = list(
        await session.scalars(
            select(ShareLink)
            .where(ShareLink.patient_user_id == actor.user_id)
            .order_by(ShareLink.created_at.desc(), ShareLink.id.desc())
        )
    )
    return ShareList(items=[await share_response(session, value) for value in rows])


@router.get("/shares/{share_id}", response_model=ShareLinkResponse)
async def get_share(
    share_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ShareLinkResponse:
    return await share_response(
        session, await _owned_share(session, share_id, actor.user_id)
    )


@router.post("/shares/{share_id}/revoke", response_model=ShareLinkResponse)
async def revoke_share(
    share_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ShareLinkResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = secret_hash(f"revoke:{share_id}")
    scope = f"v2.share.{share_id}.revoke"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=ShareLinkResponse,
    )
    if replay:
        return replay
    value = await _owned_share(session, share_id, actor.user_id)
    if value.revoked_at is None:
        now = utc_now()
        value.status = ShareLinkStatus.REVOKED
        value.revoked_at = now
        tokens = list(
            await session.scalars(
                select(ShareExchangeToken).where(
                    ShareExchangeToken.share_id == value.id,
                    ShareExchangeToken.revoked_at.is_(None),
                )
            )
        )
        for token in tokens:
            token.revoked_at = now
        append_access_event(
            session,
            patient_user_id=actor.user_id,
            actor_user_id=actor.user_id,
            actor_type=AccessActorType.PATIENT,
            event_type=AccessEventType.SHARE_REVOKED,
            resource_type="share_link",
            resource_id=value.id,
            share_id=value.id,
            request_id=request.state.request_id,
        )
    response = await share_response(session, value)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=200,
    )


async def _exchange_replay(
    session: AsyncSession,
    *,
    request: Request,
    share: ShareLink,
    key: str,
    digest: str,
) -> ShareExchangeResponse | None:
    value = await session.scalar(
        select(ShareExchangeToken).where(
            ShareExchangeToken.share_id == share.id,
            ShareExchangeToken.exchange_idempotency_key == key,
        )
    )
    if value is None:
        return None
    if value.request_sha256 != digest:
        raise ServiceError(
            409,
            "idempotency_conflict",
            "This idempotency key was already used for a different request.",
        )
    now = utc_now()
    if value.revoked_at is not None or as_utc(value.expires_at) <= now:
        raise ServiceError(410, "exchange_expired", "This exchange has expired.")
    raw_token = derive_urlsafe_secret(
        request.app.state.settings, "share-exchange", value.id
    )
    if not secret_matches(raw_token, value.token_sha256):
        raise ServiceError(
            500, "share_key_unavailable", "The exchange cannot be reconstructed."
        )
    return ShareExchangeResponse(
        exchange_token=raw_token,
        expires_at=value.expires_at,
        max_uses=value.max_uses,
    )


@router.post("/share-exchanges", response_model=ShareExchangeResponse)
async def exchange_share_secret(
    body: ShareExchangeCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ShareExchangeResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    share = await session.scalar(
        select(ShareLink).where(ShareLink.id == body.share_id).with_for_update()
    )
    if share is None or not secret_matches(body.secret, share.secret_sha256):
        raise _share_unavailable()
    replay = await _exchange_replay(
        session,
        request=request,
        share=share,
        key=key,
        digest=digest,
    )
    if replay:
        return replay
    now = utc_now()
    if (
        share.status is not ShareLinkStatus.ACTIVE
        or share.revoked_at is not None
        or as_utc(share.expires_at) <= now
        or share.exchange_count >= share.max_exchanges
    ):
        raise ServiceError(410, "share_expired", "This share is no longer active.")
    resources = await share_resources(session, share.id)
    token_id = new_id()
    raw_token = derive_urlsafe_secret(
        request.app.state.settings, "share-exchange", token_id
    )
    token_expires_at = min(now + SHARE_TOKEN_LIFETIME, as_utc(share.expires_at))
    max_uses = min(64, max(4, len(resources) * 4))
    token = ShareExchangeToken(
        id=token_id,
        share_id=share.id,
        token_sha256=secret_hash(raw_token),
        exchange_idempotency_key=key,
        request_sha256=digest,
        expires_at=token_expires_at,
        max_uses=max_uses,
        use_count=0,
        created_at=now,
        retention_expires_at=share.expires_at + SHARE_RECORD_RETENTION,
    )
    session.add(token)
    share.exchange_count += 1
    append_access_event(
        session,
        patient_user_id=share.patient_user_id,
        actor_user_id=None,
        actor_type=AccessActorType.SHARE_VIEWER,
        event_type=AccessEventType.SHARE_EXCHANGED,
        resource_type="share_link",
        resource_id=share.id,
        share_id=share.id,
        request_id=request.state.request_id,
        details={"exchangeNumber": share.exchange_count},
    )
    response = ShareExchangeResponse(
        exchange_token=raw_token,
        expires_at=token_expires_at,
        max_uses=max_uses,
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        share = await session.get(ShareLink, body.share_id)
        if share is not None:
            replay = await _exchange_replay(
                session,
                request=request,
                share=share,
                key=key,
                digest=digest,
            )
            if replay:
                return replay
        raise ServiceError(
            409, "request_conflict", "The exchange conflicted with another request."
        ) from exc
    return response


@dataclass(frozen=True, slots=True)
class ShareCredential:
    token_id: str
    share_id: str


async def get_share_credential(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ShareCredential:
    if not authorization:
        raise ServiceError(
            401,
            "share_token_required",
            "A valid share token is required.",
            headers={"WWW-Authenticate": "Share"},
        )
    scheme, separator, raw_token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "share" or not raw_token.strip():
        raise ServiceError(
            401,
            "invalid_share_token",
            "The share token could not be verified.",
            headers={"WWW-Authenticate": "Share"},
        )
    value = await session.scalar(
        select(ShareExchangeToken).where(
            ShareExchangeToken.token_sha256 == secret_hash(raw_token.strip())
        )
    )
    if value is None:
        raise ServiceError(
            401,
            "invalid_share_token",
            "The share token could not be verified.",
            headers={"WWW-Authenticate": "Share"},
        )
    return ShareCredential(token_id=value.id, share_id=value.share_id)


async def _consume_token(
    session: AsyncSession, credential: ShareCredential
) -> tuple[ShareExchangeToken, ShareLink]:
    token = await session.scalar(
        select(ShareExchangeToken)
        .where(ShareExchangeToken.id == credential.token_id)
        .with_for_update()
    )
    share = await session.get(ShareLink, credential.share_id)
    now = utc_now()
    if (
        token is None
        or share is None
        or token.revoked_at is not None
        or share.revoked_at is not None
        or token.use_count >= token.max_uses
        or as_utc(token.expires_at) <= now
        or as_utc(share.expires_at) <= now
        or share.status is not ShareLinkStatus.ACTIVE
    ):
        raise ServiceError(
            401,
            "invalid_share_token",
            "The share token could not be verified.",
            headers={"WWW-Authenticate": "Share"},
        )
    token.use_count += 1
    token.last_used_at = now
    return token, share


@router.get(
    "/share-viewer/resources",
    response_model=ShareViewerScopeResponse,
)
async def get_share_viewer_scope(
    request: Request,
    credential: Annotated[ShareCredential, Depends(get_share_credential)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ShareViewerScopeResponse:
    token, share = await _consume_token(session, credential)
    resources = await share_resources(session, share.id)
    append_access_event(
        session,
        patient_user_id=share.patient_user_id,
        actor_user_id=None,
        actor_type=AccessActorType.SHARE_VIEWER,
        event_type=AccessEventType.RESOURCE_VIEWED,
        resource_type="share_scope",
        resource_id=share.id,
        share_id=share.id,
        request_id=request.state.request_id,
    )
    response = ShareViewerScopeResponse(
        share_id=share.id,
        resources=resources,
        share_expires_at=share.expires_at,
        token_expires_at=token.expires_at,
        remaining_uses=token.max_uses - token.use_count,
    )
    await session.commit()
    return response


@router.get(
    "/share-viewer/resources/{resource_type}/{resource_id}",
    response_model=ResourceViewResponse,
)
async def get_share_viewer_resource(
    resource_type: str,
    resource_id: str,
    request: Request,
    credential: Annotated[ShareCredential, Depends(get_share_credential)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResourceViewResponse:
    try:
        resource = ResourceRef(resource_type=resource_type, resource_id=resource_id)
    except ValueError as exc:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        ) from exc
    token, share = await _consume_token(session, credential)
    del token
    selected = await session.scalar(
        select(ShareLinkResource.id).where(
            ShareLinkResource.share_id == share.id,
            ShareLinkResource.resource_type == resource.resource_type,
            ShareLinkResource.resource_id == resource.resource_id,
        )
    )
    if selected is None:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    response = await resource_view_response(
        session, patient_user_id=share.patient_user_id, resource=resource
    )
    append_access_event(
        session,
        patient_user_id=share.patient_user_id,
        actor_user_id=None,
        actor_type=AccessActorType.SHARE_VIEWER,
        event_type=AccessEventType.RESOURCE_VIEWED,
        resource_type=resource.resource_type.value,
        resource_id=resource.resource_id,
        share_id=share.id,
        request_id=request.state.request_id,
    )
    await session.commit()
    return response


@router.get("/share-viewer/resources/report/{report_id}/content")
async def get_share_viewer_report_content(
    report_id: str,
    request: Request,
    credential: Annotated[ShareCredential, Depends(get_share_credential)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    token, share = await _consume_token(session, credential)
    del token
    selected = await session.scalar(
        select(ShareLinkResource.id).where(
            ShareLinkResource.share_id == share.id,
            ShareLinkResource.resource_type == ShareResourceType.REPORT,
            ShareLinkResource.resource_id == report_id,
        )
    )
    if selected is None:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    report = await session.get(ReportArtifact, report_id)
    if (
        report is None
        or report.user_id != share.patient_user_id
        or report.deleted_at is not None
        or not report.object_key
    ):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    try:
        data = await request.app.state.object_storage.get_bytes(
            report.object_key, max_bytes=report.byte_size
        )
    except StorageNotFound as exc:
        raise ServiceError(
            410, "report_content_unavailable", "The report content is unavailable."
        ) from exc
    except StorageError as exc:
        raise ServiceError(
            503, "object_storage_unavailable", "Storage is unavailable."
        ) from exc
    if (
        len(data) != report.byte_size
        or hashlib.sha256(data).hexdigest() != report.content_sha256
    ):
        raise ServiceError(
            500, "stored_report_corrupt", "The stored report failed verification."
        )
    append_access_event(
        session,
        patient_user_id=share.patient_user_id,
        actor_user_id=None,
        actor_type=AccessActorType.SHARE_VIEWER,
        event_type=AccessEventType.RESOURCE_VIEWED,
        resource_type="report_content",
        resource_id=report.id,
        share_id=share.id,
        request_id=request.state.request_id,
    )
    await session.commit()
    return Response(
        content=data,
        media_type=report.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f'inline; filename="{report_filename(report.id, report.media_type)}"'
            ),
        },
    )
