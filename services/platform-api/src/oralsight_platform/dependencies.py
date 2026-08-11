"""Database, identity provisioning, role, and ownership dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .database import Database
from .errors import ServiceError
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


async def _provision_user(session: AsyncSession, claims: TokenClaims) -> User:
    user = await session.scalar(select(User).where(User.oidc_subject == claims.subject))
    if user is not None:
        return user

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


async def get_current_actor(
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Actor:
    user = await _provision_user(session, claims)
    if user.status is UserStatus.SUSPENDED:
        raise ServiceError(403, "account_suspended", "This account is not available.")
    return Actor(
        user_id=user.id,
        role=user.role,
        status=user.status,
        token_roles=claims.roles,
    )


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

    OIDC claims never provision or promote database roles. Privileged endpoints use
    this dependency so a stale database role or a token claim alone is insufficient.
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
