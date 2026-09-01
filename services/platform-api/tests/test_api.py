from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select

from stoma3d_platform.models import (
    AuditEvent,
    DeletionRequest,
    IdempotencyRecord,
    Job,
    JobStatus,
    JobType,
    User,
    UserRole,
    UserStatus,
)
from stoma3d_platform.security import issue_local_test_token


async def test_health_and_readiness_have_privacy_headers(client) -> None:
    supplied_id = str(uuid.uuid4())
    health = await client.get("/healthz", headers={"X-Request-ID": supplied_id})
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "service": "stoma3d-platform-api",
        "version": "0.1.0",
    }
    assert health.headers["x-request-id"] == supplied_id
    assert health.headers["cache-control"] == "no-store"
    assert health.headers["pragma"] == "no-cache"
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["referrer-policy"] == "no-referrer"


async def test_streamed_request_body_limit_applies_without_content_length(
    client, auth_headers
) -> None:
    async def oversized_body():
        chunk = b"x" * 700_000
        for _ in range(3):
            yield chunk

    response = await client.post(
        "/v2/me/deletion-requests",
        headers={
            **auth_headers(),
            "Idempotency-Key": "oversized-stream-0001",
            "Content-Type": "application/json",
        },
        content=oversized_body(),
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"
    assert response.headers["cache-control"] == "no-store"


async def test_invalid_content_length_is_rejected_before_parsing(client) -> None:
    response = await client.post(
        "/v2/me/deletion-requests",
        headers={"Content-Length": "not-an-integer"},
        content=b"{}",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_content_length"

    ready = await client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "database": "ready",
        "queue": "ready",
        "objectStorage": "ready",
    }
    uuid.UUID(ready.headers["x-request-id"])


async def test_readiness_failure_is_safe(client, app, monkeypatch) -> None:
    async def unavailable() -> None:
        raise RuntimeError("database host and password must never escape")

    monkeypatch.setattr(app.state.database, "ping", unavailable)
    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
        "queue": "ready",
        "objectStorage": "ready",
    }
    assert "password" not in response.text
    assert response.headers["cache-control"] == "no-store"


