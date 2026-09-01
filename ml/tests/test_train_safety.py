from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from stoma3d_ml.baselines import _log_local_mlflow
from stoma3d_ml.manifest import REQUIRED_COLUMNS
from stoma3d_ml.train import main

from .helpers import manifest_row


class TrainingSafetyTests(unittest.TestCase):
    def test_mlflow_uri_rejects_loopback_prefix_bypasses(self) -> None:
        for uri in (
            "http://localhost.evil.example",
            "http://127.0.0.1.evil.example",
            "file://remote-host/share",
            "http://user:secret@localhost:5000",
        ):
            with (
                self.subTest(uri=uri),
                self.assertRaisesRegex(RuntimeError, "local file or loopback"),
            ):
                _log_local_mlflow(
                    uri,
                    task="anatomy",
                    run_id="test",
                    params={},
                    metrics={},
                )

    def test_refuses_unaudited_or_missing_files_before_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_root = root / "controlled-data"
            data_root.mkdir()
            manifest = root / "manifest.csv"
            row = manifest_row(audit_status="pending")
            with manifest.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            output = root / "artifacts" / "run"
            result = main(
                [
                    "--task",
                    "anatomy",
                    "--manifest",
                    str(manifest),
                    "--data-root",
                    str(data_root),
                    "--output-dir",
                    str(output),
                    "--acknowledge-audited-data",
                    "--dry-run",
                ]
            )
            self.assertEqual(result, 2)
            self.assertFalse(output.exists())

    def test_requires_explicit_audit_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = main(
                [
                    "--task",
                    "anatomy",
                    "--manifest",
                    str(root / "missing.csv"),
                    "--data-root",
                    str(root),
                    "--output-dir",
                    str(root / "output"),
                ]
            )
            self.assertEqual(result, 2)
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
