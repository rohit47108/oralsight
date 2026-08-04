"""Start the fail-closed API on loopback and verify its public HTTP surface."""

from __future__ import annotations

import json
import io
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image, ImageDraw


def _available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def _request_json(url: str) -> tuple[dict[str, object], str]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=2) as response:
        payload = json.loads(response.read())
        if not isinstance(payload, dict):
            raise RuntimeError(f"{url} did not return a JSON object.")
        return payload, response.headers.get("Cache-Control", "")


def _smoke_capture_bytes() -> bytes:
    image = Image.new("RGB", (640, 640), (174, 102, 112))
    draw = ImageDraw.Draw(image)
    for index in range(80):
        x = 20 + ((index * 71) % 600)
        y = 20 + ((index * 113) % 600)
        color = (120 + index % 40, 65 + index % 25, 85 + index % 30)
        draw.rectangle((x - 5, y - 5, x + 5, y + 5), outline=color, width=2)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=86)
    return output.getvalue()


def _post_multipart_json(
    url: str,
    *,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[dict[str, object], str]:
    boundary = f"oralsight-smoke-{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b"\r\n")
    for name, (filename, content, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
            ).encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        url,
        data=bytes(body),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Request-ID": str(uuid.uuid4()),
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read())
        if not isinstance(payload, dict):
            raise RuntimeError(f"{url} did not return a JSON object.")
        return payload, response.headers.get("Cache-Control", "")


def main() -> int:
    service_directory = Path(__file__).resolve().parents[1]
    port = _available_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment.update(
        {
            "ORALSIGHT_DEPLOYMENT_MODE": "development",
            "ORALSIGHT_REQUIRE_RESPONSE_SIGNING": "false",
            "ORALSIGHT_ENABLE_DEMO_FIXTURES": "false",
            "ORALSIGHT_RELEASE_MANIFEST_PATH": str(
                (service_directory / "release" / "release-manifest.json").resolve()
            ),
        }
    )
    environment.pop("ORALSIGHT_RESPONSE_SIGNING_PRIVATE_KEY_B64", None)

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "vercel_entrypoint:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        cwd=service_directory,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        health: dict[str, object] | None = None
        cache_control = ""
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise RuntimeError(
                    "API exited before readiness.\n"
                    f"stdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                )
            try:
                health, cache_control = _request_json(f"{base_url}/healthz")
                break
            except (OSError, urllib.error.URLError, json.JSONDecodeError):
                time.sleep(0.2)
        if health is None:
            raise RuntimeError("API did not become ready within 15 seconds.")

        model_card, model_card_cache_control = _request_json(
            f"{base_url}/v1/model-card"
        )
        expected_health = {
            "status": "ok",
            "serverAlive": True,
            "analysisReady": True,
            "productionReady": False,
            "retainsData": False,
            "demoFixturesEnabled": False,
        }
        for key, expected in expected_health.items():
            if health.get(key) != expected:
                raise RuntimeError(
                    f"Unexpected health value {key}={health.get(key)!r}; "
                    f"expected {expected!r}."
                )
        if cache_control != "no-store" or model_card_cache_control != "no-store":
            raise RuntimeError(
                "Public JSON responses must set Cache-Control: no-store."
            )
        if "limitations" not in model_card or "enabledHeads" not in model_card:
            raise RuntimeError("Model card response is missing required fields.")
        if model_card.get("enabledHeads") != ["segmentation", "anatomy"]:
            raise RuntimeError(
                "Packaged anatomy and segmentation heads are not enabled."
            )

        capture_bytes = _smoke_capture_bytes()
        analysis, analysis_cache_control = _post_multipart_json(
            f"{base_url}/v1/analyze",
            fields={
                "metadata": json.dumps(
                    {
                        "contractVersion": "1.1.0",
                        "captureId": "http-smoke-capture",
                        "selectedRegion": "left_buccal_mucosa",
                        "inputOrigin": "live_capture",
                        "requestedHeads": ["segmentation", "anatomy"],
                    }
                )
            },
            files={
                "image": ("capture.jpg", capture_bytes, "image/jpeg"),
            },
        )
        if (
            analysis.get("captureId") != "http-smoke-capture"
            or analysis.get("inputOrigin") != "live_capture"
            or analysis.get("analysisOrigin") not in {"unavailable", "live_model"}
            or analysis.get("status") == "complete"
            or analysis.get("candidateMask") is not None
        ):
            raise RuntimeError(
                "Live analyze route did not preserve the released-model safety boundary."
            )

        quality = analysis.get("quality")
        if not isinstance(quality, dict):
            raise RuntimeError("Live analyze route omitted quality metadata.")
        candidate_mask = analysis.get("candidateMask")
        candidate_area = (
            candidate_mask.get("normalizedArea")
            if isinstance(candidate_mask, dict)
            else None
        )
        prior_analysis = {
            "region": "left_buccal_mucosa",
            "status": analysis.get("status"),
            "analysisOrigin": analysis.get("analysisOrigin"),
            "qualityAccepted": quality.get("accepted"),
            "candidateNormalizedArea": candidate_area,
            "modelVersions": analysis.get("modelVersions"),
        }
        comparison, comparison_cache_control = _post_multipart_json(
            f"{base_url}/v1/compare",
            fields={
                "metadata": json.dumps(
                    {
                        "contractVersion": "1.1.0",
                        "baselineCaptureId": "http-smoke-baseline",
                        "currentCaptureId": "http-smoke-current",
                        "region": "left_buccal_mucosa",
                        "userConfirmedMatch": False,
                        "inputOrigin": "live_capture",
                        "baselineAnalysis": {
                            **prior_analysis,
                            "captureId": "http-smoke-baseline",
                        },
                        "currentAnalysis": {
                            **prior_analysis,
                            "captureId": "http-smoke-current",
                        },
                    }
                )
            },
            files={
                "baseline_image": (
                    "baseline.jpg",
                    capture_bytes,
                    "image/jpeg",
                ),
                "current_image": (
                    "current.jpg",
                    capture_bytes,
                    "image/jpeg",
                ),
            },
        )
        if (
            comparison.get("baselineCaptureId") != "http-smoke-baseline"
            or comparison.get("currentCaptureId") != "http-smoke-current"
            or comparison.get("comparable") is not False
            or comparison.get("normalizedChange") is not None
        ):
            raise RuntimeError("Live compare route did not fail closed as expected.")
        if (
            analysis_cache_control != "no-store"
            or comparison_cache_control != "no-store"
        ):
            raise RuntimeError("POST responses must set Cache-Control: no-store.")

        print(
            json.dumps(
                {
                    "status": health["status"],
                    "serverAlive": health["serverAlive"],
                    "analysisReady": health["analysisReady"],
                    "productionReady": health["productionReady"],
                    "retainsData": health["retainsData"],
                    "enabledHeadCount": len(health.get("enabledHeads", [])),
                    "cacheControl": cache_control,
                    "modelCard": "ok",
                    "analyze": "released-model-safe",
                    "compare": "fail-closed",
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
