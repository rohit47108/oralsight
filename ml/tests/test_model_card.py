from __future__ import annotations

import unittest

from oralsight_ml.model_card import generate_model_card

from .helpers import passing_evaluation


class ModelCardTests(unittest.TestCase):
    def test_card_includes_gate_and_safety_language(self) -> None:
        metadata = {
            "model_name": "synthetic-anatomy-baseline",
            "version": "test-only",
            "task": "anatomy",
            "artifact_sha256": "a" * 64,
            "owner": "test suite",
            "training_code_version": "c" * 40,
            "evaluation_date": "2026-07-21T12:00:00Z",
            "intended_uses": ["Synthetic threshold testing."],
            "out_of_scope_uses": ["Diagnosis or care guidance."],
            "limitations": ["No clinical data were used."],
            "datasets": [
                {
                    "name": "synthetic fixtures",
                    "version": "1",
                    "role": "test",
                    "license_status": "approved",
                    "provenance_status": "complete",
                }
            ],
        }
        card = generate_model_card(metadata, passing_evaluation())
        self.assertIn("Release status: **ENABLED**", card)
        self.assertIn("This result is not a diagnosis", card)
        self.assertIn("does not establish clinical validity", card)

    def test_card_rejects_metrics_for_a_different_artifact(self) -> None:
        metadata = {
            "model_name": "synthetic-anatomy-baseline",
            "version": "test-only",
            "task": "anatomy",
            "artifact_sha256": "d" * 64,
            "owner": "test suite",
            "training_code_version": "c" * 40,
            "evaluation_date": "2026-07-21T12:00:00Z",
            "intended_uses": ["Synthetic threshold testing."],
            "out_of_scope_uses": ["Diagnosis or care guidance."],
            "limitations": ["No clinical data were used."],
            "datasets": [
                {
                    "name": "synthetic fixtures",
                    "version": "1",
                    "role": "test",
                    "license_status": "approved",
                    "provenance_status": "complete",
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "artifact_sha256"):
            generate_model_card(metadata, passing_evaluation())


if __name__ == "__main__":
    unittest.main()
