from __future__ import annotations

import importlib.util
from pathlib import Path


def _migration_module():
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260815_0012_align_unique_indexes.py"
    )
    spec = importlib.util.spec_from_file_location("schema_alignment_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_schema_alignment_migration_matches_model_unique_indexes(monkeypatch) -> None:
    migration = _migration_module()
    batch_calls: list[tuple[str, str, tuple[str, ...], bool | None]] = []
    direct_calls: list[tuple[str, str]] = []

    class Batch:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def drop_index(self, name):
            batch_calls.append(("drop_index", name, (), None))

        def drop_constraint(self, name, *, type_):
            batch_calls.append(("drop_constraint", name, (type_,), None))

        def create_index(self, name, columns, *, unique):
            batch_calls.append(("create_index", name, tuple(columns), unique))

    monkeypatch.setattr(migration.op, "batch_alter_table", lambda table: Batch())
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda name, *, table_name: direct_calls.append((name, table_name)),
    )

    migration.upgrade()

    assert ("drop_index", "ix_analysis_runs_worker_job_id", (), None) in batch_calls
    assert (
        "drop_constraint",
        "uq_analysis_runs_worker_job_id",
        ("unique",),
        None,
    ) in batch_calls
    assert (
        "create_index",
        "ix_analysis_runs_worker_job_id",
        ("worker_job_id",),
        True,
    ) in batch_calls
    assert direct_calls == [
        (
            "ix_deleted_subject_tombstones_subject_fingerprint",
            "deleted_subject_tombstones",
        )
    ]
