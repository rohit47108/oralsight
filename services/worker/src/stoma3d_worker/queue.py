"""Redis Streams queue with reclaim, delayed retry, DLQ, and idempotency."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from .models import JobEnvelope
from .settings import Settings


class IdempotencyClaim(StrEnum):
    ACQUIRED = "acquired"
    COMPLETE = "complete"
    BUSY = "busy"


@dataclass(frozen=True, slots=True)
class QueueMessage:
    message_id: str
    envelope: JobEnvelope | None
    validation_error_code: str | None = None


class QueueBackend(Protocol):
    async def setup(self) -> None: ...

    async def read(self, count: int) -> list[QueueMessage]: ...

    async def worker_heartbeat(self) -> None: ...

    async def job_heartbeat(self, job_id: str) -> None: ...

    async def is_cancelled(self, job_id: str) -> bool: ...

    async def acquire_idempotency(
        self, key: str, job_id: str, ttl_seconds: int
    ) -> IdempotencyClaim: ...

    async def release_idempotency(self, key: str, job_id: str) -> None: ...

    async def renew_idempotency(
        self, key: str, job_id: str, ttl_seconds: int
    ) -> None: ...

    async def finish_success(
        self, message: QueueMessage, idempotency_key: str, ttl_seconds: int
    ) -> None: ...

    async def schedule_retry(
        self, message: QueueMessage, envelope: JobEnvelope, delay_seconds: float
    ) -> None: ...

    async def dead_letter(
        self, message: QueueMessage, envelope: JobEnvelope, reason_code: str
    ) -> None: ...

    async def dead_letter_invalid(
        self, message: QueueMessage, reason_code: str
    ) -> None: ...

    async def promote_due(self, limit: int = 100) -> int: ...

    async def cleanup_expired(self, limit: int = 100) -> int: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


_PROMOTE_RETRIES_LUA = """
local values = redis.call(
  'ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, ARGV[2]
)
for _, value in ipairs(values) do
  local entry = cjson.decode(value)
  redis.call('XADD', KEYS[2], '*', 'envelope', entry['envelope'])
  redis.call('ZREM', KEYS[1], value)
