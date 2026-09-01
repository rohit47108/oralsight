"""HMAC-authenticated publication of generated GLB and MP4 artifacts."""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile
from starlette.responses import Response

from ..collaboration_common import append_audit_event, as_utc
from ..dependencies import Actor, get_current_actor, get_session
from ..errors import ServiceError
from ..internal_schemas import (
    GeneratedArtifactList,
    GeneratedArtifactMetadata,
    GeneratedArtifactResponse,
)
from ..models import (
    GeneratedArtifact,
    GeneratedArtifactPurpose,
    CaptureAsset,
    CaptureStatus,
    Job,
    JobStatus,
    JobType,
    ServiceRequestNonce,
    User,
    UserStatus,
    new_id,
    utc_now,
)
from ..object_storage import StorageError, StorageNotFound

router = APIRouter(tags=["internal generated assets"])
SERVICE_ID = "stoma3d-worker"
SAFE_NONCE = re.compile(r"^[a-f0-9]{32,128}$")
SAFE_DIGEST = re.compile(r"^[a-f0-9]{64}$")
SIGNATURE_WINDOW_SECONDS = 300
METADATA_MAX_BYTES = 64_000
WRITABLE_JOB_STATUSES = frozenset({JobStatus.QUEUED, JobStatus.RUNNING})


def _artifact_response(value: GeneratedArtifact) -> GeneratedArtifactResponse:
    return GeneratedArtifactResponse(
        artifact_id=value.id,
        owner_id=value.user_id,
        job_id=value.job_id,
        purpose=value.purpose,
        filename=value.filename,
        media_type=value.media_type,
        sha256=value.content_sha256,
        size_bytes=value.size_bytes,
        object_key=value.object_key,
        manifest=value.manifest,
        created_at=value.created_at,
        retention_expires_at=value.retention_expires_at,
    )


def _internal_auth_error() -> ServiceError:
    return ServiceError(
        401,
        "invalid_service_signature",
        "The service request could not be verified.",
    )


