"""Bounded exponential retry policy."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Protocol


class RandomSource(Protocol):
    def uniform(self, a: float, b: float) -> float: ...


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    base_seconds: float = 1.0
    maximum_seconds: float = 300.0
    jitter_ratio: float = 0.2
    random_source: RandomSource = field(default_factory=random.SystemRandom)

    def delay_seconds(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be at least 1")
        base = min(self.maximum_seconds, self.base_seconds * (2 ** (attempt - 1)))
        return base * self.random_source.uniform(
            1 - self.jitter_ratio, 1 + self.jitter_ratio
        )
