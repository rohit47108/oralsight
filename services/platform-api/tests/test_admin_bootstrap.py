from __future__ import annotations

import json

import pytest
from sqlalchemy import delete, func, select

from oralsight_platform.admin_bootstrap import (
    ADDITIONAL_ADMIN_CONFIRMATION_PHRASE,
    FIRST_ADMIN_CONFIRMATION_PHRASE,
    RECOVERY_ADMIN_CONFIRMATION_PHRASE,
    AdminBootstrapError,
    add_platform_admin,
    bootstrap_first_admin,
    recover_zero_admin,
)
from oralsight_platform.models import (
    AdminBootstrapSeal,
    AuditEvent,
    User,
    UserRole,
    UserStatus,
)


async def _add_user(
    app,
    *,
    subject: str,
    role: UserRole = UserRole.PATIENT,
    status: UserStatus = UserStatus.ACTIVE,
) -> str:
    async with app.state.database.sessions() as session:
        user = User(oidc_subject=subject, role=role, status=status)
        session.add(user)
        await session.commit()
        return user.id


async def _bootstrap(app, *, subject: str, confirmation: str):
    async with app.state.database.sessions() as session:
        result = await bootstrap_first_admin(
            session,
            oidc_subject=subject,
            confirmation=confirmation,
        )
        await session.commit()
        return result


async def _add_admin(
    app,
    *,
    target_subject: str,
    reference_subject: str,
    confirmation: str = ADDITIONAL_ADMIN_CONFIRMATION_PHRASE,
):
    async with app.state.database.sessions() as session:
        result = await add_platform_admin(
            session,
            target_oidc_subject=target_subject,
            reference_admin_oidc_subject=reference_subject,
            confirmation=confirmation,
        )
        await session.commit()
        return result


async def _recover_admin(
    app,
    *,
    target_subject: str,
    confirmation: str = RECOVERY_ADMIN_CONFIRMATION_PHRASE,
):
    async with app.state.database.sessions() as session:
        result = await recover_zero_admin(
            session,
            target_oidc_subject=target_subject,
            confirmation=confirmation,
        )
        await session.commit()
        return result


async def test_bootstrap_promotes_only_the_exact_existing_active_subject(app) -> None:
    subject = "auth0|first-admin"
    target_id = await _add_user(app, subject=subject)
    lookalike_id = await _add_user(app, subject=f"{subject}-lookalike")

    result = await _bootstrap(
        app,
        subject=subject,
        confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
    )

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
        lookalike = await session.get(User, lookalike_id)
        seal_count = await session.scalar(
            select(func.count(AdminBootstrapSeal.seal_key))
        )
    assert target is not None and target.role is UserRole.ADMIN
    assert lookalike is not None and lookalike.role is UserRole.PATIENT
    assert seal_count == 1
    assert result.user_id == target_id
    assert result.changed is True


async def test_bootstrap_creates_a_safe_audit_event_and_safe_output(app) -> None:
    subject = "auth0|private-bootstrap-subject"
    target_id = await _add_user(app, subject=subject)

    result = await _bootstrap(
        app,
        subject=subject,
        confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
    )

    async with app.state.database.sessions() as session:
        event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "admin.bootstrap_completed"
            )
        )
    assert event is not None
    assert event.user_id == target_id
    assert event.resource_id == target_id
    assert subject not in json.dumps(event.details, sort_keys=True)
    assert subject not in repr(result)


async def test_bootstrap_is_idempotent_for_the_same_existing_admin(app) -> None:
    subject = "auth0|idempotent-admin"
    target_id = await _add_user(app, subject=subject)

    first = await _bootstrap(
        app,
        subject=subject,
        confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
    )
    second = await _bootstrap(
        app,
        subject=subject,
        confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
    )

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
        event_count = await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type == "admin.bootstrap_completed"
            )
        )
        seal_count = await session.scalar(
            select(func.count(AdminBootstrapSeal.seal_key))
        )
    assert target is not None and target.role is UserRole.ADMIN
    assert first.changed is True
    assert second.changed is False
    assert event_count == 1
    assert seal_count == 1


