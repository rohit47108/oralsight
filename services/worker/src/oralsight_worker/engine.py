"""Job state machine and long-running worker loop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from .http_client import PermanentJobError, RetryableJobError
from .models import JobEnvelope, JobOutcome
from .processors import JobCancelled, JobContext, ProcessorRegistry
from .queue import IdempotencyClaim, QueueBackend, QueueMessage
from .retry import RetryPolicy
from .safe_logging import SafeEventLogger


class ResultReporter(Protocol):
    async def report(
        self,
        envelope: JobEnvelope,
        outcome: JobOutcome,
        *,
        result: dict | None = None,
        reason_code: str | None = None,
    ) -> None: ...

    async def register_retention(
        self, envelope: JobEnvelope, outcome: JobOutcome
    ) -> None: ...


Clock = Callable[[], datetime]


@dataclass(slots=True)
class WorkerEngine:
    queue: QueueBackend
    registry: ProcessorRegistry
    reporter: ResultReporter
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    heartbeat_interval_seconds: float = 10.0
    clock: Clock = lambda: datetime.now(UTC)
    logger: SafeEventLogger = field(default_factory=SafeEventLogger)

    @staticmethod
    def _lease_ttl_seconds() -> int:
        return 600

    @staticmethod
    def _completion_ttl(envelope: JobEnvelope, now: datetime) -> int:
        remaining = int((envelope.retention.success_delete_after - now).total_seconds())
        return max(60, min(remaining, 30 * 24 * 60 * 60))

    async def _heartbeat_loop(self, envelope: JobEnvelope, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await self.queue.job_heartbeat(str(envelope.job_id))
            await self.queue.renew_idempotency(
                envelope.idempotency_key,
                str(envelope.job_id),
                self._lease_ttl_seconds(),
            )
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=self.heartbeat_interval_seconds
                )
            except TimeoutError:
                continue

    async def _report_terminal(
        self,
        envelope: JobEnvelope,
        outcome: JobOutcome,
        reason_code: str,
    ) -> None:
        try:
            await self.reporter.report(
                envelope, outcome, result={}, reason_code=reason_code
            )
            await self.reporter.register_retention(envelope, outcome)
        except (RetryableJobError, PermanentJobError):
            self.logger.emit(
                "terminal_callback_failed",
                level=logging.ERROR,
                job_id=str(envelope.job_id),
                job_type=envelope.job_type.value,
                error_code="terminal_callback_failed",
            )

    async def _terminal_failure(
        self,
        message: QueueMessage,
        envelope: JobEnvelope,
        reason_code: str,
        *,
        owns_idempotency_lease: bool = True,
    ) -> None:
        await self._report_terminal(envelope, JobOutcome.FAILED, reason_code)
        if owns_idempotency_lease:
            await self.queue.release_idempotency(
                envelope.idempotency_key, str(envelope.job_id)
            )
        await self.queue.dead_letter(message, envelope, reason_code)
        self.logger.emit(
            "job_dead_lettered",
            level=logging.ERROR,
            job_id=str(envelope.job_id),
            job_type=envelope.job_type.value,
            message_id=message.message_id,
            attempt=envelope.attempt,
            error_code=reason_code,
        )

    async def _schedule_retry(
        self,
        message: QueueMessage,
        envelope: JobEnvelope,
        reason_code: str,
    ) -> None:
        now = self.clock()
        delay = self.retry_policy.delay_seconds(envelope.attempt)
        not_before = now + timedelta(seconds=delay)
        if (
            envelope.attempt >= envelope.max_attempts
            or not_before >= envelope.expires_at
        ):
            await self._terminal_failure(message, envelope, "retry_budget_exhausted")
            return
        updated = JobEnvelope.model_validate(
            {
                **envelope.model_dump(mode="python"),
                "attempt": envelope.attempt + 1,
                "not_before": not_before,
            }
        )
        await self.queue.release_idempotency(
            envelope.idempotency_key, str(envelope.job_id)
        )
        await self.queue.schedule_retry(message, updated, delay)
        self.logger.emit(
            "job_retry_scheduled",
            job_id=str(envelope.job_id),
            job_type=envelope.job_type.value,
            message_id=message.message_id,
            attempt=updated.attempt,
            delay_seconds=round(delay, 3),
            error_code=reason_code,
        )

    async def _defer_busy(self, message: QueueMessage, envelope: JobEnvelope) -> None:
        now = self.clock()
        delay = min(5.0, max(0.1, (envelope.expires_at - now).total_seconds() / 2))
        not_before = now + timedelta(seconds=delay)
        if not_before >= envelope.expires_at:
            await self._terminal_failure(
                message,
                envelope,
                "job_expired",
                owns_idempotency_lease=False,
            )
            return
        updated = JobEnvelope.model_validate(
            {**envelope.model_dump(mode="python"), "not_before": not_before}
        )
        await self.queue.schedule_retry(message, updated, delay)

    async def process(self, message: QueueMessage) -> None:
        if message.envelope is None:
            reason = message.validation_error_code or "invalid_envelope"
            await self.queue.dead_letter_invalid(message, reason)
            self.logger.emit(
                "invalid_job_dead_lettered",
                level=logging.ERROR,
                message_id=message.message_id,
                error_code=reason,
            )
            return

        envelope = message.envelope
        now = self.clock()
        if now >= envelope.expires_at:
            await self._terminal_failure(
                message,
                envelope,
                "job_expired",
                owns_idempotency_lease=False,
            )
            return
        if now < envelope.not_before:
            await self.queue.schedule_retry(
                message,
                envelope,
                (envelope.not_before - now).total_seconds(),
            )
            return

        claim = await self.queue.acquire_idempotency(
            envelope.idempotency_key,
            str(envelope.job_id),
            self._lease_ttl_seconds(),
        )
        if claim is IdempotencyClaim.COMPLETE:
            await self.queue.finish_success(
                message,
                envelope.idempotency_key,
                self._completion_ttl(envelope, now),
            )
            self.logger.emit(
                "duplicate_job_acknowledged",
                job_id=str(envelope.job_id),
                job_type=envelope.job_type.value,
                message_id=message.message_id,
            )
            return
        if claim is IdempotencyClaim.BUSY:
            await self._defer_busy(message, envelope)
            return

        if await self.queue.is_cancelled(str(envelope.job_id)):
            await self._report_terminal(envelope, JobOutcome.CANCELLED, "job_cancelled")
            await self.queue.finish_success(
                message,
                envelope.idempotency_key,
                self._completion_ttl(envelope, now),
            )
            return

        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(envelope, heartbeat_stop)
        )
        context = JobContext(
            job_id=str(envelope.job_id),
            cancellation_check=self.queue.is_cancelled,
            heartbeat=self.queue.job_heartbeat,
        )
        try:
            processor = self.registry.get(envelope.job_type)
            result = await processor.process(envelope, context)
            await self.reporter.report(
                envelope,
                result.outcome,
                result=result.result,
                reason_code=result.reason_code,
            )
            await self.reporter.register_retention(envelope, result.outcome)
            await self.queue.finish_success(
                message,
                envelope.idempotency_key,
                self._completion_ttl(envelope, self.clock()),
            )
            self.logger.emit(
                "job_finished",
                job_id=str(envelope.job_id),
                job_type=envelope.job_type.value,
                message_id=message.message_id,
                attempt=envelope.attempt,
                outcome=result.outcome.value,
            )
        except JobCancelled:
            await self._report_terminal(envelope, JobOutcome.CANCELLED, "job_cancelled")
            await self.queue.finish_success(
                message,
                envelope.idempotency_key,
                self._completion_ttl(envelope, self.clock()),
            )
        except RetryableJobError as exc:
            await self._schedule_retry(message, envelope, exc.code)
        except PermanentJobError as exc:
            await self._terminal_failure(message, envelope, exc.code)
        except Exception:
            # Unknown exceptions are retryable but their content is never logged.
            await self._schedule_retry(message, envelope, "unexpected_worker_error")
        finally:
            heartbeat_stop.set()
            await heartbeat_task


@dataclass(slots=True)
class WorkerRunner:
    queue: QueueBackend
    engine: WorkerEngine
    concurrency: int
    logger: SafeEventLogger = field(default_factory=SafeEventLogger)
    heartbeat_interval_seconds: float = 10.0
    cleanup_interval_seconds: float = 60.0
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _tasks: set[asyncio.Task[None]] = field(default_factory=set)

    def stop(self) -> None:
        self._stop.set()

    def _task_done(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        if task.exception() is not None:
            self.logger.emit(
                "job_task_failed",
                level=logging.ERROR,
                error_code="uncaught_job_task_error",
            )

    async def run(self) -> None:
        await self.queue.setup()
        loop = asyncio.get_running_loop()
        next_heartbeat = 0.0
        next_cleanup = 0.0
        while not self._stop.is_set():
            now = loop.time()
            if now >= next_heartbeat:
                await self.queue.worker_heartbeat()
                next_heartbeat = now + self.heartbeat_interval_seconds
            await self.queue.promote_due()
            if now >= next_cleanup:
                await self.queue.cleanup_expired()
                next_cleanup = now + self.cleanup_interval_seconds
            capacity = self.concurrency - len(self._tasks)
            if capacity <= 0:
                await asyncio.sleep(0.05)
                continue
            messages = await self.queue.read(capacity)
            for message in messages:
                task = asyncio.create_task(self.engine.process(message))
                self._tasks.add(task)
                task.add_done_callback(self._task_done)
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
