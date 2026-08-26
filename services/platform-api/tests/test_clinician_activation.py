from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from oralsight_platform.models import (
    AuditEvent,
    ClinicianVerification,
    ClinicianVerificationStatus,
    User,
    UserRole,
    UserStatus,
)


async def _provision_admin(client, app, auth_headers) -> tuple[str, dict[str, str]]:
    subject = "auth0|clinician-activation-admin"
    response = await client.get("/v2/me", headers=auth_headers(subject))
    assert response.status_code == 200
    user_id = response.json()["id"]
    async with app.state.database.sessions() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.role = UserRole.ADMIN
        await session.commit()
    return user_id, auth_headers(subject, roles=("admin",))


async def _submit_and_approve(
    client,
    app,
    auth_headers,
    *,
    suffix: str,
) -> tuple[str, str, str, object]:
    applicant_subject = f"auth0|clinician-activation-{suffix}"
    applicant_headers = auth_headers(
        applicant_subject,
        roles=("clinician_pending",),
    )
    submitted = await client.post(
        "/v2/clinician-verifications",
        headers={
            **applicant_headers,
            "Idempotency-Key": f"clinician-application-{suffix}",
        },
        json={
            "profession": "Dentist",
            "licenseJurisdiction": "New Jersey",
            "licenseNumber": f"NJ-{suffix}-4821",
            "organization": "Oral Health Research Clinic",
            "applicantEvidenceRef": f"credential-review-{suffix}",
        },
    )
    assert submitted.status_code == 201
    verification_id = submitted.json()["verificationId"]
    applicant_user_id = submitted.json()["applicantUserId"]

    _, admin_headers = await _provision_admin(client, app, auth_headers)
    decided = await client.post(
        f"/v2/admin/clinician-verifications/{verification_id}/decision",
        headers={
            **admin_headers,
            "Idempotency-Key": f"clinician-decision-{suffix}",
        },
        json={
            "status": "verified",
            "decisionReason": None,
            "evidence": {
                "source": "State licensing registry",
                "referenceId": f"registry-check-{suffix}",
                "checkedAt": datetime.now(UTC).isoformat(),
                "reviewerNotes": "License and identity evidence matched.",
            },
        },
    )
    assert decided.status_code == 200
    return applicant_subject, applicant_user_id, verification_id, decided


def _application_body(suffix: str) -> dict[str, str]:
    return {
        "profession": "Dentist",
        "licenseJurisdiction": "New Jersey",
        "licenseNumber": f"NJ-{suffix}-4821",
        "organization": "Oral Health Research Clinic",
        "applicantEvidenceRef": f"credential-review-{suffix}",
    }


async def _provision_user(client, app, auth_headers, *, suffix: str) -> tuple[str, str]:
    subject = f"auth0|clinician-transition-{suffix}"
    provisioned = await client.get("/v2/me", headers=auth_headers(subject))
    assert provisioned.status_code == 200
    return subject, provisioned.json()["id"]


def _expected_identity_role(
    settings,
    *,
    observation_status: str,
    observed_at: str | None,
    ready: bool,
) -> dict[str, object]:
    return {
        "requiredClaim": settings.oidc_role_claim,
        "requiredValue": "clinician",
        "observationStatus": observation_status,
        "oidcRoleObservedAt": observed_at,
        "privilegedAccessReady": ready,
    }


async def test_verified_decision_waits_for_a_signed_clinician_role(
    client,
    app,
    settings,
    auth_headers,
) -> None:
    (
        applicant_subject,
        applicant_user_id,
        _verification_id,
        decided,
    ) = await _submit_and_approve(
        client,
        app,
        auth_headers,
        suffix="decision",
    )

    async with app.state.database.sessions() as session:
        applicant = await session.get(User, applicant_user_id)
        assert applicant is not None
        assert applicant.role is UserRole.CLINICIAN_PENDING

    body = decided.json()
    assert body["status"] == "verified"
    assert body["identityRole"] == _expected_identity_role(
        settings,
        observation_status="awaiting_token_observation",
        observed_at=None,
        ready=False,
    )
    assert "oidcSubject" not in body
    assert applicant_subject not in decided.text

    _, admin_headers = await _provision_admin(client, app, auth_headers)
    queue = await client.get(
        "/v2/admin/clinician-verifications?status=verified",
        headers=admin_headers,
    )
    assert queue.status_code == 200
    assert applicant_subject not in queue.text