async def _authenticate_worker(
    *,
    request: Request,
    session: AsyncSession,
    body: bytes,
    service_id: str | None,
    timestamp: str | None,
    nonce: str | None,
    content_sha256: str | None,
    signature: str | None,
) -> None:
    if (
        service_id != SERVICE_ID
        or timestamp is None
        or nonce is None
        or content_sha256 is None
        or signature is None
        or SAFE_NONCE.fullmatch(nonce) is None
        or SAFE_DIGEST.fullmatch(content_sha256) is None
        or SAFE_DIGEST.fullmatch(signature) is None
    ):
        raise _internal_auth_error()
    try:
        signed_at = int(timestamp)
    except ValueError as exc:
        raise _internal_auth_error() from exc
    now_epoch = int(time.time())
    if abs(now_epoch - signed_at) > SIGNATURE_WINDOW_SECONDS:
        raise _internal_auth_error()
    actual_body_sha256 = hashlib.sha256(body).hexdigest()
    if not hmac.compare_digest(actual_body_sha256, content_sha256):
        raise _internal_auth_error()
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"
    canonical = "\n".join(
        [request.method.upper(), path, timestamp, nonce, content_sha256]
    ).encode("utf-8")
    expected_signature = hmac.new(
        request.app.state.settings.worker_service_hmac_secret.get_secret_value().encode(
            "utf-8"
        ),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        raise _internal_auth_error()
    nonce_sha256 = hashlib.sha256(nonce.encode("ascii")).hexdigest()
    existing = await session.get(ServiceRequestNonce, nonce_sha256)
    if existing is not None:
        raise ServiceError(
            409, "service_replay_rejected", "This service request was already used."
        )
    now = utc_now()
    await session.execute(
        delete(ServiceRequestNonce).where(ServiceRequestNonce.expires_at <= now)
    )
    session.add(
        ServiceRequestNonce(
            nonce_sha256=nonce_sha256,
            service_id=SERVICE_ID,
            request_sha256=content_sha256,
            created_at=now,
            expires_at=now + timedelta(minutes=10),
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ServiceError(
            409, "service_replay_rejected", "This service request was already used."
        ) from exc


async def _lock_writable_job(
    session: AsyncSession,
    *,
    job_id: str,
    expected_job_type: JobType,
    not_found_message: str,
) -> tuple[Job, User]:
    """Serialize an internal publisher with account deletion and job completion."""

    owner_id = await session.scalar(
        select(Job.user_id).where(
            Job.id == job_id,
            Job.job_type == expected_job_type,
        )
    )
    if owner_id is None:
        raise ServiceError(404, "job_not_found", not_found_message)
    user = await session.scalar(
        select(User).where(User.id == owner_id).with_for_update()
    )
    if user is None:
        raise ServiceError(404, "account_not_found", "The account was not found.")
    if user.status is UserStatus.DELETION_PENDING:
        raise ServiceError(
            409,
            "account_deletion_pending",
            "The account is pending deletion.",
        )
    if user.status is not UserStatus.ACTIVE:
        raise ServiceError(409, "account_not_active", "The account is not active.")
    job = await session.scalar(
        select(Job)
        .where(Job.id == job_id, Job.user_id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job is None or job.job_type is not expected_job_type:
        raise ServiceError(404, "job_not_found", not_found_message)
    if (
        job.status not in WRITABLE_JOB_STATUSES
        or job.cancellation_requested_at is not None
        or job.result_outcome is not None
        or job.completed_at is not None
    ):
        raise ServiceError(
            409,
            "job_not_writable",
            "The job no longer accepts generated output.",
        )
    return job, user


async def _cleanup_failed_object(request: Request, object_key: str) -> None:
    try:
        await request.app.state.object_storage.delete(object_key)
    except StorageError:
        pass


def _media_signature_is_valid(media_type: str, data: bytes) -> bool:
    if media_type == "model/gltf-binary":
        return len(data) >= 12 and data[:4] == b"glTF"
    if media_type == "video/mp4":
        return len(data) >= 12 and data[4:8] == b"ftyp"
    return False


async def _parse_upload(
    request: Request, body: bytes
) -> tuple[GeneratedArtifactMetadata, bytes]:
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data;"):
        raise ServiceError(
            415, "unsupported_media_type", "A multipart artifact upload is required."
        )
    try:
        form = await request.form(max_files=1, max_fields=1)
    except Exception as exc:
        raise ServiceError(
            422, "invalid_artifact_upload", "The upload is invalid."
        ) from exc
    items = list(form.multi_items())
    if len(items) != 2 or {name for name, _value in items} != {"metadata", "artifact"}:
        raise ServiceError(422, "invalid_artifact_upload", "The upload is invalid.")
    metadata_value = form.get("metadata")
    artifact = form.get("artifact")
    if not isinstance(metadata_value, str) or not isinstance(artifact, UploadFile):
        raise ServiceError(422, "invalid_artifact_upload", "The upload is invalid.")
    if len(metadata_value.encode("utf-8")) > METADATA_MAX_BYTES:
        raise ServiceError(
            413, "artifact_metadata_too_large", "Artifact metadata is too large."
        )
    try:
        metadata = GeneratedArtifactMetadata.model_validate_json(metadata_value)
    except ValidationError as exc:
        raise ServiceError(
            422, "invalid_artifact_metadata", "Artifact metadata is invalid."
        ) from exc
    settings = request.app.state.settings
    if metadata.size_bytes > settings.generated_asset_max_bytes:
        raise ServiceError(413, "artifact_too_large", "The artifact is too large.")
    if (
        artifact.filename != metadata.filename
        or artifact.content_type != metadata.media_type
    ):
        raise ServiceError(
            422, "artifact_metadata_mismatch", "Artifact metadata does not match."
        )
    data = await artifact.read(settings.generated_asset_max_bytes + 1)
    await artifact.close()
    if (
        len(data) != metadata.size_bytes
        or len(data) > settings.generated_asset_max_bytes
    ):
        raise ServiceError(
            422, "artifact_size_mismatch", "Artifact size does not match."
        )
    if hashlib.sha256(data).hexdigest() != metadata.sha256:
        raise ServiceError(
            422, "artifact_hash_mismatch", "Artifact hash does not match."
        )
    if not _media_signature_is_valid(metadata.media_type, data):
        raise ServiceError(
            422, "artifact_media_mismatch", "Artifact content is invalid."
        )
    del body
    return metadata, data


@router.post(
    "/internal/v2/assets/generated",
    response_model=GeneratedArtifactResponse,
    status_code=status.HTTP_200_OK,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["metadata", "artifact"],
                        "properties": {
                            "metadata": {
                                "type": "string",
                                "contentMediaType": "application/json",
                            },
                            "artifact": {"type": "string", "format": "binary"},
                        },
                    }
                }
            },
        }
    },
)
async def upload_generated_artifact(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    service_id: Annotated[str | None, Header(alias="X-Stoma3D-Service")] = None,
    timestamp: Annotated[str | None, Header(alias="X-Stoma3D-Timestamp")] = None,
    nonce: Annotated[str | None, Header(alias="X-Stoma3D-Nonce")] = None,
    content_sha256: Annotated[
        str | None, Header(alias="X-Stoma3D-Content-SHA256")
    ] = None,
    signature: Annotated[str | None, Header(alias="X-Stoma3D-Signature")] = None,
) -> GeneratedArtifactResponse:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise ServiceError(
                400, "invalid_content_length", "The upload is invalid."
            ) from exc
        if (
            declared_length
            > request.app.state.settings.generated_asset_max_bytes + 1_000_000
        ):
            raise ServiceError(413, "artifact_too_large", "The artifact is too large.")
    body = await request.body()
    if len(body) > request.app.state.settings.generated_asset_max_bytes + 1_000_000:
        raise ServiceError(413, "artifact_too_large", "The artifact is too large.")
    await _authenticate_worker(
        request=request,
        session=session,
        body=body,
        service_id=service_id,
        timestamp=timestamp,
        nonce=nonce,
        content_sha256=content_sha256,
        signature=signature,
    )
    metadata, data = await _parse_upload(request, body)
    expected_job_type = {
        GeneratedArtifactPurpose.RECONSTRUCTION: JobType.RECONSTRUCTION,
        GeneratedArtifactPurpose.SUMMARY_VIDEO: JobType.SUMMARY_VIDEO,
    }[metadata.purpose]
    job, _user = await _lock_writable_job(
        session,
        job_id=metadata.job_id,
        expected_job_type=expected_job_type,
        not_found_message="The artifact job was not found.",
    )
    existing = await session.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.job_id == job.id,
            GeneratedArtifact.purpose == metadata.purpose,
        )
    )
    if existing is not None:
        data = b""
        if (
            existing.content_sha256 != metadata.sha256
            or existing.size_bytes != metadata.size_bytes
            or existing.media_type != metadata.media_type
        ):
            raise ServiceError(
                409, "artifact_already_published", "This job already has an artifact."
            )
        return _artifact_response(existing)
    now = utc_now()
    artifact_id = new_id()
    object_key = f"users/{job.user_id}/generated/{artifact_id}/{metadata.filename}"
    try:
        await request.app.state.object_storage.put_bytes(
            object_key,
            data,
            media_type=metadata.media_type,
            sha256=metadata.sha256,
        )
        data = b""
        value = GeneratedArtifact(
            id=artifact_id,
            user_id=job.user_id,
            job_id=job.id,
            purpose=metadata.purpose,
            filename=metadata.filename,
            media_type=metadata.media_type,
            content_sha256=metadata.sha256,
            size_bytes=metadata.size_bytes,
            object_key=object_key,
            manifest=metadata.manifest,
            created_at=now,
            retention_expires_at=now
            + timedelta(days=request.app.state.settings.generated_asset_retention_days),
        )
        session.add(value)
        job.output_refs = [*job.output_refs, value.id]
        job.resource_id = value.id
        append_audit_event(
            session,
            patient_user_id=job.user_id,
            actor_user_id=None,
            event_type="generated_artifact.published",
            resource_type="generated_artifact",
            resource_id=value.id,
            request_id=request.state.request_id,
            details={
                "purpose": metadata.purpose.value,
                "sizeBytes": metadata.size_bytes,
            },
        )
        await session.commit()
    except StorageError as exc:
        data = b""
        await session.rollback()
        await _cleanup_failed_object(request, object_key)
        raise ServiceError(
            503, "object_storage_unavailable", "Storage is unavailable."
        ) from exc
    except IntegrityError as exc:
        data = b""
        await session.rollback()
        await _cleanup_failed_object(request, object_key)
        existing = await session.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.job_id == job.id,
                GeneratedArtifact.purpose == metadata.purpose,
            )
        )
        if existing is not None and existing.content_sha256 == metadata.sha256:
            return _artifact_response(existing)
        raise ServiceError(
            409, "artifact_publish_conflict", "The artifact could not be published."
        ) from exc
    except BaseException:
        data = b""
        await session.rollback()
        await _cleanup_failed_object(request, object_key)
        raise
    return _artifact_response(value)


