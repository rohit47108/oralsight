"""Shared idempotency primitives for every state-changing product endpoint."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .errors import ServiceError
from .models import IdempotencyRecord, utc_now

IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")


def validate_idempotency_key(value: str | None) -> str:
    if value is None or IDEMPOTENCY_PATTERN.fullmatch(value) is None:
        raise ServiceError(
            400,
            "invalid_idempotency_key",
            "Idempotency-Key must be 16 to 128 safe ASCII characters.",
        )
    return value


def request_sha256(body: BaseModel) -> str:
    canonical = json.dumps(
        body.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


async def find_replay[ResponseModel: BaseModel](
    session: AsyncSession,
    *,
    user_id: str,
    scope: str,
    key: str,
    digest: str,
    response_model: type[ResponseModel],
) -> ResponseModel | None:
    record = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if record is None:
        return None
    if record.request_sha256 != digest:
        raise ServiceError(
            409,
            "idempotency_conflict",
            "This idempotency key was already used for a different request.",
        )
    return response_model.model_validate(record.response_payload)


async def commit_idempotent[ResponseModel: BaseModel](
    session: AsyncSession,
    *,
    user_id: str,
    scope: str,
    key: str,
    digest: str,
    response: ResponseModel,
    response_status: int,
) -> ResponseModel:
    now = utc_now()
    session.add(
        IdempotencyRecord(
            user_id=user_id,
            scope=scope,
            idempotency_key=key,
            request_sha256=digest,
            response_status=response_status,
            response_payload=response.model_dump(mode="json", by_alias=True),
            created_at=now,
            expires_at=now + timedelta(hours=48),
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        replay = await find_replay(
            session,
            user_id=user_id,
            scope=scope,
            key=key,
            digest=digest,
            response_model=type(response),
        )
        if replay is not None:
            return replay
        raise ServiceError(
            409,
            "request_conflict",
            "The request conflicted with another account operation.",
        ) from exc
    return response