async def test_rejected_decision_returns_only_a_pending_applicant_to_patient(
    client,
    app,
    auth_headers,
) -> None:
    suffix = "rejected-transition"
    applicant_subject = f"auth0|clinician-activation-{suffix}"
    submitted = await client.post(
        "/v2/clinician-verifications",
        headers={
            **auth_headers(applicant_subject, roles=("clinician_pending",)),
            "Idempotency-Key": f"clinician-application-{suffix}",
        },
        json=_application_body(suffix),
    )
    assert submitted.status_code == 201

    _, admin_headers = await _provision_admin(client, app, auth_headers)
    rejected = await client.post(
        f"/v2/admin/clinician-verifications/{submitted.json()['verificationId']}/decision",
        headers={
            **admin_headers,
            "Idempotency-Key": f"clinician-decision-{suffix}",
        },
        json={
            "status": "rejected",
            "decisionReason": "Credential evidence could not be confirmed.",
            "evidence": {
                "source": "State licensing registry",
                "referenceId": f"registry-check-{suffix}",
                "checkedAt": datetime.now(UTC).isoformat(),
                "reviewerNotes": "The submitted evidence did not match the registry.",
            },
        },
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    async with app.state.database.sessions() as session:
        applicant = await session.get(User, submitted.json()["applicantUserId"])
        assert applicant is not None
        assert applicant.role is UserRole.PATIENT


async def test_activation_rejects_a_token_without_the_clinician_role(
    client,
    app,
    auth_headers,
) -> None:
    (
        applicant_subject,
        applicant_user_id,
        _verification_id,
        _decided,
    ) = await _submit_and_approve(
        client,
        app,
        auth_headers,
        suffix="missing-role",
    )

    denied = await client.post(
        "/v2/clinician-verifications/current/activate",
        headers=auth_headers(applicant_subject, roles=("clinician_pending",)),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "oidc_role_required"

    async with app.state.database.sessions() as session:
        applicant = await session.get(User, applicant_user_id)
        assert applicant is not None
        assert applicant.role is UserRole.CLINICIAN_PENDING


@pytest.mark.parametrize(
    ("saved_role", "saved_status", "expected_status", "expected_code"),
    [
        (UserRole.ADMIN, UserStatus.ACTIVE, 409, "invalid_verification_state"),
        (UserRole.CLINICIAN, UserStatus.ACTIVE, 409, "invalid_verification_state"),
        (
            UserRole.CLINICIAN_PENDING,
            UserStatus.ACTIVE,
            409,
            "invalid_verification_state",
        ),
        (
            UserRole.SHARE_VIEWER,
            UserStatus.ACTIVE,
            409,
            "invalid_verification_state",
        ),
        (UserRole.PATIENT, UserStatus.SUSPENDED, 403, "account_suspended"),
        (
            UserRole.PATIENT,
            UserStatus.DELETION_PENDING,
            403,
            "account_deletion_pending",
        ),
    ],
)
async def test_submission_never_overwrites_a_non_applicant_account_state(
    client,
    app,
    auth_headers,
    saved_role: UserRole,
    saved_status: UserStatus,
    expected_status: int,
    expected_code: str,
) -> None:
    suffix = f"{saved_role.value}-{saved_status.value}"
    subject, user_id = await _provision_user(
        client,
        app,
        auth_headers,
        suffix=suffix,
    )
    async with app.state.database.sessions() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.role = saved_role
        user.status = saved_status
        await session.commit()

    response = await client.post(
        "/v2/clinician-verifications",
        headers={
            **auth_headers(subject, roles=("clinician_pending",)),
            "Idempotency-Key": f"blocked-application-{suffix}",
        },
        json=_application_body(suffix),
    )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    async with app.state.database.sessions() as session:
        user = await session.get(User, user_id)
        assert user is not None
        assert user.role is saved_role
        assert user.status is saved_status
        verification_count = await session.scalar(
            select(func.count(ClinicianVerification.id)).where(
                ClinicianVerification.user_id == user_id
            )
        )
        assert verification_count == 0


@pytest.mark.parametrize("decision_status", ["verified", "rejected"])
@pytest.mark.parametrize(
    ("saved_role", "saved_status"),
    [
        (UserRole.ADMIN, UserStatus.ACTIVE),
        (UserRole.CLINICIAN, UserStatus.ACTIVE),
        (UserRole.PATIENT, UserStatus.ACTIVE),
        (UserRole.SHARE_VIEWER, UserStatus.ACTIVE),
        (UserRole.CLINICIAN_PENDING, UserStatus.SUSPENDED),
        (UserRole.CLINICIAN_PENDING, UserStatus.DELETION_PENDING),
    ],
)
async def test_admin_decision_cannot_overwrite_an_account_changed_during_review(
    client,
    app,
    auth_headers,
    decision_status: str,
    saved_role: UserRole,
    saved_status: UserStatus,
) -> None:
    suffix = f"decision-race-{decision_status}-{saved_role.value}-{saved_status.value}"
    applicant_subject = f"auth0|clinician-activation-{suffix}"
    submitted = await client.post(
        "/v2/clinician-verifications",
        headers={
            **auth_headers(applicant_subject, roles=("clinician_pending",)),
            "Idempotency-Key": f"clinician-application-{suffix}",
        },
        json=_application_body(suffix),
    )
    assert submitted.status_code == 201
    verification_id = submitted.json()["verificationId"]
    applicant_user_id = submitted.json()["applicantUserId"]

    async with app.state.database.sessions() as session:
        applicant = await session.get(User, applicant_user_id)
        assert applicant is not None
        applicant.role = saved_role
        applicant.status = saved_status
        await session.commit()

    _, admin_headers = await _provision_admin(client, app, auth_headers)
    decided = await client.post(
        f"/v2/admin/clinician-verifications/{verification_id}/decision",
        headers={
            **admin_headers,
            "Idempotency-Key": f"clinician-decision-{suffix}",
        },
        json={
            "status": decision_status,
            "decisionReason": (
                "Credential review did not pass."
                if decision_status == "rejected"
                else None
            ),
            "evidence": {
                "source": "State licensing registry",
                "referenceId": f"registry-check-{suffix}",
                "checkedAt": datetime.now(UTC).isoformat(),
                "reviewerNotes": "Account role changed before the decision committed.",
            },
        },
    )

    assert decided.status_code == 409
    assert decided.json()["error"]["code"] == "invalid_verification_state"
    async with app.state.database.sessions() as session:
        applicant = await session.get(User, applicant_user_id)
        verification = await session.get(ClinicianVerification, verification_id)
        assert applicant is not None
        assert verification is not None
        assert applicant.role is saved_role
        assert applicant.status is saved_status
        assert verification.status is ClinicianVerificationStatus.PENDING
        assert verification.reviewed_at is None


@pytest.mark.parametrize(
    "saved_role",
    [UserRole.ADMIN, UserRole.PATIENT, UserRole.SHARE_VIEWER],
)
async def test_activation_cannot_overwrite_an_account_role_changed_after_approval(
    client,
    app,
    auth_headers,
    saved_role: UserRole,
) -> None:
    (
        applicant_subject,
        applicant_user_id,
        verification_id,
        _decided,
    ) = await _submit_and_approve(
        client,
        app,
        auth_headers,
        suffix=f"activation-race-{saved_role.value}",
    )
    async with app.state.database.sessions() as session:
        applicant = await session.get(User, applicant_user_id)
        assert applicant is not None
        applicant.role = saved_role
        await session.commit()

    activated = await client.post(
        "/v2/clinician-verifications/current/activate",
        headers=auth_headers(applicant_subject, roles=("clinician",)),
    )

    assert activated.status_code == 409
    assert activated.json()["error"]["code"] == "invalid_verification_state"
    async with app.state.database.sessions() as session:
        applicant = await session.get(User, applicant_user_id)
        verification = await session.get(ClinicianVerification, verification_id)
        assert applicant is not None
        assert verification is not None
        assert applicant.role is saved_role
        assert verification.oidc_role_observed_at is None
        audit_count = await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type == "clinician_verification.oidc_role_observed",
                AuditEvent.resource_id == verification_id,
            )
        )
        assert audit_count == 0


