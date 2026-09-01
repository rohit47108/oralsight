"""Bounded, process-local request throttling without retaining network identifiers."""

from __future__ import annotations

import hashlib
import math
import os
import secrets
import threading
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass

RATE_LIMIT_PER_CLIENT_ENV = "STOMA3D_RATE_LIMIT_PER_CLIENT"
RATE_LIMIT_GLOBAL_ENV = "STOMA3D_RATE_LIMIT_GLOBAL"
RATE_LIMIT_WINDOW_ENV = "STOMA3D_RATE_LIMIT_WINDOW_SECONDS"


def _bounded_int(
    environment: Mapping[str, str],
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw = environment.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}.")
    return value


@dataclass(frozen=True, slots=True)
class RateLimitConfiguration:
    per_client_requests: int
    global_requests: int
    window_seconds: int


def load_rate_limit_configuration(
    *,
    production: bool,
    environment: Mapping[str, str] | None = None,
) -> RateLimitConfiguration:
    env = os.environ if environment is None else environment
    per_client_default = 30 if production else 10_000
    global_default = 300 if production else 100_000
    return RateLimitConfiguration(
        per_client_requests=_bounded_int(
            env,
            RATE_LIMIT_PER_CLIENT_ENV,
            default=per_client_default,
            minimum=1,
            maximum=100_000,
        ),
        global_requests=_bounded_int(
            env,
            RATE_LIMIT_GLOBAL_ENV,
            default=global_default,
            minimum=1,
            maximum=1_000_000,
        ),
        window_seconds=_bounded_int(
            env,
            RATE_LIMIT_WINDOW_ENV,
            default=60,
            minimum=1,
            maximum=3_600,
        ),
    )


class EphemeralRequestRateLimiter:
    """Fixed-window protection using salted hashes and bounded in-memory state."""

    def __init__(
        self,
        configuration: RateLimitConfiguration,
        *,
        salt: bytes | None = None,
        max_client_buckets: int = 4_096,
    ) -> None:
        self.configuration = configuration
        self._salt = salt or secrets.token_bytes(32)
        self._max_client_buckets = max_client_buckets
        self._global_events: deque[float] = deque()
        self._client_events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _key(self, client_identifier: str) -> str:
        return hashlib.sha256(
            self._salt + client_identifier.encode("utf-8", errors="replace")
        ).hexdigest()

    @staticmethod
    def _purge(events: deque[float], cutoff: float) -> None:
        while events and events[0] <= cutoff:
            events.popleft()

    def _trim_client_buckets(self, cutoff: float) -> None:
        expired = [
            key
            for key, events in self._client_events.items()
            if not events or events[-1] <= cutoff
        ]
        for key in expired:
            self._client_events.pop(key, None)
        if len(self._client_events) < self._max_client_buckets:
            return
        oldest_key = min(
            self._client_events,
            key=lambda key: self._client_events[key][-1],
        )
        self._client_events.pop(oldest_key, None)

    def check(self, client_identifier: str, *, now: float | None = None) -> int | None:
        current = time.monotonic() if now is None else now
        cutoff = current - self.configuration.window_seconds
        key = self._key(client_identifier)
        with self._lock:
            self._purge(self._global_events, cutoff)
            if len(self._global_events) >= self.configuration.global_requests:
                return max(
                    1,
                    math.ceil(
                        self._global_events[0]
                        + self.configuration.window_seconds
                        - current
                    ),
                )

            events = self._client_events.get(key)
            if events is None:
                self._trim_client_buckets(cutoff)
                events = deque()
                self._client_events[key] = events
            self._purge(events, cutoff)
            if len(events) >= self.configuration.per_client_requests:
                return max(
                    1,
                    math.ceil(events[0] + self.configuration.window_seconds - current),
                )

            events.append(current)
            self._global_events.append(current)
            return None
