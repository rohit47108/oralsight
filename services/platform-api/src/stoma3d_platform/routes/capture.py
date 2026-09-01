"""Owner-scoped device, scan, capture-set, asset, and capture-view routes."""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import Actor, get_current_actor, get_session
from ..errors import ServiceError
from ..idempotency import (
    commit_idempotent,
    find_replay,
    request_sha256,
    validate_idempotency_key,
)
from ..models import (
    CaptureAngle,
    CaptureAsset,
    CaptureProtocol,
    CaptureSet,
    CaptureStatus,
    ConsentRecord,
    CaptureView,
    Device,
    MediaKind,
    ScanSession,
    ScanStatus,
    User,
    UserStatus,
    new_id,
    utc_now,
)
from ..product_consent import DOCUMENT_ID, DOCUMENT_SHA256, DOCUMENT_VERSION
from ..product_schemas import (
    CaptureAssetInput,
    CaptureAssetResponse,
    AssetFinalizeResponse,
    AssetTransferIntentResponse,
    CaptureSetCreate,
    CaptureSetResponse,
    CaptureViewCreate,
    CaptureViewResponse,
    DeviceCreate,
    DeviceList,
    DeviceResponse,
    ScanSessionCreate,
    ScanSessionList,
    ScanSessionResponse,
    CaptureSetList,
)
from ..object_storage import (
    LocalObjectStorage,
    StorageError,
    StorageIntegrityError,
    StorageNotFound,
    TransferTokenCodec,
)

router = APIRouter(prefix="/v2", tags=["capture"])


async def _owned(session: AsyncSession, model, resource_id: str, user_id: str):
    value = await session.get(model, resource_id)
    if value is None or value.user_id != user_id or getattr(value, "deleted_at", None):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    return value


def _device_response(value: Device) -> DeviceResponse:
    return DeviceResponse(
        device_id=value.id,
        platform=value.platform,
        display_name=value.display_name,
        created_at=value.created_at,
        revoked_at=value.revoked_at,
    )


def _scan_response(value: ScanSession) -> ScanSessionResponse:
    return ScanSessionResponse(
        scan_session_id=value.id,
        consent_record_id=value.consent_record_id,
        protocol=value.protocol,
        status=value.status,
        created_at=value.created_at,
        updated_at=value.updated_at,
        completed_at=value.completed_at,
    )


def _asset_response(value: CaptureAsset) -> CaptureAssetResponse:
    if value.width_px is None or value.height_px is None:
        raise ServiceError(
            500, "invalid_asset_state", "The asset record is incomplete."
        )
    return CaptureAssetResponse(
        asset_id=value.id,
        media_kind=value.media_kind,
        mime_type=value.media_type,
        byte_size=value.byte_size,
        sha256=value.content_sha256,
        width_px=value.width_px,
        height_px=value.height_px,
        duration_ms=value.duration_ms,
        input_origin=value.input_origin,
        encrypted=True,
        created_at=value.created_at,
        retention_expires_at=value.retention_expires_at,
        upload_status=value.status,
    )


async def _view_response(
    session: AsyncSession, value: CaptureView
) -> CaptureViewResponse:
    asset = await session.get(CaptureAsset, value.asset_id)
    if asset is None:
        raise ServiceError(
            500, "invalid_capture_state", "The capture asset is missing."
        )
    return CaptureViewResponse(
        capture_view_id=value.id,
        capture_set_id=value.capture_set_id,
        region=value.region,
        anatomical_site=value.anatomical_site,
        angle=value.angle,
        asset=_asset_response(asset),
        source_video_asset_id=value.source_video_asset_id,
        quality_accepted=value.quality_accepted,
        quality_reasons=value.quality_reasons,
        ordinal=value.ordinal,
        captured_at=value.captured_at,
    )


