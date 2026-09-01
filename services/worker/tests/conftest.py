from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from stoma3d_worker.models import (
    AnalyzePayload,
    AssetPointer,
    JobEnvelope,
    JobType,
    ModelHead,
    MouthRegion,
    RetentionPolicy,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
JOB_ID = UUID("00000000-0000-4000-8000-000000000001")
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000002")
ACCOUNT_ID = UUID("00000000-0000-4000-8000-000000000003")
TRACE_ID = UUID("00000000-0000-4000-8000-000000000004")
CAPTURE_ID = UUID("00000000-0000-4000-8000-000000000005")
ASSET_ID = UUID("00000000-0000-4000-8000-000000000006")
IMAGE_BYTES = b"valid-sanitized-image"


def asset_pointer(data: bytes = IMAGE_BYTES) -> AssetPointer:
    return AssetPointer(
        asset_id=ASSET_ID,
        sha256=hashlib.sha256(data).hexdigest(),
        media_type="image/jpeg",
        size_bytes=len(data),
    )


def retention() -> RetentionPolicy:
    return RetentionPolicy(
        input_delete_after=NOW + timedelta(hours=23, minutes=30),
        success_delete_after=NOW + timedelta(days=20),
        failure_delete_after=NOW + timedelta(days=5),
        dead_letter_delete_after=NOW + timedelta(days=5),
    )


def analysis_envelope(**changes) -> JobEnvelope:
    values = {
        "job_id": JOB_ID,
        "request_id": REQUEST_ID,
        "account_id": ACCOUNT_ID,
        "trace_id": TRACE_ID,
        "job_type": JobType.ANALYSIS,
        "created_at": NOW,
        "not_before": NOW,
        "expires_at": NOW + timedelta(hours=23),
        "idempotency_key": "analysis:00000000-0000-4000-8000-000000000005",
        "attempt": 1,
        "max_attempts": 5,
        "retention": retention(),
        "payload": AnalyzePayload(
            capture_id=CAPTURE_ID,
            image=asset_pointer(),
            selected_region=MouthRegion.DORSAL_TONGUE,
            requested_heads=[ModelHead.SEGMENTATION, ModelHead.ANATOMY],
        ),
    }
    values.update(changes)
    return JobEnvelope(**values)


@pytest.fixture
def envelope() -> JobEnvelope:
    return analysis_envelope()