async def test_safe_errors_replace_bad_request_ids(client) -> None:
    response = await client.get(
        "/missing?secret=never-log", headers={"X-Request-ID": "bad"}
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["message"] == "Endpoint not found."
    assert payload["error"]["requestId"] == response.headers["x-request-id"]
    assert response.headers["x-request-id"] != "bad"
    assert "secret" not in response.text


async def test_authentication_is_required_and_token_details_are_hidden(client) -> None:
    missing = await client.get("/v2/me")
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert missing.json()["error"]["code"] == "authentication_required"

    marker = "highly-sensitive-token-marker"
    invalid = await client.get("/v2/me", headers={"Authorization": f"Bearer {marker}"})
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "invalid_access_token"
    assert marker not in invalid.text


async def test_get_me_provisions_one_patient_without_exposing_subject(
    client, app, auth_headers
) -> None:
    first = await client.get("/v2/me", headers=auth_headers())
    second = await client.get("/v2/me", headers=auth_headers())
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["role"] == "patient"
    assert first.json()["status"] == "active"
    assert first.json()["deletionPending"] is False
    assert first.json()["requiredOidcRole"] is None
    assert first.json()["privilegedAccessReady"] is True
    assert first.json()["clinicianApplicationEligible"] is False
    assert "subject" not in first.text.lower()
    assert "auth0|patient-1" not in first.text

    async with app.state.database.sessions() as session:
        assert await session.scalar(select(func.count(User.id))) == 1


async def test_identity_token_roles_cannot_self_promote_database_role(
    client, settings
) -> None:
    token = issue_local_test_token(
        settings,
        subject="auth0|claimed-admin",
        roles=("admin",),
    )
    response = await client.get("/v2/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["role"] == "patient"
    assert response.json()["requiredOidcRole"] is None
    assert response.json()["privilegedAccessReady"] is True
    assert response.json()["clinicianApplicationEligible"] is False


async def test_clinician_pending_claim_allows_application_without_self_promotion(
    client, app, auth_headers
) -> None:
    subject = "auth0|eligible-clinician-applicant"
    response = await client.get(
        "/v2/me",
        headers=auth_headers(subject, roles=("clinician_pending",)),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "patient"
    assert response.json()["clinicianApplicationEligible"] is True

    async with app.state.database.sessions() as session:
        user = await session.get(User, response.json()["id"])
        assert user is not None
        assert user.role is UserRole.PATIENT


async def test_get_me_exposes_fail_closed_privileged_role_activation(
    client, app, auth_headers
) -> None:
    subject = "auth0|clinician-role-handoff"
    provisioned = await client.get("/v2/me", headers=auth_headers(subject))
    assert provisioned.status_code == 200
    async with app.state.database.sessions() as session:
        user = await session.get(User, provisioned.json()["id"])
        assert user is not None
        user.role = UserRole.CLINICIAN
        await session.commit()

    missing_claim = await client.get("/v2/me", headers=auth_headers(subject))
    assert missing_claim.status_code == 200
    assert missing_claim.json()["role"] == "clinician"
    assert missing_claim.json()["requiredOidcRole"] == "clinician"
    assert missing_claim.json()["privilegedAccessReady"] is False

    active_claim = await client.get(
        "/v2/me",
        headers=auth_headers(subject, roles=("clinician",)),
    )
    assert active_claim.status_code == 200
    assert active_claim.json()["requiredOidcRole"] == "clinician"
    assert active_claim.json()["privilegedAccessReady"] is True


async def test_delete_all_is_durable_audited_and_idempotent(
    client, app, auth_headers
) -> None:
    headers = {
        **auth_headers(),
        "Idempotency-Key": "delete-patient-1-0001",
    }
    created = await client.post(
        "/v2/me/deletion-requests",
        headers=headers,
        json={"confirmation": "DELETE"},
    )
    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "requested"
    assert body["startedAt"] is None
    assert body["completedAt"] is None

    replay = await client.post(
        "/v2/me/deletion-requests",
        headers=headers,
        json={"confirmation": "DELETE"},
    )
    assert replay.status_code == 202
    assert replay.json() == body

    status = await client.get(
        f"/v2/me/deletion-requests/{body['requestId']}",
        headers=auth_headers(),
    )
    assert status.status_code == 200
    assert status.json() == body

    me = await client.get("/v2/me", headers=auth_headers())
    assert me.json()["status"] == "deletion_pending"
    assert me.json()["deletionPending"] is True

    async with app.state.database.sessions() as session:
        assert await session.scalar(select(func.count(DeletionRequest.id))) == 1
        assert await session.scalar(select(func.count(Job.id))) == 1
        assert await session.scalar(select(func.count(IdempotencyRecord.id))) == 1
        assert await session.scalar(select(func.count(AuditEvent.id))) == 1
        job = await session.scalar(select(Job))
        assert job is not None
        assert job.job_type is JobType.DELETE_ALL
        assert job.status is JobStatus.QUEUED
        assert job.resource_id == body["requestId"]
        user = await session.scalar(select(User))
        assert user is not None and user.status is UserStatus.DELETION_PENDING


async def test_delete_all_requires_confirmation_and_idempotency_key(
    client, auth_headers
) -> None:
    no_key = await client.post(
        "/v2/me/deletion-requests",
        headers=auth_headers(),
        json={"confirmation": "DELETE"},
    )
    assert no_key.status_code == 400
    assert no_key.json()["error"]["code"] == "invalid_idempotency_key"

    invalid_confirmation = await client.post(
        "/v2/me/deletion-requests",
        headers={**auth_headers(), "Idempotency-Key": "delete-patient-1-0002"},
        json={"confirmation": "yes", "privateNote": "must-not-echo"},
    )
    assert invalid_confirmation.status_code == 422
    assert invalid_confirmation.json()["error"]["code"] == "invalid_request"
    assert "privateNote" not in invalid_confirmation.text
    assert "must-not-echo" not in invalid_confirmation.text


async def test_new_idempotency_key_cannot_queue_second_delete(
    client, auth_headers
) -> None:
    first = await client.post(
        "/v2/me/deletion-requests",
        headers={**auth_headers(), "Idempotency-Key": "delete-patient-1-0003"},
        json={"confirmation": "DELETE"},
    )
    assert first.status_code == 202
    second = await client.post(
        "/v2/me/deletion-requests",
        headers={**auth_headers(), "Idempotency-Key": "delete-patient-1-0004"},
        json={"confirmation": "DELETE"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "deletion_already_pending"


async def test_deletion_status_does_not_disclose_another_users_request(
    client, auth_headers
) -> None:
    created = await client.post(
        "/v2/me/deletion-requests",
        headers={
            **auth_headers("auth0|owner"),
            "Idempotency-Key": "delete-owner-user-001",
        },
        json={"confirmation": "DELETE"},
    )
    response = await client.get(
        f"/v2/me/deletion-requests/{created.json()['requestId']}",
        headers=auth_headers("auth0|other-user"),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


async def test_access_log_never_contains_body_query_token_or_key(
    client, auth_headers, caplog
) -> None:
    marker = "body-secret-991827"
    token_header = auth_headers()["Authorization"]
    key = "idempotency-secret-0009"
    with caplog.at_level(logging.INFO, logger="stoma3d_platform.safe_access"):
        response = await client.post(
            "/unmatched?query-secret=7755",
            headers={"Authorization": token_header, "Idempotency-Key": key},
            json={"message": marker},
        )
    assert response.status_code == 404
    safe_log = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "stoma3d_platform.safe_access"
    )
    assert "request_complete method=POST route=<unmatched> status=404" in safe_log
    for secret in [marker, "query-secret", token_header, key, "7755"]:
        assert secret not in safe_log
