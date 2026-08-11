from __future__ import annotations

import pytest

from oralsight_platform.dependencies import Actor, enforce_ownership, require_roles
from oralsight_platform.errors import ServiceError
from oralsight_platform.models import UserRole, UserStatus


def _actor(user_id: str, role: UserRole) -> Actor:
    return Actor(
        user_id=user_id,
        role=role,
        status=UserStatus.ACTIVE,
        token_roles=frozenset(),
    )


def test_owner_is_allowed() -> None:
    enforce_ownership("user-1", _actor("user-1", UserRole.PATIENT))


def test_non_owner_gets_non_enumerating_not_found() -> None:
    with pytest.raises(ServiceError) as raised:
        enforce_ownership("user-2", _actor("user-1", UserRole.CLINICIAN))
    assert raised.value.status_code == 404
    assert raised.value.code == "resource_not_found"


def test_admin_override_is_explicit() -> None:
    admin = _actor("admin-1", UserRole.ADMIN)
    enforce_ownership("user-2", admin)
    with pytest.raises(ServiceError):
        enforce_ownership("user-2", admin, allow_admin=False)


async def test_role_dependency_uses_database_role() -> None:
    clinician = _actor("clinician-1", UserRole.CLINICIAN)
    dependency = require_roles(UserRole.CLINICIAN, UserRole.ADMIN)
    assert await dependency(actor=clinician) is clinician

    with pytest.raises(ServiceError) as raised:
        await dependency(actor=_actor("patient-1", UserRole.PATIENT))
    assert raised.value.status_code == 403
    assert raised.value.code == "insufficient_role"
