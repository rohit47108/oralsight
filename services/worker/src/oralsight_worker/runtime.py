"""Composition root for Redis, HTTP clients, processors, and the worker loop."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx
from redis.asyncio import Redis

from .auth import ServiceRequestSigner
from .engine import WorkerEngine, WorkerRunner
from .http_client import InternalHttpClient
from .models import JobType
from .processors import (
    AnalysisProcessor,
    ComparisonProcessor,
    DeleteAllProcessor,
    PlatformReporter,
    ProcessorRegistry,
    ReconstructionProcessor,
    ReportProcessor,
    SummaryVideoProcessor,
)
from .queue import RedisStreamQueue
from .safe_logging import SafeEventLogger
from .settings import Settings


@dataclass(slots=True)
class Runtime:
    settings: Settings
    queue: RedisStreamQueue
    http_client: httpx.AsyncClient
    runner: WorkerRunner
    logger: SafeEventLogger = field(default_factory=SafeEventLogger)
    task: asyncio.Task[None] | None = None

    @classmethod
    def build(cls, settings: Settings) -> Runtime:
        redis = Redis.from_url(
            settings.redis_url.get_secret_value(),
            decode_responses=True,
            health_check_interval=30,
            socket_connect_timeout=3,
            socket_timeout=max(3, settings.read_block_ms / 1000 + 2),
        )
        queue = RedisStreamQueue(redis, settings)
        secret = (
            settings.service_hmac_secret.get_secret_value().encode()
            if settings.service_hmac_secret is not None
            else None
        )
        signer = ServiceRequestSigner(settings.service_id, secret)
        httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        internal_http = InternalHttpClient(
            client=httpx_client,
            signer=signer,
            platform_api_url=settings.platform_api_url,
            inference_api_url=settings.inference_api_url,
            max_asset_bytes=settings.max_asset_bytes,
        )
        registry = ProcessorRegistry(
            {
                JobType.ANALYSIS: AnalysisProcessor(internal_http),
                JobType.COMPARISON: ComparisonProcessor(internal_http),
                JobType.RECONSTRUCTION: ReconstructionProcessor(internal_http),
                JobType.REPORT: ReportProcessor(internal_http),
                JobType.SUMMARY_VIDEO: SummaryVideoProcessor(internal_http),
                JobType.DELETE_ALL: DeleteAllProcessor(internal_http),
            }
        )
        reporter = PlatformReporter(internal_http)
        engine = WorkerEngine(
            queue=queue,
            registry=registry,
            reporter=reporter,
            heartbeat_interval_seconds=settings.heartbeat_interval_seconds,
        )
        runner = WorkerRunner(
            queue=queue,
            engine=engine,
            concurrency=settings.concurrency,
            heartbeat_interval_seconds=settings.heartbeat_interval_seconds,
        )
        return cls(settings, queue, httpx_client, runner)

    async def start(self) -> None:
        if self.task is None:
            self.task = asyncio.create_task(self.runner.run(), name="worker-runner")
            self.task.add_done_callback(self._runner_done)

    def _runner_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        if task.exception() is not None:
            self.logger.emit(
                "runner_failed",
                level=logging.ERROR,
                error_code="runner_failed",
            )

    async def ready(self) -> bool:
        if self.task is None or self.task.done():
            return False
        try:
            return await self.queue.ping()
        except Exception:
            return False

    async def close(self) -> None:
        self.runner.stop()
        try:
            if self.task is not None:
                await asyncio.wait_for(self.task, timeout=35)
        except TimeoutError:
            if self.task is not None:
                self.task.cancel()
                await asyncio.gather(self.task, return_exceptions=True)
        except Exception:
            self.logger.emit(
                "runner_close_failed",
                level=logging.ERROR,
                error_code="runner_close_failed",
            )
        finally:
            await self.http_client.aclose()
            await self.queue.close()
