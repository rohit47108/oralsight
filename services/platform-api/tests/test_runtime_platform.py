from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4
from zipfile import ZipFile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import func, select

from oralsight_platform.models import (
    AnalysisOrigin,
    AnalysisRun,
    AnalysisStatus,
    AnalyticsEvent,
    CalibrationStatus,
    CandidateObservation,
    CaptureAsset,
    CaptureStatus,
    InputOrigin,
    Job,
    MouthRegion,
    User,
    UserRole,
    UserStatus,
    new_id,
    utc_now,
)
from oralsight_platform.job_outbox import dispatch_job_outbox_once
from oralsight_platform.object_storage import (
    S3ObjectStorage,
    StorageIntegrityError,
    StorageNotFound,
)
from oralsight_platform.portable_export import decrypt_portable_export
from oralsight_platform.retention import sweep_retention


def _idempotent(auth_headers, key: str) -> dict[str, str]:
    return {**auth_headers(), "Idempotency-Key": key}


def _service_headers(settings, method: str, path: str, body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    digest = hashlib.sha256(body).hexdigest()
    canonical = "\n".join([method.upper(), path, timestamp, nonce, digest]).encode()
    signature = hmac.new(
        settings.worker_service_hmac_secret.get_secret_value().encode(),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-OralSight-Service": "oralsight-worker",
        "X-OralSight-Timestamp": timestamp,
        "X-OralSight-Nonce": nonce,
        "X-OralSight-Content-SHA256": digest,
        "X-OralSight-Signature": signature,
    }


async def _signed_json(client, settings, path: str, value: dict):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return await client.post(
        path,
        content=body,
        headers={
            **_service_headers(settings, "POST", path, body),
            "Content-Type": "application/json",
        },
    )


async def _accept_consent(client, auth_headers, *, suffix: str) -> str:
    document = (await client.get("/v2/consent-documents/current")).json()
    accepted = await client.post(
        "/v2/consents",
        headers=_idempotent(auth_headers, f"consent-{suffix}-000000"),
        json={
            "documentId": document["documentId"],
            "documentVersion": document["documentVersion"],
            "documentSha256": document["documentSha256"],
            "accepted": True,
            "deviceId": None,
        },
    )
    if accepted.status_code == 409:
        listed = await client.get("/v2/consents", headers=auth_headers())
        return next(
            item["consentRecordId"] for item in listed.json()["items"] if item["active"]
        )
    assert accepted.status_code == 201, accepted.text
    return accepted.json()["consentRecordId"]


def _test_jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (640, 480), "#b66a62").save(output, format="JPEG", quality=92)
    return output.getvalue()


