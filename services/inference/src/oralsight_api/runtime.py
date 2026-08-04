"""Bounded execution for CPU-heavy, request-scoped image work."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Mapping
from typing import ParamSpec, TypeVar

MAX_CONCURRENT_INFERENCE_ENV = "ORALSIGHT_MAX_CONCURRENT_INFERENCE"
DEFAULT_MAX_CONCURRENT_INFERENCE = min(2, max(1, os.cpu_count() or 1))
MAX_CONFIGURED_CONCURRENT_INFERENCE = 32

P = ParamSpec("P")
R = TypeVar("R")


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

    def __init__(self, max_concurrency: int) -> None:
        if not 1 <= max_concurrency <= MAX_CONFIGURED_CONCURRENT_INFERENCE:
            raise ValueError(
                f"max_concurrency must be between 1 and "
                f"{MAX_CONFIGURED_CONCURRENT_INFERENCE}."
            )
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run(
        self, function: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        async with self._semaphore:
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


INFERENCE_EXECUTOR = BoundedInferenceExecutor(load_max_concurrent_inference())
