"""Vercel Services entry point for the OralSight FastAPI application.

Vercel installs dependencies from this directory's ``pyproject.toml``.  The
application package uses a ``src`` layout, so add that directory explicitly
when the service is loaded from this file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI

SERVICE_DIRECTORY = Path(__file__).resolve().parent
SOURCE_DIRECTORY = SERVICE_DIRECTORY / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from oralsight_api.deployment import packaged_release_manifest  # noqa: E402


packaged_release = packaged_release_manifest(SERVICE_DIRECTORY)
if packaged_release is not None:
    os.environ.setdefault(
        "ORALSIGHT_RELEASE_MANIFEST_PATH",
        str(packaged_release),
    )

from oralsight_api.main import app as inference_app  # noqa: E402


app = FastAPI(
    title="OralSight Inference Service",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/api", inference_app)
app.mount("/", inference_app)

__all__ = ["app"]
