"""Offline administrator bootstrap, addition, and sealed-install recovery.

This module deliberately exposes no HTTP route. The operator must first let the
intended administrator sign in once, then run the command with the exact OIDC
subject in an environment variable. Production uses a transaction-scoped
PostgreSQL advisory lock so two operators cannot promote different users. A
durable, identity-free database seal prevents first-time bootstrap from reopening
after administrators or their audit records are removed.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .collaboration_common import append_audit_event
from .config import get_settings
from .database import Database
from .models import (
    AdminBootstrapSeal,
    User,
    UserRole,
    UserStatus,
    new_id,
)

FIRST_ADMIN_CONFIRMATION_PHRASE = "BOOTSTRAP STOMA3D FIRST ADMIN"
ADDITIONAL_ADMIN_CONFIRMATION_PHRASE = "ADD STOMA3D ADMIN"
RECOVERY_ADMIN_CONFIRMATION_PHRASE = (
    "RECOVER STOMA3D SEALED INSTALLATION WITH ZERO ADMINS"
)
ADMIN_BOOTSTRAP_SEAL_KEY = "first_admin_bootstrap_v1"
_SUBJECT_ENV = "STOMA3D_PLATFORM_BOOTSTRAP_ADMIN_SUBJECT"
_CONFIRMATION_ENV = "STOMA3D_PLATFORM_BOOTSTRAP_CONFIRMATION"
_ADMIN_TARGET_ENV = "STOMA3D_PLATFORM_ADMIN_TARGET_SUBJECT"
_ADMIN_REFERENCE_ENV = "STOMA3D_PLATFORM_ADMIN_REFERENCE_SUBJECT"
_ADMIN_CONFIRMATION_ENV = "STOMA3D_PLATFORM_ADMIN_CONFIRMATION"
_RECOVERY_TARGET_ENV = "STOMA3D_PLATFORM_RECOVERY_ADMIN_SUBJECT"
_RECOVERY_CONFIRMATION_ENV = "STOMA3D_PLATFORM_RECOVERY_CONFIRMATION"
_LOCK_NAMESPACE = "stoma3d:first-admin-bootstrap:v1"


class AdminBootstrapError(RuntimeError):
    """A safe operator-facing bootstrap failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AdminBootstrapResult:
    user_id: str
    changed: bool


async def _lock_bootstrap(session: AsyncSession) -> None:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:namespace))"),
            {"namespace": _LOCK_NAMESPACE},
        )


async def _get_bootstrap_seal(session: AsyncSession) -> AdminBootstrapSeal | None:
    return await session.scalar(
        select(AdminBootstrapSeal)
        .where(AdminBootstrapSeal.seal_key == ADMIN_BOOTSTRAP_SEAL_KEY)
        .with_for_update()
    )


async def _admin_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count(User.id)).where(User.role == UserRole.ADMIN)
        )
        or 0
    )


def _seal_bootstrap(session: AsyncSession) -> None:
    session.add(AdminBootstrapSeal(seal_key=ADMIN_BOOTSTRAP_SEAL_KEY))


async def bootstrap_first_admin(
    session: AsyncSession,
    *,
    oidc_subject: str,
    confirmation: str,
) -> AdminBootstrapResult:
    """Promote exactly one existing active account when no administrator exists."""

    if confirmation != FIRST_ADMIN_CONFIRMATION_PHRASE:
        raise AdminBootstrapError(
            "confirmation_required",
            "The exact first-administrator confirmation phrase is required.",
        )
    if not oidc_subject or len(oidc_subject) > 255:
        raise AdminBootstrapError(
            "invalid_subject",
            "The configured administrator identity is invalid.",
        )

    await _lock_bootstrap(session)
    target = await session.scalar(
        select(User).where(User.oidc_subject == oidc_subject).with_for_update()
    )
    if target is None:
        raise AdminBootstrapError(
            "target_not_found",
            "The administrator account was not found. Sign in once before bootstrapping.",
        )
    if target.status is not UserStatus.ACTIVE:
        raise AdminBootstrapError(
            "target_not_active",
            "The administrator account must be active.",
        )

    admin_count = await _admin_count(session)
    seal = await _get_bootstrap_seal(session)
    if target.role is UserRole.ADMIN and admin_count == 1:
        if seal is None:
            _seal_bootstrap(session)
            await session.flush()
        return AdminBootstrapResult(user_id=target.id, changed=False)
    if seal is not None:
        raise AdminBootstrapError(
            "bootstrap_sealed",
            "First-administrator bootstrap is permanently closed on this installation.",
        )
    if admin_count > 0:
        raise AdminBootstrapError(
            "admin_already_exists",
            "A platform administrator already exists; first-admin bootstrap is closed.",
        )

    previous_role = target.role.value
    _seal_bootstrap(session)
    target.role = UserRole.ADMIN
    append_audit_event(
        session,
        patient_user_id=target.id,
        actor_user_id=None,
        event_type="admin.bootstrap_completed",
        resource_type="user",
        resource_id=target.id,
        request_id=new_id(),
        details={
            "method": "offline_operator",
            "previousRole": previous_role,
        },
    )
    await session.flush()
    return AdminBootstrapResult(user_id=target.id, changed=True)


async def add_platform_admin(
    session: AsyncSession,
    *,
    target_oidc_subject: str,
    reference_admin_oidc_subject: str,
    confirmation: str,
) -> AdminBootstrapResult:
    """Add an administrator through a trusted infrastructure operation.

    The referenced administrator proves that this is an addition, not zero-admin
    recovery. It does not represent that person's approval or participation.
    """

    if confirmation != ADDITIONAL_ADMIN_CONFIRMATION_PHRASE:
        raise AdminBootstrapError(
            "confirmation_required",
            "The exact additional-administrator confirmation phrase is required.",
        )
    if (
        not target_oidc_subject
        or not reference_admin_oidc_subject
        or len(target_oidc_subject) > 255
        or len(reference_admin_oidc_subject) > 255
    ):
        raise AdminBootstrapError(
            "invalid_subject",
            "The configured administrator identity is invalid.",
        )
    if target_oidc_subject == reference_admin_oidc_subject:
        raise AdminBootstrapError(
            "distinct_admins_required",
            "The reference and target administrators must be different accounts.",
        )

    await _lock_bootstrap(session)
    reference_admin = await session.scalar(
        select(User)
        .where(User.oidc_subject == reference_admin_oidc_subject)
        .with_for_update()
    )
    if (
        reference_admin is None
        or reference_admin.status is not UserStatus.ACTIVE
        or reference_admin.role is not UserRole.ADMIN
    ):
        raise AdminBootstrapError(
            "reference_admin_not_active",
            "A distinct active platform administrator reference is required.",
        )
    if await _get_bootstrap_seal(session) is None:
        _seal_bootstrap(session)
    target = await session.scalar(
        select(User).where(User.oidc_subject == target_oidc_subject).with_for_update()
    )
    if target is None:
        raise AdminBootstrapError(
            "target_not_found",
            "The target administrator account was not found.",
        )
    if target.status is not UserStatus.ACTIVE:
        raise AdminBootstrapError(
            "target_not_active",
            "The target administrator account must be active.",
        )
    if target.role is UserRole.ADMIN:
        return AdminBootstrapResult(user_id=target.id, changed=False)

    previous_role = target.role.value
    target.role = UserRole.ADMIN
    append_audit_event(
        session,
        patient_user_id=target.id,
        actor_user_id=None,
        event_type="admin.additional_admin_added",
        resource_type="user",
        resource_id=target.id,
        request_id=new_id(),
        details={
            "method": "trusted_infrastructure_operator",
            "previousRole": previous_role,
            "activeAdminReferenceChecked": True,
        },
    )
    await session.flush()
    return AdminBootstrapResult(user_id=target.id, changed=True)


