"""Database, identity provisioning, role, and ownership dependencies."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .database import Database
from .errors import ServiceError
from .deletion_tombstones import matching_tombstone
from .models import User, UserRole, UserStatus
from .security import TokenClaims, TokenValidationError, TokenValidator


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: str
    role: UserRole
    status: UserStatus
    token_roles: frozenset[str]


def get_database(request: Request) -> Database:
    return request.app.state.database


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async for session in database.session():
        yield session


async def get_token_claims(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TokenClaims:
    if not authorization:
        raise ServiceError(
            401,
            "authentication_required",
            "A valid access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise ServiceError(
            401,
            "invalid_access_token",
            "The access token could not be verified.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    validator: TokenValidator = request.app.state.token_validator
    try:
        return await validator.validate(token.strip())
    except TokenValidationError as exc:
        raise ServiceError(
            401,
            "invalid_access_token",
            "The access token could not be verified.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _deletion_subject_fingerprint(request: Request, subject: str) -> str:
    key = request.app.state.settings.share_secret_derivation_key.get_secret_value().encode(
        "utf-8"
    )
    return hmac.new(
        key,
        f"oralsight:deletion-status-subject:v1:{subject}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def _provision_user(
    session: AsyncSession, claims: TokenClaims, request: Request
) -> User:
    user = await session.scalar(select(User).where(User.oidc_subject == claims.subject))
    if user is not None:
        return user

    if await matching_tombstone(session, request.app.state.settings, claims.subject):
        raise ServiceError(
            410,
            "account_deleted_recreation_required",
            "This account was deleted. Confirm recreation before using OralSight again.",
        )

    user = User(oidc_subject=claims.subject, role=UserRole.PATIENT)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        user = await session.scalar(
            select(User).where(User.oidc_subject == claims.subject)
        )
        if user is None:
            raise
    return user


def _actor(user: User, claims: TokenClaims) -> Actor:
    return Actor(
        user_id=user.id,
        role=user.role,
        status=user.status,
        token_roles=claims.roles,
    )


async def get_account_actor(
    request: Request,
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncIterator[Actor]:
    """Authenticate an account without hiding its deletion lifecycle.

    This dependency is deliberately reserved for ``GET /v2/me`` and the
    delete-all request endpoint. Ordinary account routes must use
    :func:`get_current_actor`, which rejects deletion-pending accounts.
    """

    provisioned = await _provision_user(session, claims, request)
    async with request.app.state.user_operation_locks.hold(provisioned.id):
        user = await session.scalar(
            select(User)
            .where(User.id == provisioned.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None or user.status is UserStatus.SUSPENDED:
            raise ServiceError(
                403, "account_suspended", "This account is not available."
            )
        yield _actor(user, claims)


async def get_current_actor(
    request: Request,
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Actor:
    """Authenticate and lock an account that may perform ordinary work.

    The row lock serializes normal account requests with delete-all. Once the
    deletion transaction marks the account pending, new or waiting requests
    fail closed before their route handler can read or create account data.
    """

    provisioned = await _provision_user(session, claims, request)
    user = await session.scalar(
        select(User)
        .where(User.id == provisioned.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or user.status is UserStatus.SUSPENDED:
        raise ServiceError(403, "account_suspended", "This account is not available.")
    if user.status is UserStatus.DELETION_PENDING:
        raise ServiceError(
            403,
            "account_deletion_pending",
            "This account is pending deletion.",
        )
    return _actor(user, claims)


def require_roles(*allowed_roles: UserRole) -> Callable[..., Actor]:
    allowed = frozenset(allowed_roles)

    async def dependency(
        actor: Annotated[Actor, Depends(get_current_actor)],
    ) -> Actor:
        if actor.role not in allowed:
            raise ServiceError(
                403, "insufficient_role", "This action is not permitted."
            )
        return actor

    return dependency


def require_oidc_roles(*allowed_roles: UserRole) -> Callable[..., Actor]:
    """Require both the persisted role and its trusted OIDC role claim.

    OIDC claims alone never provision or promote database roles. Explicit
    verification flows may require a validated claim before changing a saved role.
    Privileged endpoints use this dependency so a stale database role or a token
    claim alone is insufficient.
    """

    allowed = frozenset(allowed_roles)
    allowed_claims = frozenset(role.value for role in allowed_roles)

    async def dependency(
        actor: Annotated[Actor, Depends(get_current_actor)],
    ) -> Actor:
        if actor.role not in allowed:
            raise ServiceError(
                403, "insufficient_role", "This action is not permitted."
            )
        if actor.token_roles.isdisjoint(allowed_claims):
            raise ServiceError(
                403,
                "oidc_role_required",
                "The access token is not authorized for this role.",
            )
        return actor

    return dependency


def enforce_ownership(
    owner_user_id: str,
    actor: Actor,
    *,
    allow_admin: bool = True,
) -> None:
    if owner_user_id == actor.user_id:
        return
    if allow_admin and actor.role is UserRole.ADMIN:
        return
    # Do not reveal whether a resource owned by someone else exists.
    raise ServiceError(
        404, "resource_not_found", "The requested resource was not found."
    )
