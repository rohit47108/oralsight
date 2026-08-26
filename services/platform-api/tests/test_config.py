from __future__ import annotations

import pytest
from pydantic import ValidationError

from oralsight_platform.config import (
    AuthMode,
    ObjectStorageBackend,
    QueueBackend,
    RuntimeEnvironment,
    Settings,
)


def test_postgresql_is_the_non_test_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.environment is RuntimeEnvironment.DEVELOPMENT


def test_sqlite_is_rejected_outside_tests() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(
            _env_file=None,
            environment=RuntimeEnvironment.DEVELOPMENT,
            database_url="sqlite+aiosqlite:///not-allowed.db",
        )


def test_tests_require_sqlite() -> None:
    with pytest.raises(ValidationError, match="test environment requires"):
        Settings(
            _env_file=None,
            environment=RuntimeEnvironment.TEST,
            database_url="postgresql+asyncpg://user:pass@localhost/test",
        )


def test_local_issuer_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="local_test authentication is forbidden"):
        Settings(
            _env_file=None,
            environment=RuntimeEnvironment.PRODUCTION,
            database_url="postgresql+asyncpg://user:pass@localhost/oralsight",
            auth_mode=AuthMode.LOCAL_TEST,
        )


def test_remote_oidc_requires_https_issuer_and_jwks() -> None:
    with pytest.raises(ValidationError, match="OIDC issuer and JWKS"):
        Settings(
            _env_file=None,
            environment=RuntimeEnvironment.PRODUCTION,
            database_url="postgresql+asyncpg://user:pass@localhost/oralsight",
            auth_mode=AuthMode.OIDC,
        )


def test_schema_autocreation_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="Automatic schema creation"):
        Settings(
            _env_file=None,
            environment=RuntimeEnvironment.PRODUCTION,
            database_url="postgresql+asyncpg://user:pass@localhost/oralsight",
            auth_mode=AuthMode.OIDC,
            oidc_issuer_url="https://identity.example/",
            oidc_jwks_url="https://identity.example/.well-known/jwks.json",
            create_schema_on_start=True,
        )


def _production_settings(**updates) -> Settings:
    values = {
        "_env_file": None,
        "environment": RuntimeEnvironment.PRODUCTION,
        "database_url": (
            "postgresql+asyncpg://user:pass@db.example/oralsight?ssl=require"
        ),
        "auth_mode": AuthMode.OIDC,
        "oidc_issuer_url": "https://identity.example/",
        "oidc_jwks_url": "https://identity.example/.well-known/jwks.json",
        "share_secret_derivation_key": "s" * 32,
        "deletion_tombstone_current_key": "t" * 32,
        "worker_service_hmac_secret": "w" * 32,
        "object_storage_backend": ObjectStorageBackend.S3,
        "object_storage_bucket": "oralsight-private",
        "object_storage_public_base_url": "https://api.example/",
        "queue_backend": QueueBackend.REDIS,
        "redis_url": "rediss://redis.example/0",
    }
    values.update(updates)
    return Settings(**values)


def test_production_requires_tls_managed_dependencies_and_accepts_safe_config() -> None:
    settings = _production_settings()
    assert settings.environment is RuntimeEnvironment.PRODUCTION
    assert settings.object_storage_backend is ObjectStorageBackend.S3
    assert settings.queue_backend is QueueBackend.REDIS
    assert (
        _production_settings(environment=RuntimeEnvironment.STAGING).environment
        is RuntimeEnvironment.STAGING
    )

    with pytest.raises(
        ValidationError, match="PostgreSQL connections must require TLS"
    ):
        _production_settings(
            database_url="postgresql+asyncpg://user:pass@db.example/oralsight"
        )
    with pytest.raises(ValidationError, match="private S3"):
        _production_settings(object_storage_backend=ObjectStorageBackend.LOCAL)
    with pytest.raises(ValidationError, match="Redis connections must use TLS"):
        _production_settings(redis_url="redis://redis.example/0")
    with pytest.raises(ValidationError, match="public platform URL must use HTTPS"):
        _production_settings(object_storage_public_base_url="http://api.example/")
    with pytest.raises(ValidationError, match="S3 endpoint must use HTTPS"):
        _production_settings(object_storage_endpoint_url="http://s3.example/")
    with pytest.raises(ValidationError, match="configured together"):
        _production_settings(object_storage_access_key_id="access-key-only")
    with pytest.raises(ValidationError, match="retention sweep enabled"):
        _production_settings(retention_sweep_interval_seconds=0)
    with pytest.raises(ValidationError):
        _production_settings(upload_completion_quiet_seconds=0)
