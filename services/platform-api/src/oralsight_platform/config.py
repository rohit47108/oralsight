"""Strict environment-backed configuration for the stateful platform API."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SHARE_DERIVATION_KEY = (
    "local-share-derivation-key-replace-before-any-public-deployment"
)
DEFAULT_WORKER_HMAC_SECRET = "local-worker-hmac-secret-replace-before-public-deployment"
DEFAULT_DELETION_TOMBSTONE_KEY = (
    "local-deletion-tombstone-key-replace-before-public-deployment"
)


class RuntimeEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class AuthMode(StrEnum):
    OIDC = "oidc"
    LOCAL_TEST = "local_test"


class ObjectStorageBackend(StrEnum):
    LOCAL = "local"
    S3 = "s3"


class QueueBackend(StrEnum):
    MEMORY = "memory"
    REDIS = "redis"


class Settings(BaseSettings):
    """Service configuration with production-safe cross-field validation."""

    model_config = SettingsConfigDict(
        env_prefix="ORALSIGHT_PLATFORM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    service_name: str = "oralsight-platform-api"
    service_version: str = "0.1.0"
    environment: RuntimeEnvironment = RuntimeEnvironment.DEVELOPMENT
    database_url: str = Field(
        default="postgresql+asyncpg://oralsight:oralsight@127.0.0.1:5432/oralsight",
        repr=False,
    )
    create_schema_on_start: bool = False
    database_ready_timeout_seconds: float = Field(default=2.0, ge=0.1, le=30.0)

    auth_mode: AuthMode = AuthMode.LOCAL_TEST
    oidc_issuer_url: str | None = None
    oidc_jwks_url: str | None = None
    oidc_audience: str = "oralsight-platform-api"
    oidc_algorithms: tuple[str, ...] = ("RS256", "ES256")
    oidc_role_claim: str = "https://oralsight.app/roles"
    jwt_leeway_seconds: int = Field(default=30, ge=0, le=300)
    privileged_token_max_age_seconds: int = Field(default=900, ge=60, le=3600)

    local_test_issuer_url: str = "https://oralsight.local.test"
    local_test_signing_secret: SecretStr = SecretStr(
        "local-development-only-replace-this-secret"
    )
    share_secret_derivation_key: SecretStr = SecretStr(DEFAULT_SHARE_DERIVATION_KEY)
    deletion_tombstone_current_key: SecretStr = SecretStr(
        DEFAULT_DELETION_TOMBSTONE_KEY
    )
    deletion_tombstone_current_key_version: str = "tombstone-v2"
    deletion_tombstone_legacy_share_key: SecretStr | None = None
    deletion_tombstone_retained_keys: dict[str, SecretStr] = Field(default_factory=dict)
    worker_service_hmac_secret: SecretStr = SecretStr(DEFAULT_WORKER_HMAC_SECRET)
    object_storage_backend: ObjectStorageBackend = ObjectStorageBackend.LOCAL
    object_storage_root: Path = Path(".data/object-storage")
    object_storage_public_base_url: str = "http://127.0.0.1:8001"
    object_storage_bucket: str = "oralsight-private"
    object_storage_region: str = "us-east-1"
    object_storage_endpoint_url: str | None = None
    object_storage_access_key_id: SecretStr | None = None
    object_storage_secret_access_key: SecretStr | None = None
    object_storage_session_token: SecretStr | None = None
    object_storage_sse: str = "AES256"
    object_storage_kms_key_id: str | None = None
    object_transfer_lifetime_seconds: int = Field(default=300, ge=60, le=900)
    upload_completion_quiet_seconds: int = Field(default=120, ge=1, le=900)
    pending_upload_lifetime_seconds: int = Field(default=3600, ge=900, le=86_400)
    capture_asset_max_bytes: int = Field(
        default=25_000_000, ge=1_000_000, le=100_000_000
    )
    # Backwards-compatible alias used by the phase-three implementation and tests.
    generated_asset_storage_root: Path | None = None
    generated_asset_max_bytes: int = Field(
        default=32_000_000, ge=1_000_000, le=100_000_000
    )
    generated_asset_retention_days: int = Field(default=365, ge=1, le=3650)
    export_plaintext_max_bytes: int = Field(
        default=80_000_000, ge=1_000_000, le=250_000_000
    )
    export_encrypted_max_bytes: int = Field(
        default=100_000_000, ge=1_000_000, le=300_000_000
    )
    export_retention_days: int = Field(default=7, ge=1, le=30)
    report_source_max_bytes: int = Field(
        default=60_000_000, ge=1_000_000, le=200_000_000
    )

    queue_backend: QueueBackend = QueueBackend.REDIS
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    redis_stream_name: str = "oralsight:jobs:v1"
    redis_cancel_prefix: str = "oralsight:job-cancelled:v1:"
    queue_publish_timeout_seconds: float = Field(default=3.0, ge=0.1, le=30)
    queue_dispatch_interval_seconds: int = Field(default=15, ge=0, le=3600)
    queue_redelivery_after_seconds: int = Field(default=300, ge=60, le=86_400)
    queue_dispatch_batch_size: int = Field(default=100, ge=1, le=1000)
    retention_sweep_interval_seconds: int = Field(default=900, ge=0, le=86_400)

    @model_validator(mode="after")
    def validate_runtime_boundaries(self) -> Settings:
        is_sqlite = self.database_url.startswith("sqlite+")
        is_postgres = self.database_url.startswith("postgresql+asyncpg://")
        if self.environment is RuntimeEnvironment.TEST:
            if not is_sqlite:
                raise ValueError("The test environment requires sqlite+aiosqlite.")
        elif not is_postgres:
            raise ValueError(
                "PostgreSQL with the asyncpg driver is required outside tests."
            )

        if self.create_schema_on_start and self.environment not in {
            RuntimeEnvironment.DEVELOPMENT,
            RuntimeEnvironment.TEST,
        }:
            raise ValueError(
                "Automatic schema creation is allowed only in development and test."
            )

        if self.auth_mode is AuthMode.LOCAL_TEST:
            if self.environment not in {
                RuntimeEnvironment.DEVELOPMENT,
                RuntimeEnvironment.TEST,
            }:
                raise ValueError(
                    "local_test authentication is forbidden in staging and production."
                )
            if len(self.local_test_signing_secret.get_secret_value()) < 32:
                raise ValueError(
                    "The local test signing secret must be at least 32 characters."
                )
        else:
            if not self.oidc_issuer_url or not self.oidc_jwks_url:
                raise ValueError("OIDC issuer and JWKS URLs are required in oidc mode.")
            if not self.oidc_issuer_url.startswith("https://"):
                raise ValueError("The OIDC issuer URL must use HTTPS.")
            if not self.oidc_jwks_url.startswith("https://"):
                raise ValueError("The OIDC JWKS URL must use HTTPS.")
            if not self.oidc_algorithms or any(
                algorithm.startswith("HS") for algorithm in self.oidc_algorithms
            ):
                raise ValueError(
                    "Remote OIDC must use an asymmetric algorithm allowlist."
                )
        share_key = self.share_secret_derivation_key.get_secret_value()
        if len(share_key) < 32:
            raise ValueError(
                "The share-secret derivation key must be at least 32 characters."
            )
        if (
            self.environment
            in {RuntimeEnvironment.STAGING, RuntimeEnvironment.PRODUCTION}
            and share_key == DEFAULT_SHARE_DERIVATION_KEY
        ):
            raise ValueError(
                "The default share-secret derivation key is forbidden outside development."
            )
        tombstone_key = self.deletion_tombstone_current_key.get_secret_value()
        if len(tombstone_key) < 32:
            raise ValueError(
                "The deletion-tombstone key must be at least 32 characters."
            )
        if (
            self.environment
            in {RuntimeEnvironment.STAGING, RuntimeEnvironment.PRODUCTION}
            and tombstone_key == DEFAULT_DELETION_TOMBSTONE_KEY
        ):
            raise ValueError(
                "The default deletion-tombstone key is forbidden outside development."
            )
        from .deletion_tombstones import validate_tombstone_settings

        validate_tombstone_settings(self)
        worker_secret = self.worker_service_hmac_secret.get_secret_value()
        if len(worker_secret) < 32:
            raise ValueError(
                "The worker service HMAC secret must be at least 32 characters."
            )
        if (
            self.environment
            in {RuntimeEnvironment.STAGING, RuntimeEnvironment.PRODUCTION}
            and worker_secret == DEFAULT_WORKER_HMAC_SECRET
        ):
            raise ValueError(
                "The default worker HMAC secret is forbidden outside development."
            )
        if self.generated_asset_storage_root is not None:
            self.object_storage_root = self.generated_asset_storage_root
        if self.environment is RuntimeEnvironment.TEST:
            self.object_storage_backend = ObjectStorageBackend.LOCAL
            self.queue_backend = QueueBackend.MEMORY
            self.queue_dispatch_interval_seconds = 0
            self.retention_sweep_interval_seconds = 0
        protected = self.environment in {
            RuntimeEnvironment.STAGING,
            RuntimeEnvironment.PRODUCTION,
        }
        if protected and self.retention_sweep_interval_seconds <= 0:
            raise ValueError(
                "Staging and production must keep the retention sweep enabled."
            )
        if protected and self.upload_completion_quiet_seconds <= 0:
            raise ValueError(
                "Staging and production require a positive upload completion quiet period."
            )
        if protected:
            query = parse_qs(urlparse(self.database_url).query)
            postgres_tls = (query.get("ssl") or query.get("sslmode") or [""])[-1]
            if postgres_tls.lower() not in {
                "true",
                "require",
                "verify-ca",
                "verify-full",
            }:
                raise ValueError(
                    "Staging and production PostgreSQL connections must require TLS."
                )
        if protected and self.object_storage_backend is not ObjectStorageBackend.S3:
            raise ValueError(
                "Staging and production require private S3 object storage."
            )
        if protected and self.queue_backend is not QueueBackend.REDIS:
            raise ValueError("Staging and production require Redis job delivery.")
        if protected and not self.redis_url.get_secret_value().startswith("rediss://"):
            raise ValueError("Staging and production Redis connections must use TLS.")
        if self.object_storage_backend is ObjectStorageBackend.S3:
            if not self.object_storage_bucket.strip():
                raise ValueError("An S3 bucket is required for object storage.")
            if self.object_storage_sse not in {"AES256", "aws:kms"}:
                raise ValueError("S3 encryption must use AES256 or aws:kms.")
            if (
                self.object_storage_sse == "aws:kms"
                and not self.object_storage_kms_key_id
            ):
                raise ValueError(
                    "A KMS key ID is required for aws:kms storage encryption."
                )
            access_key = self.object_storage_access_key_id
            secret_key = self.object_storage_secret_access_key
            if (access_key is None) != (secret_key is None):
                raise ValueError(
                    "S3 access-key ID and secret must be configured together."
                )
            if (
                protected
                and self.object_storage_endpoint_url
                and not self.object_storage_endpoint_url.startswith("https://")
            ):
                raise ValueError("A custom production S3 endpoint must use HTTPS.")
        if protected and not self.object_storage_public_base_url.startswith("https://"):
            raise ValueError(
                "The public platform URL must use HTTPS outside development."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
