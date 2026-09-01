from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = REPOSITORY_ROOT / ".github" / "scripts" / "validate_vercel_config.py"
JSONSCHEMA_STUB = ModuleType("jsonschema")
JSONSCHEMA_STUB.Draft7Validator = object  # type: ignore[attr-defined]
sys.modules.setdefault("jsonschema", JSONSCHEMA_STUB)
SPEC = importlib.util.spec_from_file_location(
    "stoma3d_validate_vercel", VALIDATOR_PATH
)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _root_config() -> dict[str, object]:
    return json.loads((REPOSITORY_ROOT / "vercel.json").read_text(encoding="utf-8"))


def test_web_install_store_stays_inside_the_repository() -> None:
    VALIDATOR.validate_repository_contract(_root_config())


def test_web_install_store_rejects_parent_traversal() -> None:
    config = _root_config()
    config["services"]["web"]["installCommand"] = (
        "pnpm install --frozen-lockfile --virtual-store-dir ../../.pnpm"
    )

    with pytest.raises(ValueError, match="inside the repository"):
        VALIDATOR.validate_repository_contract(config)


def test_explicit_inference_entrypoint_covers_mobile_deadline() -> None:
    VALIDATOR.validate_standalone_inference(
        {"functions": {"vercel_entrypoint.py": {"maxDuration": 60}}}
    )


def test_inference_entrypoint_rejects_duration_below_mobile_deadline() -> None:
    with pytest.raises(ValueError, match="18-second mobile deadline"):
        VALIDATOR.validate_standalone_inference(
            {"functions": {"vercel_entrypoint.py": {"maxDuration": 17}}}
        )
