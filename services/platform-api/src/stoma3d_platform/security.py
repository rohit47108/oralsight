"""OIDC access-token verification with an isolated local-development issuer."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient

from .config import AuthMode, Settings


class TokenValidationError(Exception):
    """An intentionally detail-free authentication failure."""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: str
    roles: frozenset[str]


class TokenValidator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwks_client = (
            PyJWKClient(settings.oidc_jwks_url, cache_keys=True, lifespan=300)
            if settings.auth_mode is AuthMode.OIDC and settings.oidc_jwks_url
            else None
        )

    async def validate(self, encoded_token: str) -> TokenClaims:
        try:
            if self.settings.auth_mode is AuthMode.LOCAL_TEST:
                payload = jwt.decode(
                    encoded_token,
                    self.settings.local_test_signing_secret.get_secret_value(),
                    algorithms=["HS256"],
                    audience=self.settings.oidc_audience,
                    issuer=self.settings.local_test_issuer_url,
                    leeway=self.settings.jwt_leeway_seconds,
                    options={"require": ["sub", "iss", "aud", "iat", "exp"]},
                )
            else:
                if self._jwks_client is None:
                    raise TokenValidationError
                signing_key = await asyncio.to_thread(
                    self._jwks_client.get_signing_key_from_jwt, encoded_token
                )
                payload = jwt.decode(
                    encoded_token,
                    signing_key.key,
                    algorithms=list(self.settings.oidc_algorithms),
                    audience=self.settings.oidc_audience,
                    issuer=self.settings.oidc_issuer_url,
                    leeway=self.settings.jwt_leeway_seconds,
                    options={"require": ["sub", "iss", "aud", "iat", "exp"]},
                )
        except (InvalidTokenError, ValueError, TypeError) as exc:
            raise TokenValidationError from exc

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
            raise TokenValidationError

        role_value: Any = payload.get(self.settings.oidc_role_claim, [])
        if isinstance(role_value, str):
            raw_roles = [role_value]
        elif isinstance(role_value, list):
            raw_roles = role_value
        else:
            raw_roles = []
        roles = {
            role for role in raw_roles if isinstance(role, str) and 0 < len(role) <= 64
        }
        issued_at_value = payload.get("iat")
        if isinstance(issued_at_value, bool) or not isinstance(
            issued_at_value, (int, float)
        ):
            raise TokenValidationError
        try:
            issued_at = datetime.fromtimestamp(issued_at_value, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise TokenValidationError from exc
        privileged_roles = {"clinician_pending", "clinician", "admin"}
        maximum_age = timedelta(
            seconds=(
                self.settings.privileged_token_max_age_seconds
                + self.settings.jwt_leeway_seconds
            )
        )
        if datetime.now(UTC) - issued_at > maximum_age:
            roles.difference_update(privileged_roles)
        return TokenClaims(subject=subject, roles=frozenset(roles))


def issue_local_test_token(
    settings: Settings,
    *,
    subject: str,
    roles: tuple[str, ...] = ("patient",),
    lifetime: timedelta = timedelta(minutes=15),
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Create a token for automated tests and local development only."""

    if settings.auth_mode is not AuthMode.LOCAL_TEST:
        raise RuntimeError("Local test tokens are disabled for this configuration.")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "iss": issuer or settings.local_test_issuer_url,
            "aud": audience or settings.oidc_audience,
            "iat": now,
            "exp": now + lifetime,
            settings.oidc_role_claim: list(roles),
        },
        settings.local_test_signing_secret.get_secret_value(),
        algorithm="HS256",
        headers={"typ": "JWT"},
    )