async def _owned_generated_artifact(
    session: AsyncSession, artifact_id: str, actor: Actor
) -> GeneratedArtifact:
    value = await session.get(GeneratedArtifact, artifact_id)
    if value is None or value.user_id != actor.user_id:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    if as_utc(value.retention_expires_at) <= utc_now():
        raise ServiceError(410, "artifact_expired", "This artifact has expired.")
    return value


@router.get(
    "/v2/generated-artifacts/{artifact_id}", response_model=GeneratedArtifactResponse
)
async def get_generated_artifact(
    artifact_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GeneratedArtifactResponse:
    return _artifact_response(
        await _owned_generated_artifact(session, artifact_id, actor)
    )


@router.get("/v2/generated-artifacts", response_model=GeneratedArtifactList)
async def list_generated_artifacts(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    before: Annotated[datetime | None, Query()] = None,
) -> GeneratedArtifactList:
    now = utc_now()
    query = select(GeneratedArtifact).where(
        GeneratedArtifact.user_id == actor.user_id,
        GeneratedArtifact.retention_expires_at > now,
    )
    if before is not None:
        query = query.where(GeneratedArtifact.created_at < before)
    rows = list(
        await session.scalars(
            query.order_by(
                GeneratedArtifact.created_at.desc(), GeneratedArtifact.id.desc()
            ).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    cursor = (
        rows[-1].created_at.astimezone(UTC).isoformat() if has_more and rows else None
    )
    return GeneratedArtifactList(
        items=[_artifact_response(value) for value in rows], next_cursor=cursor
    )


@router.get("/v2/generated-artifacts/{artifact_id}/content")
async def get_generated_artifact_content(
    artifact_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    value = await _owned_generated_artifact(session, artifact_id, actor)
    try:
        data = await request.app.state.object_storage.get_bytes(
            value.object_key, max_bytes=value.size_bytes
        )
    except StorageNotFound as exc:
        raise ServiceError(
            410, "artifact_content_unavailable", "Artifact content is unavailable."
        ) from exc
    except StorageError as exc:
        raise ServiceError(
            503, "object_storage_unavailable", "Storage is unavailable."
        ) from exc
    if (
        len(data) != value.size_bytes
        or hashlib.sha256(data).hexdigest() != value.content_sha256
    ):
        raise ServiceError(
            500, "stored_artifact_corrupt", "The stored artifact failed verification."
        )
    return Response(
        content=data,
        media_type=value.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{value.filename}"',
        },
    )


@router.get("/internal/v2/assets/{asset_id}/content", include_in_schema=True)
async def get_internal_capture_asset_content(
    asset_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    service_id: Annotated[str | None, Header(alias="X-Stoma3D-Service")] = None,
    timestamp: Annotated[str | None, Header(alias="X-Stoma3D-Timestamp")] = None,
    nonce: Annotated[str | None, Header(alias="X-Stoma3D-Nonce")] = None,
    content_sha256: Annotated[
        str | None, Header(alias="X-Stoma3D-Content-SHA256")
    ] = None,
    signature: Annotated[str | None, Header(alias="X-Stoma3D-Signature")] = None,
) -> Response:
    await _authenticate_worker(
        request=request,
        session=session,
        body=b"",
        service_id=service_id,
        timestamp=timestamp,
        nonce=nonce,
        content_sha256=content_sha256,
        signature=signature,
    )
    asset = await session.get(CaptureAsset, asset_id)
    if (
        asset is None
        or asset.deleted_at is not None
        or asset.status is not CaptureStatus.AVAILABLE
    ):
        raise ServiceError(404, "asset_not_found", "The asset was not found.")
    try:
        data = await request.app.state.object_storage.get_bytes(
            asset.object_key, max_bytes=asset.byte_size
        )
    except StorageNotFound as exc:
        raise ServiceError(404, "asset_not_found", "The asset was not found.") from exc
    except StorageError as exc:
        raise ServiceError(
            503, "object_storage_unavailable", "Storage is unavailable."
        ) from exc
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
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )
