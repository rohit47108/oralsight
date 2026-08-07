from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest
from pydantic import ValidationError

from oralsight_worker.main import create_app
from oralsight_worker.runtime import Runtime
from oralsight_worker.settings import Settings


def test_production_fails_closed_without_secret_or_https() -> None:
    with pytest.raises(ValidationError, match="HMAC"):
        Settings(environment="production")
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(
            environment="production",
            service_hmac_secret="x" * 32,
            platform_api_url="http://platform.internal",
            inference_api_url="https://inference.internal",
        )


def test_production_accepts_only_tls_internal_dependencies() -> None:
    settings = Settings(
        environment="production",
        service_hmac_secret="x" * 32,
        redis_url="rediss://redis.internal:6379/0",
        platform_api_url="https://platform.internal",
        inference_api_url="https://inference.internal",
    )
    assert settings.production is True


async def test_runtime_composes_every_processor_without_network_access() -> None:
    runtime = Runtime.build(Settings(environment="test"))
    assert runtime.runner.concurrency == 2
    assert await runtime.ready() is False
    assert len(runtime.runner.engine.registry.processors) == 7
    await runtime.close()


@dataclass
class FakeRuntime:
    is_ready: bool
    started: bool = False
    closed: bool = False

    async def start(self):
        self.started = True

    async def ready(self):
        return self.is_ready

    async def close(self):
        self.closed = True


async def test_health_and_ready_endpoints() -> None:
    runtime = FakeRuntime(True)
    app = create_app(
        settings=Settings(environment="test"),
        runtime_factory=lambda settings: runtime,
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            health = await client.get("/healthz")
            ready = await client.get("/readyz")
            assert health.json()["status"] == "ok"
            assert ready.json() == {
                "status": "ready",
                "service": "oralsight-worker",
            }
            assert health.headers["cache-control"] == "no-store"
    assert runtime.started and runtime.closed


async def test_ready_returns_503_when_queue_is_unavailable() -> None:
    runtime = FakeRuntime(False)
    app = create_app(
        settings=Settings(environment="test"),
        runtime_factory=lambda settings: runtime,
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