async def recover_zero_admin(
    session: AsyncSession,
    *,
    target_oidc_subject: str,
    confirmation: str,
) -> AdminBootstrapResult:
    """Recover one administrator on a sealed installation with zero admins."""

    if confirmation != RECOVERY_ADMIN_CONFIRMATION_PHRASE:
        raise AdminBootstrapError(
            "confirmation_required",
            "The exact zero-administrator recovery confirmation phrase is required.",
        )
    if not target_oidc_subject or len(target_oidc_subject) > 255:
        raise AdminBootstrapError(
            "invalid_subject",
            "The configured administrator identity is invalid.",
        )

    await _lock_bootstrap(session)
    if await _get_bootstrap_seal(session) is None:
        raise AdminBootstrapError(
            "bootstrap_not_sealed",
            "Administrator recovery is unavailable because this installation is not sealed.",
        )
    if await _admin_count(session) > 0:
        raise AdminBootstrapError(
            "admin_still_exists",
            "Administrator recovery is unavailable while an administrator still exists.",
        )

    target = await session.scalar(
        select(User).where(User.oidc_subject == target_oidc_subject).with_for_update()
    )
    if target is None:
        raise AdminBootstrapError(
            "target_not_found",
            "The recovery administrator account was not found.",
        )
    if target.status is not UserStatus.ACTIVE:
        raise AdminBootstrapError(
            "target_not_active",
            "The recovery administrator account must be active.",
        )

    previous_role = target.role.value
    target.role = UserRole.ADMIN
    append_audit_event(
        session,
        patient_user_id=target.id,
        actor_user_id=None,
        event_type="admin.zero_admin_recovery_completed",
        resource_type="user",
        resource_id=target.id,
        request_id=new_id(),
        details={
            "method": "trusted_infrastructure_recovery",
            "previousRole": previous_role,
        },
    )
    await session.flush()
    return AdminBootstrapResult(user_id=target.id, changed=True)


async def _run_from_environment() -> AdminBootstrapResult:
    subject = os.environ.get(_SUBJECT_ENV, "")
    confirmation = os.environ.get(_CONFIRMATION_ENV, "")
    settings = get_settings()
    database = Database(settings)
    try:
        async with database.sessions() as session:
            async with session.begin():
                return await bootstrap_first_admin(
                    session,
                    oidc_subject=subject,
                    confirmation=confirmation,
                )
    finally:
        await database.dispose()


async def _run_additional_admin_from_environment() -> AdminBootstrapResult:
    target_subject = os.environ.get(_ADMIN_TARGET_ENV, "")
    reference_subject = os.environ.get(_ADMIN_REFERENCE_ENV, "")
    confirmation = os.environ.get(_ADMIN_CONFIRMATION_ENV, "")
    settings = get_settings()
    database = Database(settings)
    try:
        async with database.sessions() as session:
            async with session.begin():
                return await add_platform_admin(
                    session,
                    target_oidc_subject=target_subject,
                    reference_admin_oidc_subject=reference_subject,
                    confirmation=confirmation,
                )
    finally:
        await database.dispose()


async def _run_recovery_admin_from_environment() -> AdminBootstrapResult:
    target_subject = os.environ.get(_RECOVERY_TARGET_ENV, "")
    confirmation = os.environ.get(_RECOVERY_CONFIRMATION_ENV, "")
    settings = get_settings()
    database = Database(settings)
    try:
        async with database.sessions() as session:
            async with session.begin():
                return await recover_zero_admin(
                    session,
                    target_oidc_subject=target_subject,
                    confirmation=confirmation,
                )
    finally:
        await database.dispose()


def main() -> None:
    """Run the one-time bootstrap without printing identity information."""

    try:
        result = asyncio.run(_run_from_environment())
    except AdminBootstrapError as exc:
        print(f"First administrator not changed: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    except Exception:
        print(
            "First administrator not changed: the platform operation failed.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    state = "created" if result.changed else "already ready"
    print(f"First platform administrator {state}.")


def add_admin_main() -> None:
    """Add an administrator without printing either identity."""

    try:
        result = asyncio.run(_run_additional_admin_from_environment())
    except AdminBootstrapError as exc:
        print(f"Administrator not changed: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    except Exception:
        print(
            "Administrator not changed: the platform operation failed.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    state = "added" if result.changed else "already ready"
    print(f"Additional platform administrator {state}.")


def recover_admin_main() -> None:
    """Recover a sealed zero-admin installation without printing identity data."""

    try:
        asyncio.run(_run_recovery_admin_from_environment())
    except AdminBootstrapError as exc:
        print(f"Administrator not recovered: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    except Exception:
        print(
            "Administrator not recovered: the platform operation failed.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    print("Platform administrator recovered.")


if __name__ == "__main__":
    main()
