from __future__ import annotations

import json
from pathlib import Path


def test_checked_openapi_matches_application(app) -> None:
    target = Path(__file__).resolve().parents[1] / "openapi.json"
    assert json.loads(target.read_text(encoding="utf-8")) == app.openapi()
