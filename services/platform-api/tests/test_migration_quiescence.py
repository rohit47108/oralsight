from __future__ import annotations

import importlib.util
from datetime import timedelta
from pathlib import Path


def _migration_module():
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260813_0010_upload_capability_quiescence.py"
    )
    spec = importlib.util.spec_from_file_location("upload_quiescence_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_backfills_every_live_asset_for_max_capability_lifetime(
    monkeypatch,
) -> None:
    executed: list[str] = []
    added: list[tuple[str, str]] = []
    indexed: list[str] = []
    module = _migration_module()

    monkeypatch.setattr(
        module.op,
        "add_column",
        lambda table, column: added.append((table, column.name)),
    )
    monkeypatch.setattr(
        module.op,
        "create_index",
        lambda name, *_args, **_kwargs: indexed.append(name),
    )
    monkeypatch.setattr(
        module.op,
        "execute",
        lambda statement: executed.append(str(statement)),
    )

    module.upgrade()

    sql = " ".join(executed).lower()
    assert "where deleted_at is null" in sql
    assert "current_timestamp + interval '1800 seconds'" in sql
    assert "upload_expires_at + interval '900 seconds'" in sql
    assert "status = 'pending'" not in sql
    assert "upload_expires_at > current_timestamp" in sql
    assert ("capture_assets", "upload_capability_expires_at") in added
    assert ("deletion_requests", "upload_quiescence_until") in added
    assert "ix_capture_assets_upload_capability_expires_at" in indexed


def test_max_capability_migration_drain_matches_configured_upper_bound() -> None:
    # Keep the migration's conservative historical drain tied to the validated
    # configuration ceiling without importing a live settings instance.
    from stoma3d_platform.config import Settings

    transfer = Settings.model_fields["object_transfer_lifetime_seconds"]
    completion = Settings.model_fields["upload_completion_quiet_seconds"]
    transfer_max = next(item.le for item in transfer.metadata if hasattr(item, "le"))
    completion_max = next(
        item.le for item in completion.metadata if hasattr(item, "le")
    )
    assert timedelta(seconds=transfer_max + completion_max) == timedelta(seconds=1800)