async def test_bootstrap_seal_survives_admin_and_audit_deletion(app) -> None:
    original_subject = "auth0|deleted-first-admin"
    original_id = await _add_user(app, subject=original_subject)
    await _bootstrap(
        app,
        subject=original_subject,
        confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
    )

    async with app.state.database.sessions() as session:
        await session.execute(delete(AuditEvent))
        await session.execute(delete(User).where(User.id == original_id))
        await session.commit()

    replacement_subject = "auth0|replacement-admin"
    replacement_id = await _add_user(app, subject=replacement_subject)
    with pytest.raises(AdminBootstrapError, match="permanently closed") as caught:
        await _bootstrap(
            app,
            subject=replacement_subject,
            confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
        )

    async with app.state.database.sessions() as session:
        replacement = await session.get(User, replacement_id)
        seal_count = await session.scalar(
            select(func.count(AdminBootstrapSeal.seal_key))
        )
    assert caught.value.code == "bootstrap_sealed"
    assert replacement is not None and replacement.role is UserRole.PATIENT
    assert seal_count == 1


async def test_bootstrap_refuses_when_a_different_admin_exists(app) -> None:
    await _add_user(
        app,
        subject="auth0|existing-admin",
        role=UserRole.ADMIN,
    )
    target_id = await _add_user(app, subject="auth0|second-admin")

    with pytest.raises(AdminBootstrapError, match="already exists") as caught:
        await _bootstrap(
            app,
            subject="auth0|second-admin",
            confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
        )

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
    assert caught.value.code == "admin_already_exists"
    assert target is not None and target.role is UserRole.PATIENT


async def test_bootstrap_refuses_when_target_subject_does_not_exist(app) -> None:
    subject = "auth0|missing-admin"

    with pytest.raises(AdminBootstrapError, match="not found") as caught:
        await _bootstrap(
            app,
            subject=subject,
            confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
        )

    assert caught.value.code == "target_not_found"
    assert subject not in str(caught.value)


async def test_bootstrap_refuses_a_suspended_target(app) -> None:
    subject = "auth0|suspended-admin"
    target_id = await _add_user(
        app,
        subject=subject,
        status=UserStatus.SUSPENDED,
    )

    with pytest.raises(AdminBootstrapError, match="active") as caught:
        await _bootstrap(
            app,
            subject=subject,
            confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
        )

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
    assert caught.value.code == "target_not_active"
    assert target is not None and target.role is UserRole.PATIENT


async def test_bootstrap_requires_the_exact_confirmation_phrase(app) -> None:
    subject = "auth0|unconfirmed-admin"
    target_id = await _add_user(app, subject=subject)

    with pytest.raises(AdminBootstrapError, match="confirmation") as caught:
        await _bootstrap(
            app,
            subject=subject,
            confirmation="yes",
        )

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
    assert caught.value.code == "confirmation_required"
    assert target is not None and target.role is UserRole.PATIENT


async def test_infrastructure_operator_can_add_admin_with_active_admin_reference(
    app,
) -> None:
    reference_subject = "auth0|admin-reference"
    target_subject = "auth0|admin-successor"
    await _add_user(
        app,
        subject=reference_subject,
        role=UserRole.ADMIN,
    )
    target_id = await _add_user(app, subject=target_subject)

    result = await _add_admin(
        app,
        target_subject=target_subject,
        reference_subject=reference_subject,
    )

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
        event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "admin.additional_admin_added"
            )
        )
    assert target is not None and target.role is UserRole.ADMIN
    assert result.user_id == target_id
    assert result.changed is True
    assert event is not None and event.actor_user_id is None
    serialized = json.dumps(event.details, sort_keys=True)
    assert "approve" not in serialized.lower()
    assert reference_subject not in serialized
    assert target_subject not in serialized


async def test_additional_admin_is_idempotent_for_the_same_authorized_target(
    app,
) -> None:
    reference_subject = "auth0|stable-admin-reference"
    target_subject = "auth0|stable-admin-target"
    await _add_user(app, subject=reference_subject, role=UserRole.ADMIN)
    await _add_user(app, subject=target_subject)

    first = await _add_admin(
        app,
        target_subject=target_subject,
        reference_subject=reference_subject,
    )
    second = await _add_admin(
        app,
        target_subject=target_subject,
        reference_subject=reference_subject,
    )

    async with app.state.database.sessions() as session:
        event_count = await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type == "admin.additional_admin_added"
            )
        )
    assert first.changed is True
    assert second.changed is False
    assert event_count == 1