async def _uploaded_capture(
    client,
    auth_headers,
    *,
    suffix: str,
    data: bytes | None = None,
    retention_expires_at: datetime | None = None,
):
    data = data or _test_jpeg()
    digest = hashlib.sha256(data).hexdigest()
    consent_record_id = await _accept_consent(client, auth_headers, suffix=suffix)
    scan = await client.post(
        "/v2/scan-sessions",
        headers=_idempotent(auth_headers, f"scan-{suffix}-00000000"),
        json={
            "protocol": "standard_eight_region",
            "deviceId": None,
            "consentRecordId": consent_record_id,
        },
    )
    assert scan.status_code == 201, scan.text
    scan_id = scan.json()["scanSessionId"]
    capture_set = await client.post(
        f"/v2/scan-sessions/{scan_id}/capture-sets",
        headers=_idempotent(auth_headers, f"set-{suffix}-000000000"),
        json={
            "region": "left_buccal_mucosa",
            "protocol": "standard_eight_region",
        },
    )
    assert capture_set.status_code == 201, capture_set.text
    capture_set_id = capture_set.json()["captureSetId"]
    captured_at = datetime.now(UTC).isoformat()
    view = await client.post(
        f"/v2/capture-sets/{capture_set_id}/views",
        headers=_idempotent(auth_headers, f"view-{suffix}-00000000"),
        json={
            "angle": "primary",
            "anatomicalSite": "left_buccal_mucosa",
            "asset": {
                "mediaKind": "image",
                "mimeType": "image/jpeg",
                "byteSize": len(data),
                "sha256": digest,
                "widthPx": 640,
                "heightPx": 480,
                "durationMs": None,
                "inputOrigin": "live_capture",
                "encrypted": True,
                "retentionExpiresAt": (
                    retention_expires_at.isoformat()
                    if retention_expires_at is not None
                    else None
                ),
            },
            "sourceVideoAssetId": None,
            "qualityAccepted": True,
            "qualityReasons": [],
            "ordinal": 0,
            "capturedAt": captured_at,
            "makePrimary": True,
        },
    )
    assert view.status_code == 201, view.text
    selected = view.json()["views"][0]
    asset_id = selected["asset"]["assetId"]
    assert selected["asset"]["uploadStatus"] == "pending"
    intent = await client.post(
        f"/v2/capture-assets/{asset_id}/upload-intent", headers=auth_headers()
    )
    assert intent.status_code == 200, intent.text
    parsed = urlsplit(intent.json()["url"])
    uploaded = await client.put(
        parsed.path,
        content=data,
        headers=intent.json()["headers"],
    )
    assert uploaded.status_code == 204, uploaded.text
    finalized = await client.post(
        f"/v2/capture-assets/{asset_id}/finalize", headers=auth_headers()
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["asset"]["uploadStatus"] == "available"
    return {
        "scan_id": scan_id,
        "consent_record_id": consent_record_id,
        "capture_set_id": capture_set_id,
        "view_id": selected["captureViewId"],
        "asset_id": asset_id,
        "sha256": digest,
        "size": len(data),
        "data": data,
        "captured_at": captured_at,
    }


async def _insert_observation(app, capture: dict) -> str:
    async with app.state.database.sessions() as session:
        user_id = await session.scalar(select(CaptureAsset.user_id).limit(1))
        run = AnalysisRun(
            id=new_id(),
            user_id=user_id,
            capture_set_id=capture["capture_set_id"],
            requested_heads=["segmentation", "anatomy"],
            status=AnalysisStatus.COMPLETE,
            input_origin=InputOrigin.LIVE_CAPTURE,
            analysis_origin=AnalysisOrigin.LIVE_MODEL,
            source_asset_sha256=[capture["sha256"]],
            model_versions={"segmentation": "test-v1"},
            artifact_hashes={"mask": "a" * 64},
            abstention_reasons=[],
            started_at=utc_now(),
            completed_at=utc_now(),
            persisted=True,
            signed_envelope_id=f"test-{uuid4()}",
            created_at=utc_now(),
        )
        session.add(run)
        await session.flush()
        observation = CandidateObservation(
            id=new_id(),
            user_id=user_id,
            analysis_run_id=run.id,
            capture_view_id=capture["view_id"],
            region=MouthRegion.LEFT_BUCCAL_MUCOSA,
            anatomical_site="left_buccal_mucosa",
            candidate_mask={
                "polygon": [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4]],
                "boundingBox": [0.2, 0.2, 0.2, 0.2],
                "normalizedArea": 0.02,
            },
            descriptors={
                "normalizedArea": 0.02,
                "perimeter": 0.5,
                "borderIrregularity": 0.1,
                "meanRedness": 0.5,
                "meanBrightness": 0.5,
                "textureContrast": 0.2,
                "measurementLabel": "approximate",
            },
            uncertainty={
                "overallConfidence": 0.8,
                "imageQualityConfidence": 0.9,
                "datasetSimilarity": 0.7,
                "modelAgreement": 0.8,
                "limitations": ["Research prototype."],
            },
            calibration_status=CalibrationStatus.NOT_ATTEMPTED,
            limitations=["Approximate image-derived observation."],
            created_at=utc_now(),
        )
        session.add(observation)
        await session.commit()
        return observation.id


async def test_s3_upload_intent_signs_exact_content_length():
    class RecordingClient:
        def __init__(self) -> None:
            self.call = None

        def generate_presigned_url(self, operation, **kwargs):
            self.call = (operation, kwargs)
            return "https://private.example.test/upload"

    storage = object.__new__(S3ObjectStorage)
    storage.bucket = "private-test"
    storage.settings = SimpleNamespace(
        object_storage_sse="AES256", object_storage_kms_key_id=None
    )
    storage.client = RecordingClient()

    intent = await storage.presign_upload(
        "users/test/captures/asset",
        media_type="image/jpeg",
        sha256="a" * 64,
        size_bytes=12_345,
        lifetime_seconds=300,
    )

    assert storage.client.call is not None
    operation, kwargs = storage.client.call
    assert operation == "put_object"
    assert kwargs["Params"]["ContentLength"] == 12_345
    expected_checksum = base64.b64encode(bytes.fromhex("a" * 64)).decode("ascii")
    assert kwargs["Params"]["ChecksumSHA256"] == expected_checksum
    assert intent.headers["Content-Length"] == "12345"
    assert intent.headers["x-amz-checksum-sha256"] == expected_checksum


async def test_s3_stat_requires_the_service_verified_body_checksum():
    digest = "a" * 64
    expected_checksum = base64.b64encode(bytes.fromhex(digest)).decode("ascii")

    class HeadClient:
        def __init__(self, checksum: str | None) -> None:
            self.checksum = checksum
            self.call = None

        def head_object(self, **kwargs):
            self.call = kwargs
            response = {
                "ContentLength": 12_345,
                "ContentType": "image/jpeg",
                "Metadata": {"sha256": digest},
            }
            if self.checksum is not None:
                response["ChecksumSHA256"] = self.checksum
            return response

    storage = object.__new__(S3ObjectStorage)
    storage.bucket = "private-test"
    storage.client = HeadClient(expected_checksum)
    stored = await storage.stat("users/test/captures/asset")
    assert stored.sha256 == digest
    assert storage.client.call["ChecksumMode"] == "ENABLED"

    storage.client = HeadClient(base64.b64encode(b"wrong").decode("ascii"))
    with pytest.raises(StorageIntegrityError, match="object_checksum_mismatch"):
        await storage.stat("users/test/captures/asset")

    storage.client = HeadClient(None)
    with pytest.raises(StorageIntegrityError, match="object_checksum_mismatch"):
        await storage.stat("users/test/captures/asset")


async def test_expired_pending_upload_is_deleted_and_cannot_finalize(
    client, app, auth_headers
):
    capture = await _uploaded_capture(
        client, auth_headers, suffix="expired-pending-finalize"
    )
    async with app.state.database.sessions() as session:
        asset = await session.get(CaptureAsset, capture["asset_id"])
        assert asset is not None
        object_key = asset.object_key
        asset.status = CaptureStatus.PENDING
        asset.upload_expires_at = utc_now() - timedelta(seconds=1)
        await session.commit()

    response = await client.post(
        f"/v2/capture-assets/{capture['asset_id']}/finalize",
        headers=auth_headers(),
    )
    assert response.status_code == 410, response.text
    assert response.json()["error"]["code"] == "asset_upload_expired"
    with pytest.raises(StorageNotFound):
        await app.state.object_storage.stat(object_key)
    async with app.state.database.sessions() as session:
        asset = await session.get(CaptureAsset, capture["asset_id"])
        assert asset is not None
        assert asset.status.value == "deleted"
        assert asset.deleted_at is not None


async def test_retention_sweep_removes_abandoned_pending_upload(
    client, app, auth_headers
):
    capture = await _uploaded_capture(
        client, auth_headers, suffix="expired-pending-sweep"
    )
    deadline = utc_now() - timedelta(seconds=1)
    async with app.state.database.sessions() as session:
        asset = await session.get(CaptureAsset, capture["asset_id"])
        assert asset is not None
        object_key = asset.object_key
        asset.status = CaptureStatus.PENDING
        asset.upload_expires_at = deadline
        await session.commit()

    result = await sweep_retention(app, now=utc_now())
    assert result["expiredUploads"] == 1
    with pytest.raises(StorageNotFound):
        await app.state.object_storage.stat(object_key)


async def test_real_asset_queue_and_worker_fetch(
    client, app, settings, auth_headers
) -> None:
    capture = await _uploaded_capture(client, auth_headers, suffix="asset-runtime")
    closed = await client.post(
        f"/v2/capture-assets/{capture['asset_id']}/upload-intent",
        headers=auth_headers(),
    )
    assert closed.status_code == 409
    pointer = {
        "assetId": capture["asset_id"],
        "sha256": capture["sha256"],
        "mediaType": "image/jpeg",
        "sizeBytes": capture["size"],
    }
    job = await client.post(
        "/v2/jobs",
        headers=_idempotent(auth_headers, "analysis-runtime-job-0001"),
        json={
            "type": "analysis",
            "payload": {
                "contractVersion": "1.1.0",
                "captureId": capture["view_id"],
                "image": pointer,
                "selectedRegion": "left_buccal_mucosa",
                "requestedHeads": ["segmentation", "anatomy"],
                "inputOrigin": "live_capture",
                "calibration": None,
            },
            "maxAttempts": 3,
        },
    )
    assert job.status_code == 201, job.text
    assert len(app.state.job_queue.messages) == 1
    envelope = json.loads(app.state.job_queue.messages[0][1])
    assert envelope["jobId"] == job.json()["jobId"]
    assert envelope["payload"]["image"] == pointer
    assert envelope["retention"]["cleanupTargets"] == []

    async with app.state.database.sessions() as session:
        stored_job = await session.get(Job, job.json()["jobId"])
        stored_job.queue_published_at = utc_now() - timedelta(minutes=6)
        await session.commit()
    assert await dispatch_job_outbox_once(app) == 1
    assert len(app.state.job_queue.messages) == 2
    assert app.state.job_queue.messages[0][1] == app.state.job_queue.messages[1][1]

    path = f"/internal/v2/assets/{capture['asset_id']}/content"
    fetched = await client.get(
        path, headers=_service_headers(settings, "GET", path, b"")
    )
    assert fetched.status_code == 200
    assert fetched.content == capture["data"]

    notification = {
        "schemaVersion": "oralsight.job.v1",
        "jobId": job.json()["jobId"],
        "outcome": "unavailable",
        "completedAt": datetime.now(UTC).isoformat(),
        "result": {},
        "reasonCode": "analysis_unavailable",
    }
    result = await _signed_json(
        client,
        settings,
        f"/internal/v2/jobs/{job.json()['jobId']}/result",
        notification,
    )
    assert result.status_code == 200, result.text
    stored = await client.get(f"/v2/jobs/{job.json()['jobId']}", headers=auth_headers())
    assert stored.json()["outcome"] == "unavailable"
    assert stored.json()["reasonCode"] == "analysis_unavailable"

    retention = await _signed_json(
        client,
        settings,
        f"/internal/v2/jobs/{job.json()['jobId']}/retention",
        {"outcome": "unavailable", "retention": envelope["retention"]},
    )
    assert retention.status_code == 200, retention.text


async def test_analytics_is_explicit_allowlisted_and_short_lived(
    client, app, auth_headers
) -> None:
    event = {
        "events": [
            {
                "name": "scan_started",
                "platform": "ios",
                "appVersion": "1.0.0",
                "surface": "scan",
                "outcome": "started",
            }
        ]
    }
    default = await client.get("/v2/me/analytics-consent", headers=auth_headers())
    assert default.json()["enabled"] is False
    denied = await client.post(
        "/v2/analytics/events", headers=auth_headers(), json=event
    )
    assert denied.status_code == 403
    malformed = await client.post(
        "/v2/analytics/events",
        headers=auth_headers(),
        json={
            "events": [
                {
                    **event["events"][0],
                    "observationId": str(uuid4()),
                }
            ]
        },
    )
    assert malformed.status_code == 422
    enabled = await client.put(
        "/v2/me/analytics-consent",
        headers=auth_headers(),
        json={"enabled": True, "policyVersion": "analytics-v1"},
    )
    assert enabled.status_code == 200
    accepted = await client.post(
        "/v2/analytics/events", headers=auth_headers(), json=event
    )
    assert accepted.status_code == 202
    async with app.state.database.sessions() as session:
        stored = await session.scalar(select(AnalyticsEvent))
        assert stored.expires_at - stored.received_at == timedelta(days=30)


