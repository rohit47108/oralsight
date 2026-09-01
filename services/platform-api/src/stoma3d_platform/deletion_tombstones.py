"""Keyed account-deletion markers with an explicit, versioned key lifecycle."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping

from sqlalchemy import distinct, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import AuthMode, Settings
from .errors import ServiceError
from .models import DeletedSubjectTombstone

LEGACY_SHARE_KEY_VERSION = "legacy-share-v1"
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def canonical_issuer(settings: Settings) -> str:
    issuer = (
        settings.local_test_issuer_url
        if settings.auth_mode is AuthMode.LOCAL_TEST
        else settings.oidc_issuer_url
    )
    if issuer is None:
        raise RuntimeError("OIDC issuer configuration is incomplete")
    return issuer.rstrip("/")


def _digest(key: bytes, payload: str) -> str:
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def legacy_deletion_receipt_fingerprint(settings: Settings, subject: str) -> str:
    """Reproduce the v1 receipt digest so migrated rows remain enforceable."""

    key = (
        settings.deletion_tombstone_legacy_share_key
        or settings.share_secret_derivation_key
    ).get_secret_value()
    return _digest(
        key.encode("utf-8"),
        f"stoma3d:deletion-status-subject:v1:{subject}",
    )


def current_deleted_subject_fingerprint(settings: Settings, subject: str) -> str:
    identity = f"{canonical_issuer(settings)}\x1f{subject}"
    return _digest(
        settings.deletion_tombstone_current_key.get_secret_value().encode("utf-8"),
        f"stoma3d:deleted-subject-tombstone:v1:{identity}",
    )


def configured_tombstone_keys(settings: Settings) -> Mapping[str, bytes]:
    values: dict[str, bytes] = {
        settings.deletion_tombstone_current_key_version: settings.deletion_tombstone_current_key.get_secret_value().encode(
            "utf-8"
        ),
        LEGACY_SHARE_KEY_VERSION: (
            settings.deletion_tombstone_legacy_share_key
            or settings.share_secret_derivation_key
        )
        .get_secret_value()
        .encode("utf-8"),
    }
    for version, secret in settings.deletion_tombstone_retained_keys.items():
        values[version] = secret.get_secret_value().encode("utf-8")
    return values


def tombstone_fingerprint_candidates(
    settings: Settings, subject: str
) -> dict[str, str]:
    issuer_subject = f"{canonical_issuer(settings)}\x1f{subject}"
    candidates: dict[str, str] = {}
    for version, key in configured_tombstone_keys(settings).items():
        if version == LEGACY_SHARE_KEY_VERSION:
            candidates[version] = _digest(
                key, f"stoma3d:deletion-status-subject:v1:{subject}"
            )
        else:
            candidates[version] = _digest(
                key,
                f"stoma3d:deleted-subject-tombstone:v1:{issuer_subject}",
            )
    return candidates


async def ensure_database_key_versions_available(
    session: AsyncSession, settings: Settings
) -> None:
    configured = set(configured_tombstone_keys(settings))
    retained = set(
        await session.scalars(
            select(distinct(DeletedSubjectTombstone.fingerprint_key_version))
        )
    )
    if not retained.issubset(configured):
        raise ServiceError(
            503,
            "deletion_tombstone_key_unavailable",
            "Account setup is unavailable until retained deletion keys are restored.",
        )


async def matching_tombstone(
    session: AsyncSession,
    settings: Settings,
    subject: str,
    *,
    lock: bool = False,
) -> DeletedSubjectTombstone | None:
    await ensure_database_key_versions_available(session, settings)
    candidates = tombstone_fingerprint_candidates(settings, subject)
    clauses = [
        (DeletedSubjectTombstone.fingerprint_key_version == version)
        & (DeletedSubjectTombstone.subject_fingerprint == fingerprint)
        for version, fingerprint in candidates.items()
    ]
    statement = select(DeletedSubjectTombstone).where(or_(*clauses))
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement)


def validate_tombstone_settings(settings: Settings) -> None:
    versions = [
        settings.deletion_tombstone_current_key_version,
        *settings.deletion_tombstone_retained_keys.keys(),
    ]
    if any(_VERSION_PATTERN.fullmatch(version) is None for version in versions):
        raise ValueError(
            "Deletion-tombstone key versions must be 1 to 64 safe characters."
        )
    if settings.deletion_tombstone_current_key_version == LEGACY_SHARE_KEY_VERSION:
        raise ValueError("The current deletion-tombstone key must use a new version.")
    if (
        settings.deletion_tombstone_current_key_version
        in settings.deletion_tombstone_retained_keys
    ):
        raise ValueError(
            "The current deletion-tombstone key version cannot also be retained."
        )
    for secret in [
        settings.deletion_tombstone_current_key,
        *settings.deletion_tombstone_retained_keys.values(),
    ]:
        if len(secret.get_secret_value()) < 32:
            raise ValueError("Deletion-tombstone keys must be at least 32 characters.")
