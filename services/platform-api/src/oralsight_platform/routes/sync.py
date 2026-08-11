"""Encrypted cursor sync with permanent deletion tombstones."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import or_, select
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
    Device,
    EntityTombstone,
    SyncApplyStatus,
    SyncChange,
    SyncCursor,
    SyncEntityState,
    SyncOperationKind,
    utc_now,
)
from ..product_schemas import (
    SyncApplyResult,
    SyncCursorResponse,
    SyncOperationInput,
    SyncOperationOutput,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
)
from .capture import _owned

router = APIRouter(prefix="/v2/sync", tags=["sync"])


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _issue_cursor(
    session: AsyncSession, *, user_id: str, high_watermark: int
) -> SyncCursorResponse:
    now = utc_now()
    expires_at = now + timedelta(days=30)
    token = secrets.token_urlsafe(32)
    session.add(
        SyncCursor(
            user_id=user_id,
            token_sha256=_token_hash(token),
            high_watermark=high_watermark,
            issued_at=now,
            expires_at=expires_at,
        )
    )
    return SyncCursorResponse(
        cursor=token,
        high_watermark=high_watermark,
        issued_at=now,
        expires_at=expires_at,
    )


def _same_operation(stored: SyncChange, incoming: SyncOperationInput) -> bool:
    return (
        stored.operation_id == incoming.operation_id
        and stored.client_idempotency_key == incoming.idempotency_key
        and stored.device_id == incoming.device_id
        and stored.entity_type is incoming.entity_type
        and stored.entity_id == incoming.entity_id
        and stored.entity_version == incoming.version
        and stored.client_sequence == incoming.sequence
        and stored.operation is incoming.operation
        and stored.encrypted_payload == incoming.encrypted_payload
        and stored.tombstone == incoming.tombstone
    )


@router.post("/push", response_model=SyncPushResponse)
async def push_sync(
    body: SyncPushRequest,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SyncPushResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.sync.push"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=SyncPushResponse,
    )
    if replay:
        return replay

    results: list[SyncApplyResult] = []
    for incoming in body.operations:
        device = await _owned(session, Device, incoming.device_id, actor.user_id)
        if device.revoked_at is not None:
            raise ServiceError(
                403, "device_revoked", "This device is no longer active."
            )
        device.last_seen_at = utc_now()
        duplicate = await session.scalar(
            select(SyncChange).where(
                SyncChange.user_id == actor.user_id,
                or_(
                    SyncChange.operation_id == incoming.operation_id,
                    SyncChange.client_idempotency_key == incoming.idempotency_key,
                ),
            )
        )
        if duplicate:
            if not _same_operation(duplicate, incoming):
                raise ServiceError(
                    409,
                    "sync_operation_conflict",
                    "A sync operation identifier was already used for different data.",
                )
            results.append(
                SyncApplyResult(
                    operation_id=incoming.operation_id,
                    status=SyncApplyStatus.DUPLICATE,
                    server_sequence=duplicate.server_sequence,
                )
            )
            continue

        tombstone = await session.scalar(
            select(EntityTombstone).where(
                EntityTombstone.user_id == actor.user_id,
                EntityTombstone.entity_type == incoming.entity_type,
                EntityTombstone.entity_id == incoming.entity_id,
            )
        )
        apply_status = SyncApplyStatus.APPLIED
        applied = True
        if incoming.operation is SyncOperationKind.UPSERT and tombstone is not None:
            apply_status = SyncApplyStatus.TOMBSTONE_WINS
            applied = False

        state = await session.scalar(
            select(SyncEntityState).where(
                SyncEntityState.user_id == actor.user_id,
                SyncEntityState.entity_type == incoming.entity_type,
                SyncEntityState.entity_id == incoming.entity_id,
            )
        )
        if (
            incoming.operation is SyncOperationKind.UPSERT
            and tombstone is None
            and state is not None
            and incoming.version <= state.version
        ):
            apply_status = SyncApplyStatus.STALE_IGNORED
            applied = False

        change = SyncChange(
            user_id=actor.user_id,
            operation_id=incoming.operation_id,
            client_idempotency_key=incoming.idempotency_key,
            device_id=incoming.device_id,
            entity_type=incoming.entity_type,
            entity_id=incoming.entity_id,
            entity_version=incoming.version,
            client_sequence=incoming.sequence,
            operation=incoming.operation,
            encrypted_payload=incoming.encrypted_payload,
            tombstone=incoming.tombstone,
            apply_status=apply_status,
            applied=applied,
            occurred_at=incoming.occurred_at,
        )
        session.add(change)
        await session.flush()

        if incoming.operation is SyncOperationKind.DELETE:
            if state is not None:
                await session.delete(state)
            if tombstone is None:
                tombstone = EntityTombstone(
                    user_id=actor.user_id,
                    entity_type=incoming.entity_type,
                    entity_id=incoming.entity_id,
                    deleted_version=incoming.version,
                    server_sequence=change.server_sequence,
                    deleted_at=utc_now(),
                )
                session.add(tombstone)
            else:
                tombstone.deleted_version = max(
                    tombstone.deleted_version, incoming.version
                )
                tombstone.server_sequence = change.server_sequence
                tombstone.deleted_at = utc_now()
        elif applied:
            if state is None:
                state = SyncEntityState(
                    user_id=actor.user_id,
                    entity_type=incoming.entity_type,
                    entity_id=incoming.entity_id,
                    version=incoming.version,
                    encrypted_payload=incoming.encrypted_payload,
                    last_server_sequence=change.server_sequence,
                    updated_at=utc_now(),
                )
                session.add(state)
            else:
                state.version = incoming.version
                state.encrypted_payload = incoming.encrypted_payload
                state.last_server_sequence = change.server_sequence
                state.updated_at = utc_now()
        results.append(
            SyncApplyResult(
                operation_id=incoming.operation_id,
                status=apply_status,
                server_sequence=change.server_sequence,
            )
        )

    # Push has no client pull cursor, so it cannot prove the device has observed
    # any prior changes. Start the returned cursor at zero to prevent data loss.
    high_watermark = 0
    cursor = await _issue_cursor(
        session, user_id=actor.user_id, high_watermark=high_watermark
    )
    response = SyncPushResponse(results=results, cursor=cursor)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=200,
    )


@router.get("/pull", response_model=SyncPullResponse)
async def pull_sync(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cursor: Annotated[str | None, Query(min_length=16, max_length=2048)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> SyncPullResponse:
    high_watermark = 0
    if cursor:
        stored_cursor = await session.scalar(
            select(SyncCursor).where(SyncCursor.token_sha256 == _token_hash(cursor))
        )
        if stored_cursor is None or stored_cursor.user_id != actor.user_id:
            raise ServiceError(
                400, "invalid_sync_cursor", "The sync cursor is invalid."
            )
        expires_at = stored_cursor.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= utc_now():
            raise ServiceError(
                410, "sync_cursor_expired", "The sync cursor has expired."
            )
        high_watermark = stored_cursor.high_watermark

    rows = list(
        await session.scalars(
            select(SyncChange)
            .where(
                SyncChange.user_id == actor.user_id,
                SyncChange.server_sequence > high_watermark,
                SyncChange.applied.is_(True),
            )
            .order_by(SyncChange.server_sequence)
            .limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    next_high_watermark = page[-1].server_sequence if page else high_watermark
    next_cursor = await _issue_cursor(
        session,
        user_id=actor.user_id,
        high_watermark=next_high_watermark,
    )
    await session.commit()
    operations = [
        SyncOperationOutput(
            operation_id=value.operation_id,
            idempotency_key=value.client_idempotency_key,
            device_id=value.device_id,
            entity_type=value.entity_type,
            entity_id=value.entity_id,
            version=value.entity_version,
            sequence=value.client_sequence,
            occurred_at=value.occurred_at,
            operation=value.operation,
            encrypted_payload=value.encrypted_payload,
            tombstone=value.tombstone,
            server_sequence=value.server_sequence,
        )
        for value in page
    ]
    return SyncPullResponse(
        operations=operations,
        cursor=next_cursor,
        has_more=has_more,
    )