async def test_signed_role_activation_is_idempotent_and_current_token_gated(
    client,
    app,
    settings,
    auth_headers,
) -> None:
    (
        applicant_subject,
        applicant_user_id,
        verification_id,
        _decided,
    ) = await _submit_and_approve(
        client,
        app,
        auth_headers,
        suffix="observed-role",
    )
    clinician_headers = auth_headers(applicant_subject, roles=("clinician",))

    activated = await client.post(
        "/v2/clinician-verifications/current/activate",
        headers=clinician_headers,
    )
    assert activated.status_code == 200
    activated_identity_role = activated.json()["identityRole"]
    observed_at = activated_identity_role["oidcRoleObservedAt"]
    assert isinstance(observed_at, str)
    assert activated_identity_role == _expected_identity_role(
        settings,
        observation_status="observed",
        observed_at=observed_at,
        ready=True,
    )

    repeated = await client.post(
        "/v2/clinician-verifications/current/activate",
        headers=clinician_headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["identityRole"]["oidcRoleObservedAt"] == observed_at

    async with app.state.database.sessions() as session:
        applicant = await session.get(User, applicant_user_id)
        verification = await session.get(ClinicianVerification, verification_id)
        assert applicant is not None
        assert verification is not None
        assert applicant.role is UserRole.CLINICIAN
        stored_observed_at = getattr(verification, "oidc_role_observed_at", None)
        assert stored_observed_at is not None
        audit_count = await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type == "clinician_verification.oidc_role_observed",
                AuditEvent.resource_id == verification_id,
            )
        )
        assert audit_count == 1

    stale_token_status = await client.get(
        "/v2/clinician-verifications/current",
        headers=auth_headers(applicant_subject, roles=("clinician_pending",)),
    )
    assert stale_token_status.status_code == 200
    assert stale_token_status.json()["identityRole"] == _expected_identity_role(
        settings,
        observation_status="observed",
        observed_at=observed_at,
        ready=False,
    )

    privileged_route = await client.get(
        "/v2/clinician/reviews",
        headers=auth_headers(applicant_subject, roles=("clinician_pending",)),
    )
    assert privileged_route.status_code == 403
    assert privileged_route.json()["error"]["code"] == "oidc_role_required"