async def capture_set_response(
    session: AsyncSession, value: CaptureSet
) -> CaptureSetResponse:
    views = list(
        await session.scalars(
            select(CaptureView)
            .where(
                CaptureView.capture_set_id == value.id,
                CaptureView.deleted_at.is_(None),
            )
            .order_by(CaptureView.ordinal)
        )
    )
    return CaptureSetResponse(
        capture_set_id=value.id,
        scan_session_id=value.scan_session_id,
        region=value.region,
        protocol=value.protocol,
        primary_view_id=value.primary_view_id,
        views=[await _view_response(session, view) for view in views],
        complete=value.complete,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _new_asset(
    *,
    body: CaptureAssetInput,
    actor: Actor,
    capture_set: CaptureSet,
    angle: CaptureAngle,
    ordinal: int,
    pending_upload_lifetime_seconds: int,
) -> CaptureAsset:
    now = utc_now()
    if body.retention_expires_at is not None and body.retention_expires_at <= now:
        raise ServiceError(
            422,
            "invalid_retention_expiry",
            "Asset retention expiry must be in the future.",
        )
    asset_id = new_id()
    return CaptureAsset(
        id=asset_id,
        user_id=actor.user_id,
        scan_session_id=capture_set.scan_session_id,
        region=capture_set.region.value,
        capture_angle=angle.value,
        sequence_number=ordinal,
        media_kind=body.media_kind.value,
        media_type=body.mime_type,
        object_key=f"users/{actor.user_id}/captures/{asset_id}",
        content_sha256=body.sha256,
        byte_size=body.byte_size,
        encryption_key_version="kms-pending-v1",
        status=CaptureStatus.PENDING,
        width_px=body.width_px,
        height_px=body.height_px,
        duration_ms=body.duration_ms,
        input_origin=body.input_origin,
        encrypted=True,
        retention_expires_at=body.retention_expires_at,
        upload_expires_at=now + timedelta(seconds=pending_upload_lifetime_seconds),
    )


@router.post(
    "/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED
)
async def create_device(
    body: DeviceCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DeviceResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.devices.create"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=DeviceResponse,
    )
    if replay:
        return replay
    existing = await session.scalar(
        select(Device).where(
            Device.user_id == actor.user_id,
            Device.installation_id == body.installation_id,
        )
    )
    if existing:
        existing.last_seen_at = utc_now()
        if body.display_name is not None:
            existing.display_name = body.display_name
        if body.public_key is not None:
            existing.public_key = body.public_key
        response = _device_response(existing)
        return await commit_idempotent(
            session,
            user_id=actor.user_id,
            scope=scope,
            key=key,
            digest=digest,
            response=response,
            response_status=201,
        )
    value = Device(
        user_id=actor.user_id,
        installation_id=body.installation_id,
        platform=body.platform,
        display_name=body.display_name,
        public_key=body.public_key,
        last_seen_at=utc_now(),
    )
    session.add(value)
    await session.flush()
    response = _device_response(value)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/devices", response_model=DeviceList)
async def list_devices(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeviceList:
    rows = list(
        await session.scalars(
            select(Device)
            .where(Device.user_id == actor.user_id, Device.revoked_at.is_(None))
            .order_by(Device.created_at, Device.id)
        )
    )
    return DeviceList(items=[_device_response(value) for value in rows])


@router.post(
    "/scan-sessions",
    response_model=ScanSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scan_session(
    body: ScanSessionCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ScanSessionResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.scan_sessions.create"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=ScanSessionResponse,
    )
    if replay:
        return replay
    if body.device_id:
        await _owned(session, Device, body.device_id, actor.user_id)
    consent = await _owned(
        session, ConsentRecord, body.consent_record_id, actor.user_id
    )
    if (
        not consent.accepted
        or consent.revoked_at is not None
        or consent.document_id != DOCUMENT_ID
        or consent.document_version != DOCUMENT_VERSION
        or consent.document_sha256 != DOCUMENT_SHA256
    ):
        raise ServiceError(
            409,
            "active_product_consent_required",
            "Accept the current product consent before starting a cloud scan.",
        )
    value = ScanSession(
        user_id=actor.user_id,
        device_id=body.device_id,
        consent_record_id=consent.id,
        protocol=body.protocol.value,
        status=ScanStatus.DRAFT,
    )
    session.add(value)
    await session.flush()
    response = _scan_response(value)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/scan-sessions", response_model=ScanSessionList)
async def list_scan_sessions(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    before: Annotated[datetime | None, Query()] = None,
) -> ScanSessionList:
    query = select(ScanSession).where(
        ScanSession.user_id == actor.user_id,
        ScanSession.deleted_at.is_(None),
    )
    if before is not None:
        query = query.where(ScanSession.created_at < before)
    rows = list(
        await session.scalars(
            query.order_by(ScanSession.created_at.desc(), ScanSession.id.desc()).limit(
                limit + 1
            )
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    cursor = (
        rows[-1].created_at.astimezone(UTC).isoformat() if has_more and rows else None
    )
    return ScanSessionList(
        items=[_scan_response(value) for value in rows], next_cursor=cursor
    )


@router.get("/scan-sessions/{scan_session_id}", response_model=ScanSessionResponse)
async def get_scan_session(
    scan_session_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScanSessionResponse:
    value = await _owned(session, ScanSession, scan_session_id, actor.user_id)
    return _scan_response(value)


@router.get(
    "/scan-sessions/{scan_session_id}/capture-sets",
    response_model=CaptureSetList,
)
async def list_capture_sets(
    scan_session_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaptureSetList:
    await _owned(session, ScanSession, scan_session_id, actor.user_id)
    rows = list(
        await session.scalars(
            select(CaptureSet)
            .where(
                CaptureSet.user_id == actor.user_id,
                CaptureSet.scan_session_id == scan_session_id,
                CaptureSet.deleted_at.is_(None),
            )
            .order_by(CaptureSet.created_at, CaptureSet.id)
        )
    )
    return CaptureSetList(
        items=[await capture_set_response(session, value) for value in rows]
    )


@router.post(
    "/scan-sessions/{scan_session_id}/capture-sets",
    response_model=CaptureSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_capture_set(
    scan_session_id: str,
    body: CaptureSetCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CaptureSetResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = f"v2.scan.{scan_session_id}.capture_sets"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=CaptureSetResponse,
    )
    if replay:
        return replay
    scan = await _owned(session, ScanSession, scan_session_id, actor.user_id)
    if scan.protocol != body.protocol.value:
        raise ServiceError(
            422,
            "capture_protocol_mismatch",
            "The capture set protocol must match its scan session.",
        )
    value = CaptureSet(
        user_id=actor.user_id,
        scan_session_id=scan.id,
        region=body.region,
        protocol=body.protocol,
    )
    scan.status = ScanStatus.CAPTURING
    session.add(value)
    await session.flush()
    response = await capture_set_response(session, value)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/capture-sets/{capture_set_id}", response_model=CaptureSetResponse)
async def get_capture_set(
    capture_set_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaptureSetResponse:
    value = await _owned(session, CaptureSet, capture_set_id, actor.user_id)
    return await capture_set_response(session, value)


@router.post(
    "/capture-sets/{capture_set_id}/assets",
    response_model=CaptureAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_capture_asset(
    capture_set_id: str,
    body: CaptureAssetInput,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CaptureAssetResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = f"v2.capture_set.{capture_set_id}.assets"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=CaptureAssetResponse,
    )
    if replay:
        return replay
    capture_set = await _owned(session, CaptureSet, capture_set_id, actor.user_id)
    if body.media_kind is not MediaKind.VIDEO:
        raise ServiceError(
            422,
            "standalone_asset_not_video",
            "Standalone capture assets are reserved for temporary sweep video.",
        )
    asset = _new_asset(
        body=body,
        actor=actor,
        capture_set=capture_set,
        angle=CaptureAngle.PRIMARY,
        ordinal=0,
        pending_upload_lifetime_seconds=request.app.state.settings.pending_upload_lifetime_seconds,
    )
    session.add(asset)
    await session.flush()
    response = _asset_response(asset)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/capture-assets/{asset_id}", response_model=CaptureAssetResponse)
async def get_capture_asset(
    asset_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaptureAssetResponse:
    asset = await _owned(session, CaptureAsset, asset_id, actor.user_id)
    return _asset_response(asset)


def _storage_service_error(exc: StorageError) -> ServiceError:
    if isinstance(exc, StorageNotFound):
        return ServiceError(409, "asset_upload_missing", "The asset upload is missing.")
    if isinstance(exc, StorageIntegrityError):
        return ServiceError(
            422, "asset_integrity_failed", "The uploaded asset failed verification."
        )
    return ServiceError(503, "object_storage_unavailable", "Storage is unavailable.")


def _upload_deadline_passed(asset: CaptureAsset) -> bool:
    deadline = asset.upload_expires_at
    if deadline is None:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    return deadline <= utc_now()


def _upload_token_codec(request: Request) -> TransferTokenCodec:
    secret = request.app.state.settings.share_secret_derivation_key.get_secret_value().encode()
    return TransferTokenCodec(secret)


def _upload_capability_error() -> ServiceError:
    return ServiceError(
        403,
        "invalid_upload_capability",
        "The upload capability is invalid.",
    )


def _required_capability_str(payload: dict[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise _upload_capability_error()
    return value


def _required_capability_size(payload: dict[str, object]) -> int:
    value = payload.get("size")
    if type(value) is not int or value <= 0:
        raise _upload_capability_error()
    return value


def _capability_expiry(asset: CaptureAsset, lifetime_seconds: int) -> int:
    now_epoch = int(time.time())
    expiry = now_epoch + lifetime_seconds
    deadline = asset.upload_expires_at
    if deadline is not None:
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        expiry = min(expiry, int(deadline.timestamp()))
    if expiry < now_epoch:
        raise ServiceError(410, "asset_upload_expired", "This upload has expired.")
    return expiry


async def _cleanup_ambiguous_upload(request: Request, object_key: str) -> None:
    try:
        await request.app.state.object_storage.delete(object_key)
    except StorageError:
        pass


async def _reject_expired_upload(
    request: Request, session: AsyncSession, asset: CaptureAsset
) -> None:
    if not _upload_deadline_passed(asset):
        return
    try:
        await request.app.state.object_storage.delete(asset.object_key)
    except StorageError as exc:
        raise _storage_service_error(exc) from exc
    asset.status = CaptureStatus.DELETED
    asset.deleted_at = utc_now()
    await session.commit()
    raise ServiceError(410, "asset_upload_expired", "This upload has expired.")


@router.post(
    "/capture-assets/{asset_id}/upload-intent",
    response_model=AssetTransferIntentResponse,
)
async def create_asset_upload_intent(
    asset_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetTransferIntentResponse:
    asset = await _owned(session, CaptureAsset, asset_id, actor.user_id)
    await _reject_expired_upload(request, session, asset)
    if asset.status is not CaptureStatus.PENDING:
        raise ServiceError(
            409, "asset_upload_closed", "This asset no longer accepts uploads."
        )
    if asset.byte_size > request.app.state.settings.capture_asset_max_bytes:
        raise ServiceError(413, "asset_too_large", "The capture asset is too large.")
    capability_expiry_epoch = _capability_expiry(
        asset, request.app.state.settings.object_transfer_lifetime_seconds
    )
    token = _upload_token_codec(request).issue(
        {
            "op": "put",
            "user": asset.user_id,
            "asset": asset.id,
            "key": asset.object_key,
            "type": asset.media_type,
            "sha": asset.content_sha256,
            "size": asset.byte_size,
            "exp": capability_expiry_epoch,
        }
    )
    capability_expires_at = datetime.fromtimestamp(capability_expiry_epoch, UTC)
    current_capability_expiry = asset.upload_capability_expires_at
    if (
        current_capability_expiry is None
        or (
            current_capability_expiry.replace(tzinfo=UTC)
            if current_capability_expiry.tzinfo is None
            else current_capability_expiry.astimezone(UTC)
        )
        < capability_expires_at
    ):
        asset.upload_capability_expires_at = capability_expires_at
    await session.commit()
    return AssetTransferIntentResponse(
        asset_id=asset.id,
        method="PUT",
        url=(
            f"{request.app.state.settings.object_storage_public_base_url.rstrip('/')}"
            f"/v2/storage/uploads/{quote(token, safe='')}"
        ),
        headers={
            "Content-Type": asset.media_type,
            "Content-Length": str(asset.byte_size),
        },
        expires_at=capability_expires_at,
    )


@router.post(
    "/capture-assets/{asset_id}/finalize",
    response_model=AssetFinalizeResponse,
)
async def finalize_asset_upload(
    asset_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetFinalizeResponse:
    asset = await _owned(session, CaptureAsset, asset_id, actor.user_id)
    await _reject_expired_upload(request, session, asset)
    if asset.status is not CaptureStatus.PENDING:
        raise ServiceError(
            409, "asset_upload_closed", "This asset no longer accepts uploads."
        )
    try:
        stored = await request.app.state.object_storage.stat(asset.object_key)
    except StorageError as exc:
        raise _storage_service_error(exc) from exc
    if (
        stored.size_bytes != asset.byte_size
        or stored.sha256 != asset.content_sha256
        or stored.media_type != asset.media_type
    ):
        try:
            await request.app.state.object_storage.delete(asset.object_key)
        except StorageError:
            pass
        raise ServiceError(
            422, "asset_integrity_failed", "The uploaded asset failed verification."
        )
    asset.status = CaptureStatus.AVAILABLE
    asset.upload_expires_at = None
    asset.encryption_key_version = "managed-object-storage-v1"
    await session.commit()
    return AssetFinalizeResponse(asset=_asset_response(asset))


@router.post(
    "/capture-assets/{asset_id}/download-intent",
    response_model=AssetTransferIntentResponse,
)
async def create_asset_download_intent(
    asset_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetTransferIntentResponse:
    asset = await _owned(session, CaptureAsset, asset_id, actor.user_id)
    if asset.status is not CaptureStatus.AVAILABLE:
        raise ServiceError(409, "asset_not_available", "The asset is not available.")
    try:
        intent = await request.app.state.object_storage.presign_download(
            asset.object_key,
            lifetime_seconds=request.app.state.settings.object_transfer_lifetime_seconds,
        )
    except StorageError as exc:
        raise _storage_service_error(exc) from exc
    return AssetTransferIntentResponse(
        asset_id=asset.id,
        method="GET",
        url=intent.url,
        headers=intent.headers,
        expires_at=datetime.fromtimestamp(intent.expires_at_epoch, UTC),
    )


@router.get("/capture-assets/{asset_id}/content")
async def get_capture_asset_content(
    asset_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    asset = await _owned(session, CaptureAsset, asset_id, actor.user_id)
    if asset.status is not CaptureStatus.AVAILABLE:
        raise ServiceError(409, "asset_not_available", "The asset is not available.")
    try:
        data = await request.app.state.object_storage.get_bytes(
            asset.object_key, max_bytes=asset.byte_size
        )
    except StorageError as exc:
        raise _storage_service_error(exc) from exc
    if (
        len(data) != asset.byte_size
        or hashlib.sha256(data).hexdigest() != asset.content_sha256
    ):
        raise ServiceError(
            500, "stored_asset_corrupt", "The stored asset failed verification."
        )
    return Response(
        content=data,
        media_type=asset.media_type,
        headers={"Content-Disposition": "inline", "Cache-Control": "no-store"},
    )


@router.put("/storage/uploads/{token}", include_in_schema=False)
async def platform_capability_upload(
    token: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    try:
        payload = _upload_token_codec(request).verify(token, operation="put")
    except StorageError as exc:
        raise _upload_capability_error() from exc

    user_id = _required_capability_str(payload, "user")
    asset_id = _required_capability_str(payload, "asset")
    object_key = _required_capability_str(payload, "key")
    media_type = _required_capability_str(payload, "type")
    content_sha256 = _required_capability_str(payload, "sha")
    expected_size = _required_capability_size(payload)
    if expected_size > request.app.state.settings.capture_asset_max_bytes:
        raise ServiceError(413, "asset_too_large", "The capture asset is too large.")

    content_length = request.headers.get("content-length")
    try:
        declared_length = int(content_length) if content_length is not None else None
    except ValueError as exc:
        raise ServiceError(
            400, "invalid_content_length", "The upload length is invalid."
        ) from exc
    if declared_length != expected_size:
        raise ServiceError(
            400, "invalid_content_length", "The upload length is invalid."
        )
    submitted_media_type = request.headers.get("content-type", "").split(";", 1)[0]
    if submitted_media_type.strip() != media_type:
        raise ServiceError(
            422, "asset_integrity_failed", "The uploaded asset failed verification."
        )

    async with request.app.state.user_operation_locks.hold(user_id):
        user = await session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise _upload_capability_error()
        if user.status is UserStatus.DELETION_PENDING:
            raise ServiceError(
                403,
                "account_deletion_pending",
                "This account is pending deletion.",
            )
        if user.status is not UserStatus.ACTIVE:
            raise ServiceError(403, "account_not_active", "This account is not active.")

        asset = await session.scalar(
            select(CaptureAsset)
            .where(CaptureAsset.id == asset_id, CaptureAsset.user_id == user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if asset is None:
            raise _upload_capability_error()
        if _upload_deadline_passed(asset):
            raise ServiceError(410, "asset_upload_expired", "This upload has expired.")
        if asset.deleted_at is not None or asset.status is not CaptureStatus.PENDING:
            raise ServiceError(
                409, "asset_upload_closed", "This asset no longer accepts uploads."
            )
        if (
            asset.object_key != object_key
            or asset.media_type != media_type
            or asset.byte_size != expected_size
            or not hmac.compare_digest(asset.content_sha256, content_sha256)
        ):
            raise _upload_capability_error()

        body = bytearray()
        digest = hashlib.sha256()
        async for chunk in request.stream():
            body.extend(chunk)
            digest.update(chunk)
            if len(body) > expected_size:
                body.clear()
                raise ServiceError(
                    422,
                    "asset_integrity_failed",
                    "The uploaded asset failed verification.",
                )
        if len(body) != expected_size or not hmac.compare_digest(
            digest.hexdigest(), content_sha256
        ):
            body.clear()
            raise ServiceError(
                422,
                "asset_integrity_failed",
                "The uploaded asset failed verification.",
            )
        data = bytes(body)
        body.clear()
        try:
            stored = await request.app.state.object_storage.put_bytes(
                object_key,
                data,
                media_type=media_type,
                sha256=content_sha256,
            )
            data = b""
            if (
                stored.size_bytes != expected_size
                or stored.media_type != media_type
                or not hmac.compare_digest(stored.sha256, content_sha256)
            ):
                raise StorageError("object_write_unverified")
        except StorageError as exc:
            data = b""
            await _cleanup_ambiguous_upload(request, object_key)
            raise ServiceError(
                503, "object_storage_unavailable", "Storage is unavailable."
            ) from exc
        except Exception as exc:
            data = b""
            await _cleanup_ambiguous_upload(request, object_key)
            raise ServiceError(
                503, "object_storage_unavailable", "Storage is unavailable."
            ) from exc
    return Response(status_code=204)


@router.get("/storage/downloads/{token}", include_in_schema=False)
async def local_presigned_download(token: str, request: Request) -> Response:
    storage = request.app.state.object_storage
    if not isinstance(storage, LocalObjectStorage):
        raise ServiceError(404, "not_found", "Endpoint not found.")
    try:
        payload = storage.tokens.verify(token, operation="get")
        stored = await storage.stat(str(payload["key"]))
        data = await storage.get_bytes(
            str(payload["key"]),
            max_bytes=request.app.state.settings.generated_asset_max_bytes,
        )
    except StorageError as exc:
        raise _storage_service_error(exc) from exc
    return Response(
        content=data,
        media_type=stored.media_type,
        headers={"Content-Disposition": "inline", "Cache-Control": "no-store"},
    )


@router.post(
    "/capture-sets/{capture_set_id}/views",
    response_model=CaptureSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_capture_view(
    capture_set_id: str,
    body: CaptureViewCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CaptureSetResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = f"v2.capture_set.{capture_set_id}.views"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=CaptureSetResponse,
    )
    if replay:
        return replay
    capture_set = await _owned(session, CaptureSet, capture_set_id, actor.user_id)
    views = list(
        await session.scalars(
            select(CaptureView).where(
                CaptureView.capture_set_id == capture_set.id,
                CaptureView.deleted_at.is_(None),
            )
        )
    )
    if len(views) >= 12:
        raise ServiceError(
            409, "capture_set_full", "This capture set already has 12 views."
        )
    if capture_set.protocol is CaptureProtocol.STANDARD and views:
        raise ServiceError(
            409,
            "standard_capture_already_exists",
            "A standard region retains one accepted image.",
        )
    if any(view.ordinal == body.ordinal for view in views):
        raise ServiceError(
            409, "capture_ordinal_exists", "This capture ordinal is already used."
        )

    source_asset = None
    if body.source_video_asset_id:
        source_asset = await _owned(
            session, CaptureAsset, body.source_video_asset_id, actor.user_id
        )
        if source_asset.media_kind != MediaKind.VIDEO.value:
            raise ServiceError(
                422,
                "invalid_source_video",
                "The source asset must be a video from this account.",
            )
        if source_asset.scan_session_id != capture_set.scan_session_id:
            raise ServiceError(
                404, "resource_not_found", "The requested resource was not found."
            )

    existing_origins: set[str] = set()
    for view in views:
        existing_asset = await session.get(CaptureAsset, view.asset_id)
        if existing_asset:
            existing_origins.add(existing_asset.input_origin.value)
    if existing_origins and body.asset.input_origin.value not in existing_origins:
        raise ServiceError(
            422,
            "mixed_input_origin",
            "Live and bundled captures cannot be mixed in one capture set.",
        )

    asset = _new_asset(
        body=body.asset,
        actor=actor,
        capture_set=capture_set,
        angle=body.angle,
        ordinal=body.ordinal,
        pending_upload_lifetime_seconds=request.app.state.settings.pending_upload_lifetime_seconds,
    )
    view = CaptureView(
        user_id=actor.user_id,
        capture_set_id=capture_set.id,
        asset_id=asset.id,
        region=capture_set.region,
        anatomical_site=body.anatomical_site.value if body.anatomical_site else None,
        angle=body.angle,
        source_video_asset_id=source_asset.id if source_asset else None,
        quality_accepted=True,
        quality_reasons=body.quality_reasons,
        ordinal=body.ordinal,
        captured_at=body.captured_at,
    )
    session.add_all([asset, view])
    await session.flush()
    if capture_set.primary_view_id is None or body.make_primary:
        capture_set.primary_view_id = view.id
    accepted_angles = {item.angle for item in [*views, view] if item.quality_accepted}
    if capture_set.protocol is CaptureProtocol.STANDARD:
        capture_set.complete = capture_set.primary_view_id is not None
    else:
        capture_set.complete = capture_set.primary_view_id is not None and {
            CaptureAngle.STRAIGHT,
            CaptureAngle.LEFT_OBLIQUE,
            CaptureAngle.RIGHT_OBLIQUE,
        }.issubset(accepted_angles)
    capture_set.version += 1
    response = await capture_set_response(session, capture_set)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )
