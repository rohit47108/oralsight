from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from oralsight_platform.models import (
    AccessGrantStatus,
    CandidateObservation,
    CaptureAsset,
    CaptureStatus,
    ClinicianAccessGrant,
    ClinicianVerification,
    ClinicianVerificationStatus,
    ConsentRecord,
    LesionObservationLink,
    LesionRecord,
    ReportArtifact,
    ShareExchangeToken,
    ShareLink,
    ShareLinkStatus,
    User,
    UserRole,
    utc_now,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _idempotent(auth_headers, key: str, subject: str = "auth0|patient-1"):
    return {**auth_headers(subject), "Idempotency-Key": key}


async def _accept_consent(
    client,
    auth_headers,
    *,
    key_suffix: str,
    subject: str = "auth0|patient-1",
) -> str:
    existing = await client.get("/v2/consents", headers=auth_headers(subject))
    assert existing.status_code == 200, existing.text
    active = next((item for item in existing.json()["items"] if item["active"]), None)
    if active is not None:
        return active["consentRecordId"]
    document = await client.get("/v2/consent-documents/current")
    assert document.status_code == 200, document.text
    current = document.json()
    accepted = await client.post(
        "/v2/consents",
        headers=_idempotent(auth_headers, f"consent-{key_suffix}", subject),
        json={
            "documentId": current["documentId"],
            "documentVersion": current["documentVersion"],
            "documentSha256": current["documentSha256"],
            "accepted": True,
            "deviceId": None,
        },
    )
    assert accepted.status_code == 201, accepted.text
    return accepted.json()["consentRecordId"]


async def _create_scan(
    client,
    auth_headers,
    *,
    key_suffix: str,
    subject: str = "auth0|patient-1",
    region: str = "left_buccal_mucosa",
    sha256: str = SHA_A,
    captured_at: datetime | None = None,
):
    anatomical_site = {
        "upper_lip": "upper_labial_mucosa",
        "lower_lip": "lower_labial_mucosa",
        "upper_dental_arch": "upper_gingiva",
        "lower_dental_arch": "lower_gingiva",
    }.get(region, region)
    consent_record_id = await _accept_consent(
        client, auth_headers, key_suffix=key_suffix, subject=subject
    )
    session = await client.post(
        "/v2/scan-sessions",
        headers=_idempotent(auth_headers, f"scan-session-{key_suffix}", subject),
        json={
            "protocol": "standard_eight_region",
            "deviceId": None,
            "consentRecordId": consent_record_id,
        },
    )
    assert session.status_code == 201, session.text
    scan_id = session.json()["scanSessionId"]
    capture_set = await client.post(
        f"/v2/scan-sessions/{scan_id}/capture-sets",
        headers=_idempotent(auth_headers, f"capture-set-{key_suffix}", subject),
        json={"region": region, "protocol": "standard_eight_region"},
    )
    assert capture_set.status_code == 201, capture_set.text
    capture_set_id = capture_set.json()["captureSetId"]
    view = await client.post(
        f"/v2/capture-sets/{capture_set_id}/views",
        headers=_idempotent(auth_headers, f"capture-view-{key_suffix}", subject),
        json={
            "angle": "primary",
            "anatomicalSite": anatomical_site,
            "asset": {
                "mediaKind": "image",
                "mimeType": "image/jpeg",
                "byteSize": 2048,
                "sha256": sha256,
                "widthPx": 1024,
                "heightPx": 768,
                "durationMs": None,
                "inputOrigin": "live_capture",
                "encrypted": True,
                "retentionExpiresAt": None,
            },
            "sourceVideoAssetId": None,
            "qualityAccepted": True,
            "qualityReasons": [],
            "ordinal": 0,
            "capturedAt": (captured_at or datetime.now(UTC)).isoformat(),
            "makePrimary": True,
        },
    )
    assert view.status_code == 201, view.text
    assert view.json()["complete"] is True
    return {
        "scan_id": scan_id,
        "consent_record_id": consent_record_id,
        "capture_set_id": capture_set_id,
        "view_id": view.json()["views"][0]["captureViewId"],
        "asset_id": view.json()["views"][0]["asset"]["assetId"],
        "sha256": sha256,
    }


def _observation(view_id: str, *, calibrated: bool = False):
    calibration = None
    if calibrated:
        calibration = {
            "status": "valid",
            "method": "versioned_reference_card",
            "cardVersion": "card-v1",
            "markerId": "marker-7",
            "referenceWidthMm": 10.0,
            "millimetersPerPixel": 0.05,
            "estimatedWidthMm": 3.5,
            "estimatedHeightMm": 2.0,
            "estimatedAreaMm2": 5.25,
            "confidence": 0.94,
            "gateReasons": [],
            "calibratedAt": datetime.now(UTC).isoformat(),
            "modelVersions": {"calibration": "1.0.0"},
            "measurementLabel": "calibrated estimate",
        }
    return {
        "captureViewId": view_id,
        "anatomicalSite": "left_buccal_mucosa",
        "candidateMask": {
            "polygon": [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4], [0.2, 0.4]],
            "boundingBox": [0.2, 0.2, 0.2, 0.2],
            "normalizedArea": 0.04,
        },
        "descriptors": {
            "normalizedArea": 0.04,
            "perimeter": 0.8,
            "borderIrregularity": 0.1,
            "meanRedness": 0.6,
            "meanBrightness": 0.5,
            "textureContrast": 0.2,
            "measurementLabel": "approximate",
        },
        "calibration": calibration,
        "appearanceOutput": None,
        "diseaseResearchOutput": None,
        "uncertainty": {
            "overallConfidence": 0.82,
            "imageQualityConfidence": 0.9,
            "datasetSimilarity": 0.75,
            "modelAgreement": 0.8,
            "limitations": ["Research output only."],
        },
        "namedMesh": None,
        "uvCoordinates": None,
        "assetVersion": None,
        "limitations": ["Approximate image-derived observation."],
    }


async def _create_analysis(
    client,
    auth_headers,
    capture,
    *,
    key_suffix: str,
    calibrated: bool = False,
    subject: str = "auth0|patient-1",
):
    now = datetime.now(UTC)
    response = await client.post(
        f"/v2/capture-sets/{capture['capture_set_id']}/analysis-runs",
        headers=_idempotent(auth_headers, f"analysis-run-{key_suffix}", subject),
        json={
            "requestedHeads": ["segmentation", "anatomy"],
            "status": "complete",
            "observations": [_observation(capture["view_id"], calibrated=calibrated)],
            "inputOrigin": "live_capture",
            "analysisOrigin": "live_model",
            "sourceAssetSha256": [capture["sha256"]],
            "modelVersions": {"segmentation": "seg-v1", "anatomy": "anat-v1"},
            "artifactHashes": {"segmentation": SHA_C},
            "abstentionReasons": [],
            "startedAt": (now - timedelta(seconds=2)).isoformat(),
            "completedAt": now.isoformat(),
            "signedEnvelopeId": f"signed-envelope-{key_suffix}",
        },
    )
    assert response.status_code == 201, response.text
    return {
        "analysis_id": response.json()["analysisRunId"],
        "observation_id": response.json()["observations"][0]["observationId"],
        "response": response.json(),
    }


async def test_product_consent_is_versioned_revocable_and_required(
    client, auth_headers
) -> None:
    document = await client.get("/v2/consent-documents/current")
    assert document.status_code == 200
    current = document.json()
    assert current["body"].endswith("This result is not a diagnosis.")
    assert (
        current["withdrawalEffect"]
        == "blocks_new_cloud_work_revokes_access_preserves_existing_data"
    )

    outdated = await client.post(
        "/v2/consents",
        headers=_idempotent(auth_headers, "consent-outdated-document-001"),
        json={
            "documentId": current["documentId"],
            "documentVersion": current["documentVersion"],
            "documentSha256": "0" * 64,
            "accepted": True,
            "deviceId": None,
        },
    )
    assert outdated.status_code == 409
    assert outdated.json()["error"]["code"] == "consent_document_outdated"

    consent_record_id = await _accept_consent(
        client, auth_headers, key_suffix="required-contract"
    )
    scan = await client.post(
        "/v2/scan-sessions",
        headers=_idempotent(auth_headers, "consent-required-scan-001"),
        json={
            "protocol": "standard_eight_region",
            "deviceId": None,
            "consentRecordId": consent_record_id,
        },
    )
    assert scan.status_code == 201, scan.text
    assert scan.json()["consentRecordId"] == consent_record_id

    revoke_headers = _idempotent(auth_headers, "consent-revoke-record-001")
    revoked = await client.post(
        f"/v2/consents/{consent_record_id}/revoke",
        headers=revoke_headers,
        json={"confirmation": "REVOKE"},
    )
    replay = await client.post(
        f"/v2/consents/{consent_record_id}/revoke",
        headers=revoke_headers,
        json={"confirmation": "REVOKE"},
    )
    assert revoked.status_code == replay.status_code == 200
    assert revoked.json() == replay.json()
    assert revoked.json()["active"] is False

    blocked = await client.post(
        "/v2/scan-sessions",
        headers=_idempotent(auth_headers, "consent-revoked-scan-001"),
        json={
            "protocol": "standard_eight_region",
            "deviceId": None,
            "consentRecordId": consent_record_id,
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "active_product_consent_required"
    retained = await client.get(
        f"/v2/scan-sessions/{scan.json()['scanSessionId']}",
        headers=auth_headers(),
    )
    assert retained.status_code == 200

    replacement = await _accept_consent(
        client, auth_headers, key_suffix="replacement-contract"
    )
    assert replacement != consent_record_id


async def test_delete_request_immediately_closes_account_access(
    client, app, auth_headers
) -> None:
    capture = await _create_scan(
        client,
        auth_headers,
        key_suffix="delete-access",
        sha256=SHA_A,
    )

    clinician_subject = "auth0|delete-access-clinician"
    clinician_headers = auth_headers(clinician_subject, ("clinician",))
    clinician_me = await client.get("/v2/me", headers=clinician_headers)
    assert clinician_me.status_code == 200
    clinician_id = clinician_me.json()["id"]
    now = utc_now()
    async with app.state.database.sessions() as session:
        clinician = await session.get(User, clinician_id)
        assert clinician is not None
        clinician.role = UserRole.CLINICIAN
        session.add(
            ClinicianVerification(
                user_id=clinician_id,
                status=ClinicianVerificationStatus.VERIFIED,
                profession="dentist",
                license_jurisdiction="NJ",
                license_number_sha256=SHA_A,
                license_number_suffix="1234",
                organization="Deletion guard test clinic",
                applicant_evidence_ref="test-evidence",
                submitted_at=now,
                reviewer_evidence={"source": "test"},
                reviewed_at=now,
                retention_expires_at=now + timedelta(days=365),
            )
        )
        await session.commit()

    grant = await client.post(
        "/v2/access-grants",
        headers=_idempotent(auth_headers, "delete-access-grant-001"),
        json={
            "clinicianUserId": clinician_id,
            "resources": [
                {
                    "resourceType": "scan_session",
                    "resourceId": capture["scan_id"],
                }
            ],
            "label": "Deletion guard",
            "expiresAt": None,
        },
    )
    assert grant.status_code == 201, grant.text

    share = await client.post(
        "/v2/shares",
        headers=_idempotent(auth_headers, "delete-access-share-001"),
        json={
            "resources": [
                {
                    "resourceType": "scan_session",
                    "resourceId": capture["scan_id"],
                }
            ],
            "expiresInSeconds": 3600,
            "maxExchanges": 2,
        },
    )
    assert share.status_code == 201, share.text
    share_body = share.json()
    share_id = share_body["share"]["shareId"]
    fragment_secret = share_body["fragmentSecret"]

    exchange = await client.post(
        "/v2/share-exchanges",
        headers={"Idempotency-Key": "delete-access-exchange-01"},
        json={"shareId": share_id, "secret": fragment_secret},
    )
    assert exchange.status_code == 200, exchange.text
    exchange_token = exchange.json()["exchangeToken"]
    before_delete = await client.get(
        "/v2/share-viewer/resources",
        headers={"Authorization": f"Share {exchange_token}"},
    )
    assert before_delete.status_code == 200, before_delete.text

    delete_headers = {
        **auth_headers(),
        "Idempotency-Key": "delete-access-request-001",
    }
    deletion = await client.post(
        "/v2/me/deletion-requests",
        headers=delete_headers,
        json={"confirmation": "DELETE"},
    )
    assert deletion.status_code == 202, deletion.text

    me = await client.get("/v2/me", headers=auth_headers())
    assert me.status_code == 200
    assert me.json()["deletionPending"] is True
    replay = await client.post(
        "/v2/me/deletion-requests",
        headers=delete_headers,
        json={"confirmation": "DELETE"},
    )
    assert replay.status_code == 202
    assert replay.json() == deletion.json()
    status_response = await client.get(
        f"/v2/me/deletion-requests/{deletion.json()['requestId']}",
        headers=auth_headers(),
    )
    assert status_response.status_code == 200
    assert status_response.json() == deletion.json()

    blocked_share = await client.post(
        "/v2/shares",
        headers=_idempotent(auth_headers, "delete-access-share-002"),
        json={
            "resources": [
                {
                    "resourceType": "scan_session",
                    "resourceId": capture["scan_id"],
                }
            ],
            "expiresInSeconds": 3600,
            "maxExchanges": 1,
        },
    )
    assert blocked_share.status_code == 403
    assert blocked_share.json()["error"]["code"] == "account_deletion_pending"

    blocked_scan = await client.post(
        "/v2/scan-sessions",
        headers=_idempotent(auth_headers, "delete-access-scan-001"),
        json={
            "protocol": "standard_eight_region",
            "deviceId": None,
            "consentRecordId": capture["consent_record_id"],
        },
    )
    assert blocked_scan.status_code == 403
    assert blocked_scan.json()["error"]["code"] == "account_deletion_pending"

    blocked_read = await client.get("/v2/consents", headers=auth_headers())
    assert blocked_read.status_code == 403
    assert blocked_read.json()["error"]["code"] == "account_deletion_pending"

    new_exchange = await client.post(
        "/v2/share-exchanges",
        headers={"Idempotency-Key": "delete-access-exchange-02"},
        json={"shareId": share_id, "secret": fragment_secret},
    )
    assert new_exchange.status_code == 410
    assert new_exchange.json()["error"]["code"] == "share_expired"
    old_exchange = await client.get(
        "/v2/share-viewer/resources",
        headers={"Authorization": f"Share {exchange_token}"},
    )
    assert old_exchange.status_code == 401
    assert old_exchange.json()["error"]["code"] == "invalid_share_token"

    async with app.state.database.sessions() as session:
        consent = await session.get(ConsentRecord, capture["consent_record_id"])
        stored_share = await session.get(ShareLink, share_id)
        token = await session.scalar(
            select(ShareExchangeToken).where(ShareExchangeToken.share_id == share_id)
        )
        stored_grant = await session.get(ClinicianAccessGrant, grant.json()["grantId"])
        assert consent is not None and consent.revoked_at is not None
        assert stored_share is not None
        assert stored_share.status is ShareLinkStatus.REVOKED
        assert stored_share.revoked_at is not None
        assert token is not None and token.revoked_at is not None
        assert stored_grant is not None
        assert stored_grant.status is AccessGrantStatus.REVOKED
        assert stored_grant.revoked_at is not None


async def test_clinician_annotations_cover_structured_review_corrections(
    client, app, auth_headers
) -> None:
    clinician_headers = auth_headers("auth0|annotation-clinician", ("clinician",))
    clinician_me = await client.get("/v2/me", headers=clinician_headers)
    assert clinician_me.status_code == 200
    clinician_id = clinician_me.json()["id"]
    now = utc_now()
    async with app.state.database.sessions() as session:
        clinician = await session.get(User, clinician_id)
        clinician.role = UserRole.CLINICIAN
        session.add(
            ClinicianVerification(
                user_id=clinician_id,
                status=ClinicianVerificationStatus.VERIFIED,
                profession="dentist",
                license_jurisdiction="NJ",
                license_number_sha256=SHA_A,
                license_number_suffix="1234",
                organization="Test clinic",
                applicant_evidence_ref="test-evidence",
                submitted_at=now,
                reviewer_evidence={"source": "test"},
                reviewed_at=now,
                retention_expires_at=now + timedelta(days=365),
            )
        )
        await session.commit()

    capture = await _create_scan(
        client,
        auth_headers,
        key_suffix="clinician-annotation",
        sha256=hashlib.sha256(
            b"\xff\xd8\xff\xe0" + b"capture-image".ljust(2042, b".") + b"\xff\xd9"
        ).hexdigest(),
    )
    analysis = await _create_analysis(
        client,
        auth_headers,
        capture,
        key_suffix="clinician-annotation",
    )
    capture_bytes = (
        b"\xff\xd8\xff\xe0" + b"capture-image".ljust(2042, b".") + b"\xff\xd9"
    )
    assert len(capture_bytes) == 2048
    async with app.state.database.sessions() as session:
        asset = await session.get(CaptureAsset, capture["asset_id"])
        assert asset is not None
        await app.state.object_storage.put_bytes(
            asset.object_key,
            capture_bytes,
            media_type=asset.media_type,
            sha256=asset.content_sha256,
        )
        asset.status = CaptureStatus.AVAILABLE
        await session.commit()
    grant = await client.post(
        "/v2/access-grants",
        headers=_idempotent(auth_headers, "annotation-access-grant-001"),
        json={
            "clinicianUserId": clinician_id,
            "resources": [
                {
                    "resourceType": "scan_session",
                    "resourceId": capture["scan_id"],
                },
                {
                    "resourceType": "analysis_run",
                    "resourceId": analysis["analysis_id"],
                },
            ],
            "label": "Review correction test",
            "expiresAt": None,
        },
    )
    assert grant.status_code == 201, grant.text
    review_id = grant.json()["reviewId"]
    kinds = [
        "outline_adjustment",
        "location_correction",
        "insufficient_scan",
        "date_comparison",
    ]
    for index, kind in enumerate(kinds):
        response = await client.post(
            f"/v2/clinician/reviews/{review_id}/annotations",
            headers={
                **clinician_headers,
                "Idempotency-Key": f"annotation-{kind}-{index:04d}",
            },
            json={
                "resource": {
                    "resourceType": "scan_session",
                    "resourceId": capture["scan_id"],
                },
                "kind": kind,
                "body": f"Structured review note for {kind}.",
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["kind"] == kind

    review = await client.get(
        f"/v2/clinician/reviews/{review_id}", headers=clinician_headers
    )
    assert review.status_code == 200, review.text
    assert {item["kind"] for item in review.json()["annotations"]} == set(kinds)
    rejected = await client.post(
        f"/v2/clinician/reviews/{review_id}/annotations",
        headers={
            **clinician_headers,
            "Idempotency-Key": "annotation-mask-replacement-0001",
        },
        json={
            "resource": {
                "resourceType": "scan_session",
                "resourceId": capture["scan_id"],
            },
            "kind": "mask_replacement",
            "body": "This unsupported operation must not mutate a learned mask.",
        },
    )
    assert rejected.status_code == 422

    image = await client.get(
        f"/v2/clinician/reviews/{review_id}/capture-views/{capture['view_id']}/content",
        headers=clinician_headers,
    )
    assert image.status_code == 200, image.text
    assert image.content == capture_bytes
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "no-store"
    assert image.headers["x-content-type-options"] == "nosniff"

    unshared_capture = await _create_scan(
        client,
        auth_headers,
        key_suffix="clinician-annotation-unshared",
        region="right_buccal_mucosa",
        sha256=SHA_B,
    )
    unshared_analysis = await _create_analysis(
        client,
        auth_headers,
        unshared_capture,
        key_suffix="clinician-annotation-unshared",
    )
    assert unshared_analysis["analysis_id"] != analysis["analysis_id"]
    hidden_image = await client.get(
        f"/v2/clinician/reviews/{review_id}/capture-views/{unshared_capture['view_id']}/content",
        headers=clinician_headers,
    )
    assert hidden_image.status_code == 404


async def test_capture_flow_is_owner_scoped_strict_and_idempotent(
    client, auth_headers
) -> None:
    consent_record_id = await _accept_consent(
        client, auth_headers, key_suffix="capture-idempotent"
    )
    headers = _idempotent(auth_headers, "scan-session-idempotent-001")
    first = await client.post(
        "/v2/scan-sessions",
        headers=headers,
        json={
            "protocol": "standard_eight_region",
            "deviceId": None,
            "consentRecordId": consent_record_id,
        },
    )
    replay = await client.post(
        "/v2/scan-sessions",
        headers=headers,
        json={
            "protocol": "standard_eight_region",
            "deviceId": None,
            "consentRecordId": consent_record_id,
        },
    )
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()

    conflict = await client.post(
        "/v2/scan-sessions",
        headers=headers,
        json={
            "protocol": "detailed_multi_angle",
            "deviceId": None,
            "consentRecordId": consent_record_id,
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"

    capture = await _create_scan(client, auth_headers, key_suffix="owner-scope")
    denied = await client.get(
        f"/v2/capture-sets/{capture['capture_set_id']}",
        headers=auth_headers("auth0|other-account"),
    )
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "resource_not_found"

    malformed = await client.post(
        f"/v2/scan-sessions/{capture['scan_id']}/capture-sets",
        headers=_idempotent(auth_headers, "capture-invalid-region-01"),
        json={"region": "not_a_mouth_region", "protocol": "standard_eight_region"},
    )
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "invalid_request"

    rejected = await client.post(
        f"/v2/capture-sets/{capture['capture_set_id']}/views",
        headers=_idempotent(auth_headers, "capture-rejected-view-01"),
        json={
            "angle": "primary",
            "asset": {
                "mediaKind": "image",
                "mimeType": "image/jpeg",
                "byteSize": 10,
                "sha256": SHA_B,
                "widthPx": 10,
                "heightPx": 10,
                "durationMs": None,
                "inputOrigin": "live_capture",
                "encrypted": True,
                "retentionExpiresAt": None,
            },
            "sourceVideoAssetId": None,
            "qualityAccepted": False,
            "qualityReasons": ["private-rejection-detail"],
            "ordinal": 1,
            "capturedAt": datetime.now(UTC).isoformat(),
            "makePrimary": False,
        },
    )
    assert rejected.status_code == 422
    assert "private-rejection-detail" not in rejected.text

    second_accepted = await client.post(
        f"/v2/capture-sets/{capture['capture_set_id']}/views",
        headers=_idempotent(auth_headers, "capture-second-standard-01"),
        json={
            "angle": "primary",
            "anatomicalSite": "left_buccal_mucosa",
            "asset": {
                "mediaKind": "image",
                "mimeType": "image/jpeg",
                "byteSize": 10,
                "sha256": SHA_B,
                "widthPx": 10,
                "heightPx": 10,
                "durationMs": None,
                "inputOrigin": "live_capture",
                "encrypted": True,
                "retentionExpiresAt": None,
            },
            "sourceVideoAssetId": None,
            "qualityAccepted": True,
            "qualityReasons": [],
            "ordinal": 1,
            "capturedAt": datetime.now(UTC).isoformat(),
            "makePrimary": False,
        },
    )
    assert second_accepted.status_code == 409
    assert second_accepted.json()["error"]["code"] == "standard_capture_already_exists"


async def test_detailed_sweep_retains_three_frames_and_only_then_completes(
    client, auth_headers
) -> None:
    consent_record_id = await _accept_consent(
        client, auth_headers, key_suffix="detailed-sweep"
    )
    scan = await client.post(
        "/v2/scan-sessions",
        headers=_idempotent(auth_headers, "detailed-scan-session-001"),
        json={
            "protocol": "guided_video_sweep",
            "deviceId": None,
            "consentRecordId": consent_record_id,
        },
    )
    scan_id = scan.json()["scanSessionId"]
    capture_set = await client.post(
        f"/v2/scan-sessions/{scan_id}/capture-sets",
        headers=_idempotent(auth_headers, "detailed-capture-set-001"),
        json={
            "region": "right_buccal_mucosa",
            "protocol": "guided_video_sweep",
        },
    )
    capture_set_id = capture_set.json()["captureSetId"]
    video = await client.post(
        f"/v2/capture-sets/{capture_set_id}/assets",
        headers=_idempotent(auth_headers, "detailed-video-asset-001"),
        json={
            "mediaKind": "video",
            "mimeType": "video/mp4",
            "byteSize": 8192,
            "sha256": "d" * 64,
            "widthPx": 1920,
            "heightPx": 1080,
            "durationMs": 3500,
            "inputOrigin": "live_capture",
            "encrypted": True,
            "retentionExpiresAt": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert video.status_code == 201, video.text
    video_id = video.json()["assetId"]
    hashes = [SHA_A, SHA_B, SHA_C]
    angles = ["straight", "left_oblique", "right_oblique"]
    latest = None
    for ordinal, (angle, frame_hash) in enumerate(zip(angles, hashes, strict=True)):
        latest = await client.post(
            f"/v2/capture-sets/{capture_set_id}/views",
            headers=_idempotent(auth_headers, f"detailed-frame-{ordinal:04d}"),
            json={
                "angle": angle,
                "anatomicalSite": "right_buccal_mucosa",
                "asset": {
                    "mediaKind": "video_frame",
                    "mimeType": "image/jpeg",
                    "byteSize": 2048,
                    "sha256": frame_hash,
                    "widthPx": 1024,
                    "heightPx": 768,
                    "durationMs": None,
                    "inputOrigin": "live_capture",
                    "encrypted": True,
                    "retentionExpiresAt": None,
                },
                "sourceVideoAssetId": video_id,
                "qualityAccepted": True,
                "qualityReasons": [],
                "ordinal": ordinal,
                "capturedAt": datetime.now(UTC).isoformat(),
                "makePrimary": ordinal == 0,
            },
        )
        assert latest.status_code == 201, latest.text
        assert latest.json()["complete"] is (ordinal == 2)
    assert latest is not None and len(latest.json()["views"]) == 3
    assert {value["angle"] for value in latest.json()["views"]} == {
        "straight",
        "left_oblique",
        "right_oblique",
    }

    fetched_scan = await client.get(
        f"/v2/scan-sessions/{scan_id}", headers=auth_headers()
    )
    fetched_asset = await client.get(
        f"/v2/capture-assets/{video_id}", headers=auth_headers()
    )
    assert fetched_scan.status_code == fetched_asset.status_code == 200
    assert fetched_asset.json()["mediaKind"] == "video"

    wrong_asset = await client.post(
        f"/v2/capture-sets/{capture_set_id}/assets",
        headers=_idempotent(auth_headers, "detailed-wrong-asset-001"),
        json={
            "mediaKind": "image",
            "mimeType": "image/jpeg",
            "byteSize": 100,
            "sha256": "e" * 64,
            "widthPx": 100,
            "heightPx": 100,
            "durationMs": None,
            "inputOrigin": "live_capture",
            "encrypted": True,
            "retentionExpiresAt": None,
        },
    )
    assert wrong_asset.status_code == 422
    assert wrong_asset.json()["error"]["code"] == "standalone_asset_not_video"


async def test_analysis_enforces_live_provenance_and_calibration_evidence(
    client, app, auth_headers
) -> None:
    capture = await _create_scan(client, auth_headers, key_suffix="analysis-calibrated")
    analysis = await _create_analysis(
        client,
        auth_headers,
        capture,
        key_suffix="analysis-calibrated",
        calibrated=True,
    )
    result = analysis["response"]
    assert result["persisted"] is True
    assert result["analysisOrigin"] == "live_model"
    assert result["disclaimer"] == "This result is not a diagnosis."
    assert result["observations"][0]["calibration"]["estimatedWidthMm"] == 3.5

    async with app.state.database.sessions() as session:
        observation = await session.scalar(select(CandidateObservation))
        assert observation is not None
        assert observation.estimated_width_mm == 3.5
        assert observation.calibration_evidence_sha256 is not None

    now = datetime.now(UTC)
    fixture_on_live = await client.post(
        f"/v2/capture-sets/{capture['capture_set_id']}/analysis-runs",
        headers=_idempotent(auth_headers, "analysis-fixture-live-001"),
        json={
            "requestedHeads": ["segmentation"],
            "status": "abstained",
            "observations": [],
            "inputOrigin": "live_capture",
            "analysisOrigin": "manual_fixture",
            "sourceAssetSha256": [capture["sha256"]],
            "modelVersions": {"segmentation": "fixture"},
            "artifactHashes": {},
            "abstentionReasons": ["Fixture not allowed."],
            "startedAt": now.isoformat(),
            "completedAt": None,
            "signedEnvelopeId": "fixture-envelope",
        },
    )
    assert fixture_on_live.status_code == 422
    assert fixture_on_live.json()["error"]["code"] == "invalid_request"

    unavailable = await client.post(
        f"/v2/capture-sets/{capture['capture_set_id']}/analysis-runs",
        headers=_idempotent(auth_headers, "analysis-unavailable-001"),
        json={
            "requestedHeads": ["segmentation"],
            "status": "failed",
            "observations": [],
            "inputOrigin": "live_capture",
            "analysisOrigin": "unavailable",
            "sourceAssetSha256": [capture["sha256"]],
            "modelVersions": {"segmentation": "unavailable"},
            "artifactHashes": {},
            "abstentionReasons": ["Service unavailable."],
            "startedAt": now.isoformat(),
            "completedAt": None,
            "signedEnvelopeId": "unavailable-envelope",
        },
    )
    assert unavailable.status_code == 422

    invalid_calibration = _observation(capture["view_id"])
    invalid_calibration["calibration"] = {
        "status": "invalid",
        "method": "versioned_reference_card",
        "cardVersion": None,
        "markerId": None,
        "referenceWidthMm": None,
        "millimetersPerPixel": None,
        "estimatedWidthMm": 8.0,
        "estimatedHeightMm": None,
        "estimatedAreaMm2": None,
        "confidence": None,
        "gateReasons": ["pose_failed"],
        "calibratedAt": None,
        "modelVersions": {},
        "measurementLabel": "calibrated estimate",
    }
    bad_measurement = await client.post(
        f"/v2/capture-sets/{capture['capture_set_id']}/analysis-runs",
        headers=_idempotent(auth_headers, "analysis-bad-calibration-01"),
        json={
            "requestedHeads": ["segmentation"],
            "status": "complete",
            "observations": [invalid_calibration],
            "inputOrigin": "live_capture",
            "analysisOrigin": "live_model",
            "sourceAssetSha256": [capture["sha256"]],
            "modelVersions": {"segmentation": "seg-v1"},
            "artifactHashes": {"segmentation": SHA_C},
            "abstentionReasons": [],
            "startedAt": now.isoformat(),
            "completedAt": now.isoformat(),
            "signedEnvelopeId": "bad-calibration-envelope",
        },
    )
    assert bad_measurement.status_code == 422

    wrong_hash = await client.post(
        f"/v2/capture-sets/{capture['capture_set_id']}/analysis-runs",
        headers=_idempotent(auth_headers, "analysis-wrong-source-hash-1"),
        json={
            "requestedHeads": ["segmentation"],
            "status": "abstained",
            "observations": [],
            "inputOrigin": "live_capture",
            "analysisOrigin": "live_model",
            "sourceAssetSha256": [SHA_B],
            "modelVersions": {"segmentation": "seg-v1"},
            "artifactHashes": {"segmentation": SHA_C},
            "abstentionReasons": ["No supported candidate."],
            "startedAt": now.isoformat(),
            "completedAt": None,
            "signedEnvelopeId": "wrong-source-envelope",
        },
    )
    assert wrong_hash.status_code == 422
    assert wrong_hash.json()["error"]["code"] == "source_asset_mismatch"

    abstained = await client.post(
        f"/v2/capture-sets/{capture['capture_set_id']}/analysis-runs",
        headers=_idempotent(auth_headers, "analysis-abstained-valid-01"),
        json={
            "requestedHeads": ["segmentation"],
            "status": "abstained",
            "observations": [],
            "inputOrigin": "live_capture",
            "analysisOrigin": "live_model",
            "sourceAssetSha256": [capture["sha256"]],
            "modelVersions": {"segmentation": "seg-v1"},
            "artifactHashes": {"segmentation": SHA_C},
            "abstentionReasons": ["No supported candidate."],
            "startedAt": now.isoformat(),
            "completedAt": None,
            "signedEnvelopeId": "abstained-envelope",
        },
    )
    assert abstained.status_code == 201, abstained.text
    fetched = await client.get(
        f"/v2/analysis-runs/{abstained.json()['analysisRunId']}",
        headers=auth_headers(),
    )
    assert fetched.status_code == 200
    assert fetched.json()["observations"] == []

    wrong_origin = await client.post(
        f"/v2/capture-sets/{capture['capture_set_id']}/analysis-runs",
        headers=_idempotent(auth_headers, "analysis-origin-mismatch-01"),
        json={
            "requestedHeads": ["segmentation"],
            "status": "abstained",
            "observations": [],
            "inputOrigin": "bundled_demo",
            "analysisOrigin": "live_model",
            "sourceAssetSha256": [capture["sha256"]],
            "modelVersions": {"segmentation": "seg-v1"},
            "artifactHashes": {"segmentation": SHA_C},
            "abstentionReasons": ["Origin does not match."],
            "startedAt": now.isoformat(),
            "completedAt": None,
            "signedEnvelopeId": "origin-mismatch-envelope",
        },
    )
    assert wrong_origin.status_code == 422
    assert wrong_origin.json()["error"]["code"] == "input_origin_mismatch"


async def test_incomplete_capture_cannot_be_analyzed_and_regions_cannot_cross_match(
    client, auth_headers
) -> None:
    consent_record_id = await _accept_consent(
        client, auth_headers, key_suffix="incomplete-analysis"
    )
    scan = await client.post(
        "/v2/scan-sessions",
        headers=_idempotent(auth_headers, "incomplete-analysis-scan-01"),
        json={
            "protocol": "standard_eight_region",
            "deviceId": None,
            "consentRecordId": consent_record_id,
        },
    )
    capture_set = await client.post(
        f"/v2/scan-sessions/{scan.json()['scanSessionId']}/capture-sets",
        headers=_idempotent(auth_headers, "incomplete-analysis-set-001"),
        json={"region": "upper_lip", "protocol": "standard_eight_region"},
    )
    now = datetime.now(UTC)
    incomplete = await client.post(
        f"/v2/capture-sets/{capture_set.json()['captureSetId']}/analysis-runs",
        headers=_idempotent(auth_headers, "incomplete-analysis-run-001"),
        json={
            "requestedHeads": ["segmentation"],
            "status": "abstained",
            "observations": [],
            "inputOrigin": "live_capture",
            "analysisOrigin": "live_model",
            "sourceAssetSha256": [SHA_A],
            "modelVersions": {"segmentation": "seg-v1"},
            "artifactHashes": {"segmentation": SHA_C},
            "abstentionReasons": ["Capture incomplete."],
            "startedAt": now.isoformat(),
            "completedAt": None,
            "signedEnvelopeId": "incomplete-envelope",
        },
    )
    assert incomplete.status_code == 409
    assert incomplete.json()["error"]["code"] == "capture_set_incomplete"

    left_capture = await _create_scan(
        client,
        auth_headers,
        key_suffix="cross-region-left",
        region="left_buccal_mucosa",
    )
    left = await _create_analysis(
        client, auth_headers, left_capture, key_suffix="cross-region-left"
    )
    lip_capture = await _create_scan(
        client,
        auth_headers,
        key_suffix="cross-region-lip",
        region="upper_lip",
        sha256=SHA_B,
    )
    lip_observation = _observation(lip_capture["view_id"])
    lip_observation["anatomicalSite"] = "upper_labial_mucosa"
    lip_analysis = await client.post(
        f"/v2/capture-sets/{lip_capture['capture_set_id']}/analysis-runs",
        headers=_idempotent(auth_headers, "cross-region-lip-analysis-1"),
        json={
            "requestedHeads": ["segmentation"],
            "status": "complete",
            "observations": [lip_observation],
            "inputOrigin": "live_capture",
            "analysisOrigin": "live_model",
            "sourceAssetSha256": [SHA_B],
            "modelVersions": {"segmentation": "seg-v1"},
            "artifactHashes": {"segmentation": SHA_C},
            "abstentionReasons": [],
            "startedAt": now.isoformat(),
            "completedAt": now.isoformat(),
            "signedEnvelopeId": "cross-region-lip-envelope",
        },
    )
    cross_match = await client.post(
        "/v2/match-proposals",
        headers=_idempotent(auth_headers, "cross-region-proposal-01"),
        json={
            "currentObservationId": lip_analysis.json()["observations"][0][
                "observationId"
            ],
            "candidatePriorObservationId": left["observation_id"],
            "candidateLesionId": None,
            "score": 0.8,
            "rank": 1,
            "modelVersions": {"reidentification": "reid-v1"},
            "expiresAt": None,
        },
    )
    assert cross_match.status_code == 422
    assert cross_match.json()["error"]["code"] == "region_mismatch"


async def test_match_proposal_never_links_until_explicit_confirmation(
    client, app, auth_headers
) -> None:
    baseline_capture = await _create_scan(
        client, auth_headers, key_suffix="match-baseline", sha256=SHA_A
    )
    baseline = await _create_analysis(
        client, auth_headers, baseline_capture, key_suffix="match-baseline"
    )
    current_capture = await _create_scan(
        client, auth_headers, key_suffix="match-current", sha256=SHA_B
    )
    current = await _create_analysis(
        client, auth_headers, current_capture, key_suffix="match-current"
    )
    proposal = await client.post(
        "/v2/match-proposals",
        headers=_idempotent(auth_headers, "match-proposal-confirm-01"),
        json={
            "currentObservationId": current["observation_id"],
            "candidatePriorObservationId": baseline["observation_id"],
            "candidateLesionId": None,
            "score": 0.97,
            "rank": 1,
            "modelVersions": {"reidentification": "reid-v1"},
            "expiresAt": None,
        },
    )
    assert proposal.status_code == 201, proposal.text
    assert proposal.json()["automaticallyConfirmed"] is False
    async with app.state.database.sessions() as session:
        assert await session.scalar(select(func.count(LesionRecord.id))) == 0
        assert await session.scalar(select(func.count(LesionObservationLink.id))) == 0

    decision_headers = _idempotent(auth_headers, "match-decision-confirm-01")
    confirmed = await client.post(
        f"/v2/match-proposals/{proposal.json()['proposalId']}/decisions",
        headers=decision_headers,
        json={"decision": "confirmed", "rationale": "These are the same area."},
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["decision"] == "confirmed"
    assert confirmed.json()["lesionId"] is not None
    replay = await client.post(
        f"/v2/match-proposals/{proposal.json()['proposalId']}/decisions",
        headers=decision_headers,
        json={"decision": "confirmed", "rationale": "These are the same area."},
    )
    assert replay.json() == confirmed.json()

    lesion = await client.get(
        f"/v2/lesions/{confirmed.json()['lesionId']}", headers=auth_headers()
    )
    assert lesion.status_code == 200
    assert lesion.json()["confirmedObservationIds"] == [
        baseline["observation_id"],
        current["observation_id"],
    ]
    assert lesion.json()["matchDecisionIds"] == [confirmed.json()["decisionId"]]

    second = await client.post(
        f"/v2/match-proposals/{proposal.json()['proposalId']}/decisions",
        headers=_idempotent(auth_headers, "match-decision-second-001"),
        json={"decision": "rejected", "rationale": None},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "proposal_already_decided"

    denied = await client.get(
        f"/v2/match-proposals/{proposal.json()['proposalId']}",
        headers=auth_headers("auth0|other-account"),
    )
    assert denied.status_code == 404


async def test_user_selected_pair_records_confirmation_without_model_evidence(
    client, auth_headers
) -> None:
    baseline_capture = await _create_scan(
        client, auth_headers, key_suffix="manual-pair-baseline", sha256=SHA_A
    )
    baseline = await _create_analysis(
        client, auth_headers, baseline_capture, key_suffix="manual-pair-baseline"
    )
    current_capture = await _create_scan(
        client, auth_headers, key_suffix="manual-pair-current", sha256=SHA_B
    )
    current = await _create_analysis(
        client, auth_headers, current_capture, key_suffix="manual-pair-current"
    )
    body = {
        "currentObservationId": current["observation_id"],
        "candidatePriorObservationId": baseline["observation_id"],
        "candidateLesionId": None,
        "proposalOrigin": "user_selected",
        "score": None,
        "rank": None,
        "modelVersions": {},
        "expiresAt": None,
    }
    proposal = await client.post(
        "/v2/match-proposals",
        headers=_idempotent(auth_headers, "manual-pair-proposal-001"),
        json=body,
    )
    assert proposal.status_code == 201, proposal.text
    assert proposal.json()["proposalOrigin"] == "user_selected"
    assert proposal.json()["score"] is None
    assert proposal.json()["rank"] is None
    assert proposal.json()["modelVersions"] == {}
    invalid_evidence = await client.post(
        "/v2/match-proposals",
        headers=_idempotent(auth_headers, "manual-pair-invalid-001"),
        json={**body, "score": 0.99},
    )
    assert invalid_evidence.status_code == 422

    decision = await client.post(
        f"/v2/match-proposals/{proposal.json()['proposalId']}/decisions",
        headers=_idempotent(auth_headers, "manual-pair-decision-001"),
        json={
            "decision": "confirmed",
            "rationale": "Selected and confirmed by the user.",
        },
    )
    assert decision.status_code == 201, decision.text
    assert decision.json()["lesionId"] is not None


async def test_existing_lesion_requires_a_deferred_then_explicit_confirmed_decision(
    client, auth_headers
) -> None:
    baseline_capture = await _create_scan(
        client, auth_headers, key_suffix="existing-lesion-base", sha256=SHA_A
    )
    baseline = await _create_analysis(
        client, auth_headers, baseline_capture, key_suffix="existing-lesion-base"
    )
    current_capture = await _create_scan(
        client, auth_headers, key_suffix="existing-lesion-current", sha256=SHA_B
    )
    current = await _create_analysis(
        client, auth_headers, current_capture, key_suffix="existing-lesion-current"
    )
    lesion = await client.post(
        "/v2/lesions",
        headers=_idempotent(auth_headers, "manual-lesion-create-001"),
        json={
            "firstObservationId": baseline["observation_id"],
            "label": "Area to track",
        },
    )
    assert lesion.status_code == 201
    lesion_id = lesion.json()["lesionId"]
    proposal = await client.post(
        "/v2/match-proposals",
        headers=_idempotent(auth_headers, "existing-lesion-proposal-1"),
        json={
            "currentObservationId": current["observation_id"],
            "candidatePriorObservationId": baseline["observation_id"],
            "candidateLesionId": lesion_id,
            "score": 0.96,
            "rank": 1,
            "modelVersions": {"reidentification": "reid-v1"},
            "expiresAt": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    deferred = await client.post(
        f"/v2/match-proposals/{proposal.json()['proposalId']}/decisions",
        headers=_idempotent(auth_headers, "existing-lesion-defer-001"),
        json={"decision": "deferred", "rationale": "Review later."},
    )
    assert deferred.status_code == 201
    assert deferred.json()["lesionId"] is None
    still_one = await client.get(f"/v2/lesions/{lesion_id}", headers=auth_headers())
    assert still_one.json()["confirmedObservationIds"] == [baseline["observation_id"]]

    confirmed = await client.post(
        f"/v2/match-proposals/{proposal.json()['proposalId']}/decisions",
        headers=_idempotent(auth_headers, "existing-lesion-confirm-01"),
        json={"decision": "confirmed", "rationale": "Confirmed after review."},
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["lesionId"] == lesion_id
    fetched_decision = await client.get(
        f"/v2/match-decisions/{confirmed.json()['decisionId']}",
        headers=auth_headers(),
    )
    assert fetched_decision.json() == confirmed.json()


async def test_reports_and_jobs_are_owner_scoped_and_idempotent(
    client, app, auth_headers
) -> None:
    capture = await _create_scan(client, auth_headers, key_suffix="report-job")
    analysis = await _create_analysis(
        client, auth_headers, capture, key_suffix="report-job"
    )
    report_payload = {
        "scanSessionIds": [capture["scan_id"]],
        "format": "pdf",
        "assetId": "report-file-report-job",
        "sha256": SHA_B,
        "byteSize": 4096,
        "locale": "en-US",
        "accessible": True,
        "inputOrigins": ["live_capture"],
        "analysisOrigins": ["live_model"],
        "modelVersions": {"report": "1.0.0"},
        "signedEnvelopeId": "signed-report-envelope",
        "retentionExpiresAt": None,
    }
    headers = _idempotent(auth_headers, "report-create-idempotent-01")
    report = await client.post("/v2/reports", headers=headers, json=report_payload)
    replay = await client.post("/v2/reports", headers=headers, json=report_payload)
    assert report.status_code == replay.status_code == 201
    assert report.json() == replay.json()

    job = await client.post(
        "/v2/jobs",
        headers=_idempotent(auth_headers, "job-create-report-0001"),
        json={
            "type": "report",
            "inputRefs": [
                capture["scan_id"],
                capture["consent_record_id"],
                analysis["observation_id"],
            ],
            "payload": {
                "scanSessionId": capture["scan_id"],
                "consentRecordId": capture["consent_record_id"],
                "observationIds": [analysis["observation_id"]],
                "comparisonIds": [],
                "locale": "en-US",
                "includeExperimentalResearchOutput": False,
                "disclaimer": "This result is not a diagnosis.",
            },
            "maxAttempts": 3,
        },
    )
    assert job.status_code == 201, job.text
    assert job.json()["status"] == "queued"
    assert job.json()["progress"] == 0
    fetched_job = await client.get(
        f"/v2/jobs/{job.json()['jobId']}", headers=auth_headers()
    )
    assert fetched_job.json() == job.json()

    denied = await client.get(
        f"/v2/reports/{report.json()['reportArtifactId']}",
        headers=auth_headers("auth0|other-account"),
    )
    assert denied.status_code == 404
    bad_ref = await client.post(
        "/v2/jobs",
        headers=_idempotent(
            auth_headers, "job-other-resource-001", "auth0|other-account"
        ),
        json={
            "type": "report",
            "inputRefs": [
                capture["scan_id"],
                capture["consent_record_id"],
                analysis["observation_id"],
            ],
            "payload": {
                "scanSessionId": capture["scan_id"],
                "consentRecordId": capture["consent_record_id"],
                "observationIds": [analysis["observation_id"]],
                "comparisonIds": [],
                "locale": "en-US",
                "includeExperimentalResearchOutput": False,
                "disclaimer": "This result is not a diagnosis.",
            },
            "maxAttempts": 3,
        },
    )
    assert bad_ref.status_code == 404
    internal_job = await client.post(
        "/v2/jobs",
        headers=_idempotent(auth_headers, "job-account-delete-invalid-1"),
        json={"type": "account_deletion", "inputRefs": [], "maxAttempts": 1},
    )
    assert internal_job.status_code == 422

    mixed_fixture_report = dict(report_payload)
    mixed_fixture_report["assetId"] = "report-mixed-fixture"
    mixed_fixture_report["analysisOrigins"] = ["manual_fixture"]
    mixed_fixture_report["inputOrigins"] = ["live_capture"]
    invalid_report = await client.post(
        "/v2/reports",
        headers=_idempotent(auth_headers, "report-mixed-fixture-001"),
        json=mixed_fixture_report,
    )
    assert invalid_report.status_code == 422
    async with app.state.database.sessions() as session:
        assert await session.scalar(select(func.count(ReportArtifact.id))) == 1


async def test_openapi_contains_product_routes(app) -> None:
    schema = app.openapi()
    paths = set(schema["paths"])
    assert {
        "/v2/scan-sessions",
        "/v2/capture-sets/{capture_set_id}/views",
        "/v2/capture-sets/{capture_set_id}/analysis-runs",
        "/v2/match-proposals/{proposal_id}/decisions",
        "/v2/lesions/{lesion_id}",
        "/v2/reports",
        "/v2/jobs",
        "/v2/sync/push",
        "/v2/sync/pull",
        "/v2/clinician-verifications",
        "/v2/admin/clinician-verifications",
        "/v2/access-grants",
        "/v2/clinician/reviews",
        "/v2/shares",
        "/v2/share-exchanges",
        "/v2/share-viewer/resources",
        "/v2/access-history",
        "/internal/v2/assets/generated",
        "/v2/generated-artifacts/{artifact_id}",
    }.issubset(paths)
    assert "components" in schema and "schemas" in schema["components"]
