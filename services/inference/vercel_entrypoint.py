"""Vercel Services entry point for the OralSight FastAPI application.

Vercel installs dependencies from this directory's ``pyproject.toml``.  The
application package uses a ``src`` layout, so add that directory explicitly
when the service is loaded from this file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SERVICE_DIRECTORY = Path(__file__).resolve().parent
SOURCE_DIRECTORY = SERVICE_DIRECTORY / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

packaged_release = SERVICE_DIRECTORY / "release" / "release-manifest.json"
if packaged_release.is_file():
    os.environ.setdefault(
        "ORALSIGHT_RELEASE_MANIFEST_PATH",
        str(packaged_release),
    )

from oralsight_api.main import app  # noqa: E402

__all__ = ["app"]
