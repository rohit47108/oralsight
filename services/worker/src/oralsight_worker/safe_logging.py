"""Structured logs that accept only a small non-clinical field allowlist."""

from __future__ import annotations

import json
import logging
import re

SAFE_FIELDS = frozenset(
    {
        "attempt",
        "consumer",
        "delay_seconds",
        "error_code",
        "event",
        "job_id",
        "job_type",
        "message_id",
        "outcome",
        "request_id",
        "status_code",
        "worker_version",
    }
)
SAFE_VALUE = re.compile(r"^[A-Za-z0-9_.:/-]{0,128}$")


class SafeEventLogger:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("oralsight_worker")

    def emit(self, event: str, *, level: int = logging.INFO, **fields: object) -> None:
        safe_event = event if SAFE_VALUE.fullmatch(event) else "invalid_event"
        record: dict[str, str | int | float | bool | None] = {"event": safe_event}
        for key, value in fields.items():
            if key not in SAFE_FIELDS or key == "event":
                continue
            if isinstance(value, (bool, int, float)) or value is None:
                record[key] = value
                continue
            text = str(value)
            record[key] = text if SAFE_VALUE.fullmatch(text) else "redacted"
        self._logger.log(level, json.dumps(record, separators=(",", ":")))