end
return #values
"""

_RELEASE_IDEMPOTENCY_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

_RENEW_IDEMPOTENCY_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


class RedisStreamQueue:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings
        self._claim_cursor = "0-0"

    @staticmethod
    def _idempotency_key(value: str) -> str:
        return f"stoma3d:idempotency:v1:{value}"

    @staticmethod
    def _cancellation_key(job_id: str) -> str:
        return f"stoma3d:job-cancelled:v1:{job_id}"

    async def setup(self) -> None:
        try:
            await self.redis.xgroup_create(
                self.settings.stream_name,
                self.settings.consumer_group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    @staticmethod
    def _text(value: object) -> str:
        return value.decode() if isinstance(value, bytes) else str(value)

    def _decode_message(
        self, message_id: object, fields: dict[object, object]
    ) -> QueueMessage:
        normalized = {self._text(k): self._text(v) for k, v in fields.items()}
        raw = normalized.get("envelope")
        if raw is None:
            return QueueMessage(
                message_id=self._text(message_id),
                envelope=None,
                validation_error_code="missing_envelope",
            )
        try:
            envelope = JobEnvelope.model_validate_json(raw)
        except (ValidationError, ValueError, TypeError):
            return QueueMessage(
                message_id=self._text(message_id),
                envelope=None,
                validation_error_code="invalid_envelope",
            )
        return QueueMessage(message_id=self._text(message_id), envelope=envelope)

    async def _reclaimed(self, count: int) -> list[QueueMessage]:
        response = await self.redis.xautoclaim(
            self.settings.stream_name,
            self.settings.consumer_group,
            self.settings.consumer_name,
            min_idle_time=self.settings.claim_idle_ms,
            start_id=self._claim_cursor,
            count=count,
        )
        if not response:
            return []
        self._claim_cursor = self._text(response[0])
        entries = response[1] if len(response) > 1 else []
        return [
            self._decode_message(message_id, fields) for message_id, fields in entries
        ]

    async def read(self, count: int) -> list[QueueMessage]:
        reclaimed = await self._reclaimed(count)
        if reclaimed:
            return reclaimed
        response = await self.redis.xreadgroup(
            groupname=self.settings.consumer_group,
            consumername=self.settings.consumer_name,
            streams={self.settings.stream_name: ">"},
            count=count,
            block=self.settings.read_block_ms,
        )
        messages: list[QueueMessage] = []
        for _, entries in response or []:
            messages.extend(
                self._decode_message(message_id, fields)
                for message_id, fields in entries
            )
        return messages

    async def worker_heartbeat(self) -> None:
        await self.redis.set(
            f"stoma3d:worker-heartbeat:v1:{self.settings.consumer_name}",
            str(int(time.time())),
            ex=self.settings.heartbeat_ttl_seconds,
        )

    async def job_heartbeat(self, job_id: str) -> None:
        await self.redis.set(
            f"stoma3d:job-heartbeat:v1:{job_id}",
            self.settings.consumer_name,
            ex=self.settings.heartbeat_ttl_seconds,
        )

    async def is_cancelled(self, job_id: str) -> bool:
        return bool(await self.redis.exists(self._cancellation_key(job_id)))

    async def acquire_idempotency(
        self, key: str, job_id: str, ttl_seconds: int
    ) -> IdempotencyClaim:
        redis_key = self._idempotency_key(key)
        acquired = await self.redis.set(redis_key, job_id, nx=True, ex=ttl_seconds)
        if acquired:
            return IdempotencyClaim.ACQUIRED
        value = await self.redis.get(redis_key)
        if self._text(value) == "complete":
            return IdempotencyClaim.COMPLETE
        return IdempotencyClaim.BUSY

    async def release_idempotency(self, key: str, job_id: str) -> None:
        await self.redis.eval(
            _RELEASE_IDEMPOTENCY_LUA,
            1,
            self._idempotency_key(key),
            job_id,
        )

    async def renew_idempotency(self, key: str, job_id: str, ttl_seconds: int) -> None:
        await self.redis.eval(
            _RENEW_IDEMPOTENCY_LUA,
            1,
            self._idempotency_key(key),
            job_id,
            ttl_seconds,
        )

    async def finish_success(
        self, message: QueueMessage, idempotency_key: str, ttl_seconds: int
    ) -> None:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.set(
                self._idempotency_key(idempotency_key),
                "complete",
                ex=ttl_seconds,
            )
            pipe.xack(
                self.settings.stream_name,
                self.settings.consumer_group,
                message.message_id,
            )
            pipe.xdel(self.settings.stream_name, message.message_id)
            if message.envelope is not None:
                pipe.delete(self._cancellation_key(str(message.envelope.job_id)))
            await pipe.execute()

    async def schedule_retry(
        self, message: QueueMessage, envelope: JobEnvelope, delay_seconds: float
    ) -> None:
        due = time.time() + max(0.0, delay_seconds)
        entry = json.dumps(
            {
                "messageId": message.message_id,
                "envelope": envelope.model_dump_json(by_alias=True),
            },
            separators=(",", ":"),
        )
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zadd(self.settings.retry_set, {entry: due})
            pipe.xack(
                self.settings.stream_name,
                self.settings.consumer_group,
                message.message_id,
            )
            pipe.xdel(self.settings.stream_name, message.message_id)
            await pipe.execute()

    async def dead_letter(
        self, message: QueueMessage, envelope: JobEnvelope, reason_code: str
    ) -> None:
        entry_id = await self.redis.xadd(
            self.settings.dead_letter_stream,
            {
                "envelope": envelope.model_dump_json(by_alias=True),
                "reasonCode": reason_code,
                "failedAt": datetime.now(UTC).isoformat(),
            },
        )
        entry_id_text = self._text(entry_id)
        expiry = envelope.retention.dead_letter_delete_after.timestamp()
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zadd(
                self.settings.retention_set,
                {f"{self.settings.dead_letter_stream}|{entry_id_text}": expiry},
            )
            pipe.xack(
                self.settings.stream_name,
                self.settings.consumer_group,
                message.message_id,
            )
            pipe.xdel(self.settings.stream_name, message.message_id)
            pipe.delete(self._cancellation_key(str(envelope.job_id)))
            await pipe.execute()

    async def dead_letter_invalid(
        self, message: QueueMessage, reason_code: str
    ) -> None:
        entry_id = await self.redis.xadd(
            self.settings.dead_letter_stream,
            {
                "sourceMessageId": message.message_id,
                "reasonCode": reason_code,
                "failedAt": datetime.now(UTC).isoformat(),
            },
        )
        expiry = time.time() + 86_400
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zadd(
                self.settings.retention_set,
                {f"{self.settings.dead_letter_stream}|{self._text(entry_id)}": expiry},
            )
            pipe.xack(
                self.settings.stream_name,
                self.settings.consumer_group,
                message.message_id,
            )
            pipe.xdel(self.settings.stream_name, message.message_id)
            await pipe.execute()

    async def promote_due(self, limit: int = 100) -> int:
        value = await self.redis.eval(
            _PROMOTE_RETRIES_LUA,
            2,
            self.settings.retry_set,
            self.settings.stream_name,
            time.time(),
            limit,
        )
        return int(value)

    async def cleanup_expired(self, limit: int = 100) -> int:
        entries = await self.redis.zrangebyscore(
            self.settings.retention_set,
            min="-inf",
            max=time.time(),
            start=0,
            num=limit,
        )
        removed = 0
        for raw in entries:
            member = self._text(raw)
            stream, separator, entry_id = member.partition("|")
            if not separator or not stream or not entry_id:
                await self.redis.zrem(self.settings.retention_set, member)
                continue
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.xdel(stream, entry_id)
                pipe.zrem(self.settings.retention_set, member)
                result = await pipe.execute()
            removed += int(bool(result[0]))
        return removed

    async def ping(self) -> bool:
        return bool(await self.redis.ping())

    async def close(self) -> None:
        await self.redis.aclose()