async def test_admin_analytics_requires_current_oidc_admin_role(
    client, app, auth_headers
) -> None:
    subject = "auth0|analytics-admin"
    provisioned = await client.get("/v2/me", headers=auth_headers(subject))
    assert provisioned.status_code == 200
    async with app.state.database.sessions() as session:
        user = await session.get(User, provisioned.json()["id"])
        assert user is not None
        user.role = UserRole.ADMIN
        await session.commit()

    stale_claim = await client.get(
        "/v2/admin/analytics/summary", headers=auth_headers(subject)
    )
    assert stale_claim.status_code == 403
    assert stale_claim.json()["error"]["code"] == "oidc_role_required"

    current_claim = await client.get(
        "/v2/admin/analytics/summary",
        headers=auth_headers(subject, roles=("admin",)),
    )
    assert current_claim.status_code == 200


async def test_real_pdf_and_recipient_encrypted_portable_export(
    client, app, settings, auth_headers
) -> None:
    capture = await _uploaded_capture(client, auth_headers, suffix="pdf-export")
    observation_id = await _insert_observation(app, capture)
    report_payload = {
        "scanSessionId": capture["scan_id"],
        "consentRecordId": capture["consent_record_id"],
        "observationIds": [observation_id],
        "comparisonIds": [],
        "patientProfile": {
            "ageRange": "40_64",
            "assisted": False,
        },
        "intakeSummary": {
            "firstNoticed": "A small patch noticed during brushing.",
            "durationDays": 12,
            "symptoms": ["tenderness"],
            "bleedingFrequency": "once",
            "bleedingDuration": "Stopped quickly.",
            "change": "no_change",
            "tobaccoExposure": "none",
            "alcoholExposure": "some",
            "previousConditions": "None reported.",
            "professionallyExamined": False,
        },
        "appointmentQuestions": ["What should I watch for before my appointment?"],
        "locale": "en-US",
        "includeExperimentalResearchOutput": False,
        "disclaimer": "This result is not a diagnosis.",
    }
    report_job = await client.post(
        "/v2/jobs",
        headers=_idempotent(auth_headers, "report-runtime-job-00001"),
        json={"type": "report", "payload": report_payload, "maxAttempts": 3},
    )
    assert report_job.status_code == 201, report_job.text
    rendered = await _signed_json(
        client,
        settings,
        "/internal/v2/reports/render",
        {"jobId": report_job.json()["jobId"], **report_payload},
    )
    assert rendered.status_code == 200, rendered.text
    pdf = await client.get(
        f"/v2/reports/{rendered.json()['artifactId']}/content",
        headers=auth_headers(),
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF-")
    assert hashlib.sha256(pdf.content).hexdigest() == rendered.json()["sha256"]
    parsed = PdfReader(BytesIO(pdf.content))
    assert parsed.pages
    for page in parsed.pages:
        assert "This result is not a diagnosis." in (page.extract_text() or "")
    text = "\n".join(page.extract_text() or "" for page in parsed.pages)
    assert "Consent and data use" in text
    assert "Symptoms and intake" in text
    assert "Oral observation map" in text
    assert "Questions for an appointment" in text
    assert "Input and analysis provenance" in text
    assert any("/XObject" in page["/Resources"] for page in parsed.pages), (
        "The report must render at least one embedded source image."
    )

    recipient_private = X25519PrivateKey.generate()
    recipient_public = recipient_private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    export_request_id = str(uuid4())
    encryption = {
        "scheme": "x25519-hkdf-sha256-aes-256-gcm",
        "recipientPublicKeyB64": base64.b64encode(recipient_public).decode(),
    }
    export_payload = {
        "exportRequestId": export_request_id,
        "scope": "all_portable_data",
        "format": "zip",
        "encryption": encryption,
        "includeFiles": True,
        "disclaimer": "This result is not a diagnosis.",
    }
    export_job = await client.post(
        "/v2/jobs",
        headers=_idempotent(auth_headers, "export-runtime-job-00001"),
        json={"type": "data_export", "payload": export_payload, "maxAttempts": 3},
    )
    assert export_job.status_code == 201, export_job.text
    export = await _signed_json(
        client,
        settings,
        "/internal/v2/exports/render",
        {"jobId": export_job.json()["jobId"], **export_payload},
    )
    assert export.status_code == 200, export.text
    artifact = await client.get(
        f"/v2/data-exports/{export.json()['artifactId']}/content",
        headers=auth_headers(),
    )
    assert artifact.status_code == 200
    metadata = export.json()["encryption"]
    recipient_private_b64 = base64.b64encode(
        recipient_private.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
    ).decode()
    plaintext = decrypt_portable_export(
        artifact.content,
        recipient_private_key_b64=recipient_private_b64,
        encryption=metadata,
    )
    wrong_key = X25519PrivateKey.generate().private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    with pytest.raises(ValueError, match="portable_export_decryption_failed"):
        decrypt_portable_export(
            artifact.content,
            recipient_private_key_b64=base64.b64encode(wrong_key).decode(),
            encryption=metadata,
        )
    with ZipFile(BytesIO(plaintext)) as archive:
        names = set(archive.namelist())
        assert "portable-manifest.json" in names
        assert "records/account.json" in names
        consents = json.loads(archive.read("records/consents.json"))
        assert (
            consents[0]["document_sha256"]
            == (await client.get("/v2/consent-documents/current")).json()[
                "documentSha256"
            ]
        )
        scans = json.loads(archive.read("records/scans.json"))
        assert scans[0]["consent_record_id"] == capture["consent_record_id"]
        observations = json.loads(archive.read("records/observations.json"))
        assert "estimated_area_mm2" in observations[0]
        assert json.loads(archive.read("records/jobs.json"))
        assert any(name.startswith("files/captures/") for name in names)
        included_capture = next(
            name for name in names if name.startswith("files/captures/")
        )
        assert archive.read(included_capture) == capture["data"]


async def test_delete_all_removes_bytes_rows_and_identity(
    client, app, settings, auth_headers
) -> None:
    capture = await _uploaded_capture(client, auth_headers, suffix="delete-all")
    consent = await client.put(
        "/v2/me/analytics-consent",
        headers=auth_headers(),
        json={"enabled": True, "policyVersion": "analytics-v1"},
    )
    assert consent.status_code == 200
    deletion = await client.post(
        "/v2/me/deletion-requests",
        headers=_idempotent(auth_headers, "delete-all-runtime-00001"),
        json={"confirmation": "DELETE"},
    )
    assert deletion.status_code == 202, deletion.text
    execute_path = (
        f"/internal/v2/deletion-requests/{deletion.json()['requestId']}/execute"
    )
    executed = await _signed_json(
        client,
        settings,
        execute_path,
        {
            "jobId": deletion.json()["jobId"],
            "subjectAccountId": (
                await client.get("/v2/me", headers=auth_headers())
            ).json()["id"],
            "scope": "all_oralsight_data",
            "rotateInstallationKey": True,
        },
    )
    assert executed.status_code == 200, executed.text
    completed = await client.get(
        f"/v2/me/deletion-requests/{deletion.json()['requestId']}",
        headers=auth_headers(),
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    async with app.state.database.sessions() as session:
        assert await session.scalar(select(func.count(CaptureAsset.id))) == 0
        assert await session.scalar(select(func.count(AnalyticsEvent.id))) == 0
        preserved = await session.get(Job, deletion.json()["jobId"])
        user = await session.get(User, preserved.user_id)
        assert user.status is UserStatus.SUSPENDED
        assert user.oidc_subject.startswith("deleted:")
        assert user.analytics_enabled is False
        # Polling a completed receipt authenticates the original subject without
        # silently provisioning a replacement account.
        assert await session.scalar(select(func.count(User.id))) == 1
    try:
        await app.state.object_storage.stat(
            f"users/{user.id}/captures/{capture['asset_id']}"
        )
    except StorageNotFound:
        pass
    else:
        raise AssertionError("Deleted account capture bytes still exist")
