"""Strict, environment-derived service configuration.

Development stays convenient by default. Production mode is deliberately explicit and
cannot start unless response signing is also explicitly required.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

DEMO_FIXTURES_ENV = "STOMA3D_ENABLE_DEMO_FIXTURES"
DEPLOYMENT_MODE_ENV = "STOMA3D_DEPLOYMENT_MODE"
REQUIRE_SIGNING_ENV = "STOMA3D_REQUIRE_RESPONSE_SIGNING"


class DeploymentMode(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


def _strict_bool(
    environment: Mapping[str, str],
    name: str,
    *,
    default: bool,
) -> bool:
    raw_value = environment.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    value = raw_value.strip().lower()
    if value not in {"true", "false"}:
        raise RuntimeError(f"{name} must be exactly true or false.")
    return value == "true"


@dataclass(frozen=True, slots=True)
class ServiceConfiguration:
    deployment_mode: DeploymentMode
    demo_fixtures_enabled: bool
    response_signing_required: bool

    @property
    def production(self) -> bool:
        return self.deployment_mode is DeploymentMode.PRODUCTION


def load_service_configuration(
    environment: Mapping[str, str] | None = None,
) -> ServiceConfiguration:
    env = os.environ if environment is None else environment
    raw_mode = env.get(DEPLOYMENT_MODE_ENV, DeploymentMode.DEVELOPMENT.value)
    try:
        deployment_mode = DeploymentMode(raw_mode.strip().lower())
    except ValueError as exc:
        raise RuntimeError(
            f"{DEPLOYMENT_MODE_ENV} must be development or production."
        ) from exc

    response_signing_required = _strict_bool(
        env,
        REQUIRE_SIGNING_ENV,
        default=False,
    )
    demo_fixtures_enabled = _strict_bool(
        env,
        DEMO_FIXTURES_ENV,
        default=False,
    )
    if deployment_mode is DeploymentMode.PRODUCTION and not response_signing_required:
        raise RuntimeError(
            f"{REQUIRE_SIGNING_ENV}=true is required when "
            f"{DEPLOYMENT_MODE_ENV}=production."
        )

    return ServiceConfiguration(
        deployment_mode=deployment_mode,
        demo_fixtures_enabled=demo_fixtures_enabled,
        response_signing_required=response_signing_required,
    )