async def test_additional_admin_requires_a_distinct_active_admin_reference(app) -> None:
    reference_subject = "auth0|not-an-admin"
    target_subject = "auth0|blocked-admin-target"
    await _add_user(app, subject=reference_subject)
    target_id = await _add_user(app, subject=target_subject)

    with pytest.raises(AdminBootstrapError, match="administrator") as caught:
        await _add_admin(
            app,
            target_subject=target_subject,
            reference_subject=reference_subject,
        )

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
    assert caught.value.code == "reference_admin_not_active"
    assert target is not None and target.role is UserRole.PATIENT


async def test_recovery_requires_a_previously_created_bootstrap_seal(app) -> None:
    target_subject = "auth0|unsealed-recovery-target"
    target_id = await _add_user(app, subject=target_subject)

    with pytest.raises(AdminBootstrapError, match="not sealed") as caught:
        await _recover_admin(app, target_subject=target_subject)

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
    assert caught.value.code == "bootstrap_not_sealed"
    assert target is not None and target.role is UserRole.PATIENT


async def test_recovery_refuses_while_any_admin_exists(app) -> None:
    existing_subject = "auth0|existing-recovery-admin"
    await _add_user(app, subject=existing_subject)
    await _bootstrap(
        app,
        subject=existing_subject,
        confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
    )
    target_subject = "auth0|blocked-recovery-target"
    target_id = await _add_user(app, subject=target_subject)

    with pytest.raises(AdminBootstrapError, match="still exists") as caught:
        await _recover_admin(app, target_subject=target_subject)

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
    assert caught.value.code == "admin_still_exists"
    assert target is not None and target.role is UserRole.PATIENT


async def test_recovery_promotes_exact_active_target_after_all_admins_disappear(
    app,
) -> None:
    original_subject = "auth0|lost-recovery-admin"
    original_id = await _add_user(app, subject=original_subject)
    await _bootstrap(
        app,
        subject=original_subject,
        confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
    )
    async with app.state.database.sessions() as session:
        await session.execute(delete(AuditEvent))
        await session.execute(delete(User).where(User.id == original_id))
        await session.commit()

    target_subject = "auth0|recovered-admin"
    target_id = await _add_user(app, subject=target_subject)
    lookalike_id = await _add_user(app, subject=f"{target_subject}-lookalike")
    result = await _recover_admin(app, target_subject=target_subject)

    async with app.state.database.sessions() as session:
        target = await session.get(User, target_id)
        lookalike = await session.get(User, lookalike_id)
        event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "admin.zero_admin_recovery_completed"
            )
        )
        seal_count = await session.scalar(
            select(func.count(AdminBootstrapSeal.seal_key))
        )
    assert target is not None and target.role is UserRole.ADMIN
    assert lookalike is not None and lookalike.role is UserRole.PATIENT
    assert result.user_id == target_id and result.changed is True
    assert event is not None and event.actor_user_id is None
    assert target_subject not in json.dumps(event.details, sort_keys=True)
    assert target_subject not in repr(result)
    assert seal_count == 1


async def test_recovery_requires_exact_confirmation_and_active_existing_target(
    app,
) -> None:
    original_subject = "auth0|former-admin"
    original_id = await _add_user(app, subject=original_subject)
    await _bootstrap(
        app,
        subject=original_subject,
        confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
    )
    async with app.state.database.sessions() as session:
        await session.execute(delete(AuditEvent))
        await session.execute(delete(User).where(User.id == original_id))
        await session.commit()

    suspended_subject = "auth0|suspended-recovery-target"
    suspended_id = await _add_user(
        app,
        subject=suspended_subject,
        status=UserStatus.SUSPENDED,
    )
    with pytest.raises(AdminBootstrapError, match="confirmation") as confirmation_error:
        await _recover_admin(
            app,
            target_subject=suspended_subject,
            confirmation="recover",
        )
    assert confirmation_error.value.code == "confirmation_required"

    with pytest.raises(AdminBootstrapError, match="active") as target_error:
        await _recover_admin(app, target_subject=suspended_subject)
    assert target_error.value.code == "target_not_active"

    missing_subject = "auth0|missing-recovery-target"
    with pytest.raises(AdminBootstrapError, match="not found") as missing_error:
        await _recover_admin(app, target_subject=missing_subject)
    assert missing_error.value.code == "target_not_found"
    assert missing_subject not in str(missing_error.value)

    async with app.state.database.sessions() as session:
        suspended = await session.get(User, suspended_id)
    assert suspended is not None and suspended.role is UserRole.PATIENT
