from __future__ import annotations

from dataclasses import dataclass, field

from stoma3d_worker.queue import IdempotencyClaim, QueueMessage, RedisStreamQueue
from stoma3d_worker.settings import Settings


class NoopRedis:
    pass


@dataclass
class FakePipeline:
    owner: FakeRedis
    calls: list = field(default_factory=list)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self

        return record

    async def execute(self):
        self.owner.pipeline_calls.extend(self.calls)
        return [1] * len(self.calls)


@dataclass
class FakeRedis:
    values: dict = field(default_factory=dict)
    pipeline_calls: list = field(default_factory=list)
    direct_calls: list = field(default_factory=list)
    autoclaim_response: tuple = ("0-0", [])
    read_response: list = field(default_factory=list)
    retention_entries: list = field(default_factory=list)
    closed: bool = False

    async def xgroup_create(self, *args, **kwargs):
        self.direct_calls.append(("xgroup_create", args, kwargs))

    async def xautoclaim(self, *args, **kwargs):
        return self.autoclaim_response

    async def xreadgroup(self, *args, **kwargs):
        return self.read_response

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.direct_calls.append(("set", (key, value), {"nx": nx, "ex": ex}))
        return True

    async def get(self, key):
        return self.values.get(key)

    async def exists(self, key):
        return int(key in self.values)

    async def expire(self, key, ttl):
        self.direct_calls.append(("expire", (key, ttl), {}))
        return 1

    async def eval(self, script, number_of_keys, *args):
        self.direct_calls.append(("eval", (script, number_of_keys, *args), {}))
        if "GET" in script:
            key, expected, *rest = args
            if self.values.get(key) == expected:
                if rest:
                    self.direct_calls.append(("expire", (key, rest[0]), {}))
                    return 1
                del self.values[key]
                return 1
            return 0
        return 2

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    async def xadd(self, *args, **kwargs):
        self.direct_calls.append(("xadd", args, kwargs))
        return "9-0"

    async def zrangebyscore(self, *args, **kwargs):
        return self.retention_entries

    async def zrem(self, *args, **kwargs):
        self.direct_calls.append(("zrem", args, kwargs))
        return 1

    async def ping(self):
        return True

    async def aclose(self):
        self.closed = True


def test_stream_decoder_accepts_only_strict_envelopes(envelope) -> None:
    queue = RedisStreamQueue(NoopRedis(), Settings(environment="test"))
    valid = queue._decode_message(
        b"1-0", {b"envelope": envelope.model_dump_json(by_alias=True).encode()}
    )
    assert valid.envelope == envelope
    assert valid.validation_error_code is None

    invalid = queue._decode_message(
        "2-0", {"envelope": '{"schemaVersion":"wrong","image":"private"}'}
    )
    assert invalid.envelope is None
    assert invalid.validation_error_code == "invalid_envelope"


def test_stream_decoder_does_not_retain_malformed_payload() -> None:
    queue = RedisStreamQueue(NoopRedis(), Settings(environment="test"))
    invalid = queue._decode_message("2-0", {"something": "private image bytes"})
    assert invalid.envelope is None
    assert not hasattr(invalid, "raw")
    assert invalid.validation_error_code == "missing_envelope"


async def test_consumer_group_reclaims_stale_then_reads_new(envelope) -> None:
    redis = FakeRedis(
        autoclaim_response=(
            "7-0",
            [("1-0", {"envelope": envelope.model_dump_json(by_alias=True)})],
        )
    )
    queue = RedisStreamQueue(redis, Settings(environment="test", read_block_ms=100))
    await queue.setup()
    reclaimed = await queue.read(2)
    assert reclaimed[0].message_id == "1-0"
    assert queue._claim_cursor == "7-0"

    redis.autoclaim_response = ("0-0", [])
    redis.read_response = [
        (
            "stoma3d:jobs:v1",
            [("2-0", {"envelope": envelope.model_dump_json(by_alias=True)})],
        )
    ]
    fresh = await queue.read(2)
    assert fresh[0].message_id == "2-0"


async def test_heartbeat_cancellation_and_idempotency_lifecycle(envelope) -> None:
    redis = FakeRedis()
    settings = Settings(environment="test")
    queue = RedisStreamQueue(redis, settings)
    await queue.worker_heartbeat()
    await queue.job_heartbeat(str(envelope.job_id))
    assert await queue.is_cancelled(str(envelope.job_id)) is False
    redis.values[queue._cancellation_key(str(envelope.job_id))] = "1"
    assert await queue.is_cancelled(str(envelope.job_id)) is True

    claim = await queue.acquire_idempotency("unique-key-123456", "job-1", 60)
    assert claim is IdempotencyClaim.ACQUIRED
    await queue.renew_idempotency("unique-key-123456", "job-1", 60)
    assert any(call[0] == "expire" for call in redis.direct_calls)
    redis.values[queue._idempotency_key("done-key-1234567")] = "complete"
    assert (
        await queue.acquire_idempotency("done-key-1234567", "job-2", 60)
        is IdempotencyClaim.COMPLETE
    )
    redis.values[queue._idempotency_key("busy-key-1234567")] = "other"
    assert (
        await queue.acquire_idempotency("busy-key-1234567", "job-2", 60)
        is IdempotencyClaim.BUSY
    )
    await queue.release_idempotency("unique-key-123456", "job-1")
    assert queue._idempotency_key("unique-key-123456") not in redis.values


async def test_queue_terminal_retry_and_retention_operations(envelope) -> None:
    redis = FakeRedis(retention_entries=["stoma3d:jobs:dead:v1|9-0", "bad"])
    queue = RedisStreamQueue(redis, Settings(environment="test"))
    message = QueueMessage("1-0", envelope)

    await queue.finish_success(message, envelope.idempotency_key, 60)
    await queue.schedule_retry(message, envelope, 2.5)
    await queue.dead_letter(message, envelope, "permanent_failure")
    await queue.dead_letter_invalid(
        QueueMessage("2-0", None, "invalid_envelope"), "invalid_envelope"
    )
    assert await queue.promote_due() == 2
    assert await queue.cleanup_expired() == 1
    assert await queue.ping() is True
    await queue.close()

    operation_names = {call[0] for call in redis.pipeline_calls}
    assert {"set", "xack", "xdel", "zadd"} <= operation_names
    assert redis.closed is True
