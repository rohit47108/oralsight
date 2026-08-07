from __future__ import annotations

import hashlib
import hmac
import json
import logging

import pytest

from oralsight_worker.auth import ServiceRequestSigner
from oralsight_worker.retry import RetryPolicy
from oralsight_worker.safe_logging import SafeEventLogger


class FixedRandom:
    def __init__(self, value: float) -> None:
        self.value = value

    def uniform(self, _a: float, _b: float) -> float:
        return self.value


def test_hmac_signature_covers_method_path_time_nonce_and_body() -> None:
    secret = b"a" * 32
    signer = ServiceRequestSigner("oralsight-worker", secret)
    headers = signer.headers(
        "post",
        "https://internal.example/v1/jobs?mode=full",
        b"body",
        timestamp=123,
        nonce="abc123",
    )
    digest = hashlib.sha256(b"body").hexdigest()
    canonical = f"POST\n/v1/jobs?mode=full\n123\nabc123\n{digest}".encode()
    assert (
        headers["X-OralSight-Signature"]
        == hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    )
    assert headers["X-OralSight-Content-SHA256"] == digest


def test_local_unsigned_hook_returns_no_auth_headers() -> None:
    assert (
        ServiceRequestSigner("oralsight-worker", None).headers(
            "GET", "http://127.0.0.1/healthz"
        )
        == {}
    )


def test_retry_is_bounded_exponential_with_jitter() -> None:
    policy = RetryPolicy(
        base_seconds=2,
        maximum_seconds=10,
        jitter_ratio=0.2,
        random_source=FixedRandom(1.1),
    )
    assert policy.delay_seconds(1) == pytest.approx(2.2)
    assert policy.delay_seconds(3) == pytest.approx(8.8)
    assert policy.delay_seconds(8) == pytest.approx(11.0)
    with pytest.raises(ValueError):
        policy.delay_seconds(0)


def test_logging_drops_payloads_and_redacts_unsafe_values(caplog) -> None:
    caplog.set_level(logging.INFO, logger="worker-test")
    logger = SafeEventLogger(logging.getLogger("worker-test"))
    logger.emit(
        "job_failed",
        job_id="safe-id",
        error_code="newline\nsecret",
        payload={"image": "private"},
    )
    record = json.loads(caplog.records[-1].message)
    assert record == {
        "event": "job_failed",
        "job_id": "safe-id",
        "error_code": "redacted",
    }
    assert "private" not in caplog.records[-1].message

    logger.emit("unsafe\nevent", job_id="safe-id")
    assert json.loads(caplog.records[-1].message)["event"] == "invalid_event"
