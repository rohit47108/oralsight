"""Bounded execution for CPU-heavy, request-scoped image work."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Mapping
from typing import ParamSpec, TypeVar

MAX_CONCURRENT_INFERENCE_ENV = "ORALSIGHT_MAX_CONCURRENT_INFERENCE"
DEFAULT_MAX_CONCURRENT_INFERENCE = min(2, max(1, os.cpu_count() or 1))
MAX_CONFIGURED_CONCURRENT_INFERENCE = 32
DEFAULT_QUEUE_TIMEOUT_SECONDS = 0.25

P = ParamSpec("P")
R = TypeVar("R")


class InferenceCapacityError(RuntimeError):
    """Raised when CPU capacity is already occupied beyond the short wait budget."""


def load_max_concurrent_inference(
    environment: Mapping[str, str] | None = None,
) -> int:
    env = os.environ if environment is None else environment
    raw_value = env.get(MAX_CONCURRENT_INFERENCE_ENV, "").strip()
    if not raw_value:
        return DEFAULT_MAX_CONCURRENT_INFERENCE
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"{MAX_CONCURRENT_INFERENCE_ENV} must be an integer between 1 and "
            f"{MAX_CONFIGURED_CONCURRENT_INFERENCE}."
        ) from exc
    if not 1 <= value <= MAX_CONFIGURED_CONCURRENT_INFERENCE:
        raise RuntimeError(
            f"{MAX_CONCURRENT_INFERENCE_ENV} must be between 1 and "
            f"{MAX_CONFIGURED_CONCURRENT_INFERENCE}."
        )
    return value


class BoundedInferenceExecutor:
    """Run synchronous image work off-loop with bounded active concurrency.

    This is not a retained job queue. A caller awaits its own request-scoped
    function and receives the result directly; the semaphore only limits how
    many CPU-heavy functions are active at once.
    """

    def __init__(
        self,
        max_concurrency: int,
        *,
        queue_timeout_seconds: float = DEFAULT_QUEUE_TIMEOUT_SECONDS,
    ) -> None:
        if not 1 <= max_concurrency <= MAX_CONFIGURED_CONCURRENT_INFERENCE:
            raise ValueError(
                f"max_concurrency must be between 1 and "
                f"{MAX_CONFIGURED_CONCURRENT_INFERENCE}."
            )
        self.max_concurrency = max_concurrency
        if not 0 < queue_timeout_seconds <= 5:
            raise ValueError(
                "queue_timeout_seconds must be greater than 0 and at most 5."
            )
        self.queue_timeout_seconds = queue_timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run(
        self, function: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(), timeout=self.queue_timeout_seconds
            )
        except TimeoutError as exc:
            raise InferenceCapacityError("inference_capacity_exhausted") from exc
        try:
            worker = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                # Python cannot forcibly stop an active native/Python worker
                # thread. Keep the semaphore slot until it really exits so a
                # disconnected request cannot make active CPU work exceed the
                # configured bound. The original cancellation still wins.
                try:
                    await worker
                except Exception:
                    pass
                raise
        finally:
            self._semaphore.release()


INFERENCE_EXECUTOR = BoundedInferenceExecutor(load_max_concurrent_inference())
