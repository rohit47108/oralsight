"""At-least-once Redis Streams publication with an in-memory test backend."""

from __future__ import annotations

import asyncio
from typing import Protocol

from redis.asyncio import Redis

from .config import QueueBackend, Settings


class QueueUnavailable(RuntimeError):
    pass


class JobQueue(Protocol):
    async def publish(self, envelope: str) -> str: ...

    async def cancel(self, job_id: str, *, ttl_seconds: int) -> None: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


class MemoryJobQueue:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []
        self.cancelled: set[str] = set()

    async def publish(self, envelope: str) -> str:
        message_id = f"memory-{len(self.messages) + 1}"
        self.messages.append((message_id, envelope))
        return message_id

    async def cancel(self, job_id: str, *, ttl_seconds: int) -> None:
        del ttl_seconds
        self.cancelled.add(job_id)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class RedisJobQueue:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis = Redis.from_url(
            settings.redis_url.get_secret_value(),
            decode_responses=True,
            health_check_interval=30,
        )

    async def publish(self, envelope: str) -> str:
        try:
            value = await asyncio.wait_for(
                self.redis.xadd(
                    self.settings.redis_stream_name,
                    {"envelope": envelope},
                    maxlen=100_000,
                    approximate=True,
                ),
                timeout=self.settings.queue_publish_timeout_seconds,
            )
        except Exception as exc:
            raise QueueUnavailable("queue_publish_failed") from exc
        return str(value)

    async def cancel(self, job_id: str, *, ttl_seconds: int) -> None:
        try:
            await asyncio.wait_for(
                self.redis.set(
                    f"{self.settings.redis_cancel_prefix}{job_id}",
                    "1",
                    ex=ttl_seconds,
                ),
                timeout=self.settings.queue_publish_timeout_seconds,
            )
        except Exception as exc:
            raise QueueUnavailable("queue_cancel_failed") from exc

    async def ping(self) -> bool:
        try:
            return bool(
                await asyncio.wait_for(
                    self.redis.ping(),
                    timeout=self.settings.queue_publish_timeout_seconds,
                )
            )
        except Exception:
            return False

    async def close(self) -> None:
        await self.redis.aclose()


def create_job_queue(settings: Settings) -> JobQueue:
    if settings.queue_backend is QueueBackend.REDIS:
        return RedisJobQueue(settings)
    return MemoryJobQueue()
