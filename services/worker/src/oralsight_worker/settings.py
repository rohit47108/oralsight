"""Validated worker configuration with production fail-closed rules."""

from __future__ import annotations

from enum import StrEnum
from ipaddress import ip_address
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .response_verification import InferenceResponseVerifier


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORALSIGHT_WORKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.DEVELOPMENT
    service_id: str = Field(default="oralsight-worker", pattern=r"^[a-z0-9-]{3,64}$")
    service_hmac_secret: SecretStr | None = None

    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    platform_api_url: str = "http://127.0.0.1:8001"
    inference_api_url: str = "http://127.0.0.1:8000"
    inference_response_signing_public_key_b64: str | None = None

    consumer_name: str = Field(
        default="worker-local-1", pattern=r"^[A-Za-z0-9._-]{3,64}$"
    )
    concurrency: int = Field(default=2, ge=1, le=16)
    read_block_ms: int = Field(default=2_000, ge=100, le=30_000)
    claim_idle_ms: int = Field(default=60_000, ge=5_000, le=600_000)
    heartbeat_interval_seconds: float = Field(default=10, ge=1, le=60)
    heartbeat_ttl_seconds: int = Field(default=35, ge=5, le=300)
    http_timeout_seconds: float = Field(default=30, ge=1, le=120)
    health_port: int = Field(default=8010, ge=1, le=65_535)
    max_asset_bytes: int = Field(default=8_000_000, ge=1_000_000, le=25_000_000)

    stream_name: str = "oralsight:jobs:v1"
    consumer_group: str = "oralsight-workers-v1"
    retry_set: str = "oralsight:jobs:retry:v1"
    dead_letter_stream: str = "oralsight:jobs:dead:v1"
    retention_set: str = "oralsight:jobs:retention:v1"

    @model_validator(mode="after")
    def validate_security_boundary(self) -> Settings:
        protected = self.environment in {Environment.STAGING, Environment.PRODUCTION}
        secret = (
            self.service_hmac_secret.get_secret_value()
            if self.service_hmac_secret is not None
            else ""
        )
        if protected and len(secret.encode("utf-8")) < 32:
            raise ValueError(
                "Staging and production require a service HMAC secret "
                "of at least 32 bytes."
            )
        if protected:
            for name, value in (
                ("platform_api_url", self.platform_api_url),
                ("inference_api_url", self.inference_api_url),
            ):
                if value is not None and urlparse(value).scheme != "https":
                    raise ValueError(
                        f"{name} must use HTTPS outside local development."
                    )
            if urlparse(self.redis_url.get_secret_value()).scheme != "rediss":
                raise ValueError("Redis must use TLS outside local development.")
        encoded_public_key = (
            self.inference_response_signing_public_key_b64.strip()
            if self.inference_response_signing_public_key_b64 is not None
            else ""
        )
        if encoded_public_key:
            try:
                InferenceResponseVerifier.from_standard_base64(encoded_public_key)
            except ValueError as exc:
                raise ValueError(
                    "The inference response signing public key must be a raw "
                    "32-byte Ed25519 public key in canonical standard base64."
                ) from exc
        elif protected:
            raise ValueError(
                "Staging and production require a pinned inference response "
                "signing public key."
            )
        elif (
            self.environment is Environment.DEVELOPMENT
            and not self._inference_url_is_loopback()
        ):
            raise ValueError(
                "Unsigned development inference is permitted only for a loopback URL."
            )
        if self.heartbeat_ttl_seconds <= self.heartbeat_interval_seconds * 2:
            raise ValueError("Heartbeat TTL must be more than twice its interval.")
        return self

    @property
    def production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    def _inference_url_is_loopback(self) -> bool:
        hostname = (urlparse(self.inference_api_url).hostname or "").lower()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            return True
        try:
            return ip_address(hostname).is_loopback
        except ValueError:
            return False

    @property
    def inference_response_verifier(self) -> InferenceResponseVerifier | None:
        encoded_public_key = (
            self.inference_response_signing_public_key_b64.strip()
            if self.inference_response_signing_public_key_b64 is not None
            else ""
        )
        if not encoded_public_key:
            return None
        return InferenceResponseVerifier.from_standard_base64(encoded_public_key)
