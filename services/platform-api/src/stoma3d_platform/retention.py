"""Bounded retention sweeps for private bytes and short-lived metadata."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select

from .models import (
    AccessEvent,
    AnalyticsEvent,
    AuditEvent,
    CaptureAsset,
    CaptureStatus,
    ClinicianAccessGrant,
    ClinicianReview,
    ClinicianVerification,
    DataExportArtifact,
    DeletionRequest,
    GeneratedArtifact,
    IdempotencyRecord,
    Job,
    JobStatus,
    ReportArtifact,
    ReviewAnnotation,
    ServiceRequestNonce,
    ShareExchangeToken,
    ShareLink,
    SyncCursor,
    utc_now,
)
from .object_storage import StorageError

logger = logging.getLogger("stoma3d_platform.retention")


def _deadline(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


async def _delete_object(app, object_key: str | None) -> bool:
    if not object_key:
        return True
    try:
        await app.state.object_storage.delete(object_key)
    except StorageError:
        return False
    return True


async def sweep_retention(app, *, now: datetime | None = None) -> dict[str, int]:
    """Delete expired content first, then make its metadata unavailable."""

    current = now or utc_now()
    counts = {
        "captureBytes": 0,
        "expiredUploads": 0,
        "generatedArtifacts": 0,
        "reports": 0,
        "exports": 0,
        "metadata": 0,
        "expiredJobs": 0,
        "scrubbedJobs": 0,
    }
    async with app.state.database.sessions() as session:
        captures = list(
            await session.scalars(
                select(CaptureAsset).where(
                    CaptureAsset.retention_expires_at.is_not(None),
                    CaptureAsset.retention_expires_at <= current,
                    CaptureAsset.deleted_at.is_(None),
                )
            )
        )
        for value in captures:
            if await _delete_object(app, value.object_key):
                value.status = CaptureStatus.DELETED
                value.deleted_at = current
                counts["captureBytes"] += 1

        pending_uploads = list(
            await session.scalars(
                select(CaptureAsset).where(
                    CaptureAsset.status == CaptureStatus.PENDING,
                    CaptureAsset.upload_expires_at.is_not(None),
                    CaptureAsset.upload_expires_at <= current,
                    CaptureAsset.deleted_at.is_(None),
                )
            )
        )
        for value in pending_uploads:
            if await _delete_object(app, value.object_key):
                value.status = CaptureStatus.DELETED
                value.deleted_at = current
                counts["expiredUploads"] += 1

        generated = list(
            await session.scalars(
                select(GeneratedArtifact).where(
                    GeneratedArtifact.retention_expires_at <= current
                )
            )
        )
        for value in generated:
            if await _delete_object(app, value.object_key):
                await session.delete(value)
                counts["generatedArtifacts"] += 1

        reports = list(
            await session.scalars(
                select(ReportArtifact).where(
                    ReportArtifact.retention_expires_at.is_not(None),
                    ReportArtifact.retention_expires_at <= current,
                    ReportArtifact.deleted_at.is_(None),
                )
            )
        )
        for value in reports:
            if await _delete_object(app, value.object_key):
                value.object_key = None
                value.deleted_at = current
                counts["reports"] += 1

        exports = list(
            await session.scalars(
                select(DataExportArtifact).where(
                    DataExportArtifact.retention_expires_at <= current
                )
            )
        )
        for value in exports:
            if await _delete_object(app, value.object_key):
                await session.delete(value)
                counts["exports"] += 1

        for model, column in (
            (AnalyticsEvent, AnalyticsEvent.expires_at),
            (ServiceRequestNonce, ServiceRequestNonce.expires_at),
            (IdempotencyRecord, IdempotencyRecord.expires_at),
            (SyncCursor, SyncCursor.expires_at),
            (ShareExchangeToken, ShareExchangeToken.retention_expires_at),
            (ReviewAnnotation, ReviewAnnotation.retention_expires_at),
            (ClinicianReview, ClinicianReview.retention_expires_at),
            (ClinicianAccessGrant, ClinicianAccessGrant.retention_expires_at),
            (ShareLink, ShareLink.retention_expires_at),
            (ClinicianVerification, ClinicianVerification.retention_expires_at),
            (AccessEvent, AccessEvent.retention_expires_at),
            (AuditEvent, AuditEvent.retention_expires_at),
        ):
            condition = column <= current
            if model is AuditEvent:
                condition = column.is_not(None) & condition
            result = await session.execute(delete(model).where(condition))
            counts["metadata"] += int(result.rowcount or 0)

        expired_deletion_receipts = list(
            await session.scalars(
                select(DeletionRequest).where(
                    DeletionRequest.retention_expires_at.is_not(None),
                    DeletionRequest.retention_expires_at <= current,
                    DeletionRequest.subject_fingerprint.is_not(None),
                )
            )
        )
        for value in expired_deletion_receipts:
            value.subject_fingerprint = None
            counts["metadata"] += 1

        expiring_jobs = list(
            await session.scalars(
                select(Job).where(
                    Job.expires_at.is_not(None),
                    Job.expires_at <= current,
                    Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
                )
            )
        )
        for value in expiring_jobs:
            value.status = JobStatus.EXPIRED
            value.result_outcome = "failed"
            value.reason_code = "job_expired"
            value.completed_at = current
            counts["expiredJobs"] += 1

        terminal_jobs = list(
            await session.scalars(
                select(Job).where(
                    Job.completed_at.is_not(None),
                    Job.retention_policy.is_not(None),
                    Job.queue_envelope.is_not(None),
                )
            )
        )
        for value in terminal_jobs:
            policy = value.retention_policy or {}
            key = (
                "successDeleteAfter"
                if value.result_outcome == "complete"
                else "failureDeleteAfter"
            )
            cutoff = _deadline(policy.get(key))
            if cutoff is not None and cutoff <= current:
                value.queue_envelope = None
                value.request_payload = {}
                value.result_payload = None
                value.error_message = None
                value.input_refs = []
                value.output_refs = []
                counts["scrubbedJobs"] += 1

        await session.commit()
    return counts


async def retention_loop(app) -> None:
    interval = app.state.settings.retention_sweep_interval_seconds
    while interval > 0:
        try:
            await sweep_retention(app)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - never log private record content
            logger.error("retention_sweep_failed type=%s", type(exc).__name__)
        await asyncio.sleep(interval)
