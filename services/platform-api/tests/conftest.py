from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from oralsight_platform.config import AuthMode, RuntimeEnvironment, Settings
from oralsight_platform.main import create_app
from oralsight_platform.security import issue_local_test_token


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = (tmp_path / "platform.db").as_posix()
    return Settings(
        _env_file=None,
        environment=RuntimeEnvironment.TEST,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        create_schema_on_start=True,
        auth_mode=AuthMode.LOCAL_TEST,
        jwt_leeway_seconds=0,
        local_test_signing_secret="test-suite-signing-secret-at-least-32-characters",
        worker_service_hmac_secret="test-worker-hmac-secret-at-least-32-characters",
        generated_asset_storage_root=tmp_path / "generated-assets",
    )


@pytest_asyncio.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    value = create_app(settings)
    async with value.router.lifespan_context(value):
        yield value


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://platform.test",
    ) as value:
        yield value


@pytest.fixture
def auth_headers(settings: Settings):
    def build(
        subject: str = "auth0|patient-1", roles: tuple[str, ...] = ("patient",)
    ) -> dict[str, str]:
        token = issue_local_test_token(settings, subject=subject, roles=roles)
        return {"Authorization": f"Bearer {token}"}

    return build
