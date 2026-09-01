from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from stoma3d_ml.reidentification_release import (
    PAIR_MANIFEST_COLUMNS,
    binary_match_metrics,
    generate_deterministic_pairs,
    load_pair_manifest,
    pair_inventory,
    pair_manifest_sha256,
    release_gate_from_locked_test,
    select_precision_first_threshold,
)

from .helpers import manifest_row


def _samples() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for split_index, split in enumerate(("train", "validation", "test")):
        consent = "research_training" if split == "train" else "evaluation_only"
        for lesion_index in range(2):
            patient_id = f"patient-{split_index}-{lesion_index}"
            lesion_id = f"lesion-{split_index}-{lesion_index}"
            for capture_index in range(2):
                sample_id = f"sample-{split_index}-{lesion_index}-{capture_index}"
                rows.append(
                    manifest_row(
                        sample_id=sample_id,
                        patient_id=patient_id,
                        lesion_id=lesion_id,
                        split=split,
                        consent_scope=consent,
                        image_path=f"images/{sample_id}.jpg",
                        appearance_label="red-patch",
                        device_family="test-phone",
                    )
                )
    return rows


class PairManifestTests(unittest.TestCase):
    def test_generated_pairs_are_deterministic_and_region_matched(self) -> None:
        samples = _samples()
        first = generate_deterministic_pairs(samples, seed=41)
        second = generate_deterministic_pairs(list(reversed(samples)), seed=41)
        self.assertEqual(first, second)
        self.assertEqual(pair_manifest_sha256(first), pair_manifest_sha256(second))
        inventory = pair_inventory(first, samples=samples)
        for split in ("train", "validation", "test"):
            self.assertEqual(inventory[split]["matched_pairs"], 2)
            self.assertGreaterEqual(inventory[split]["hard_negative_pairs"], 2)

        sample_by_id = {sample["sample_id"]: sample for sample in samples}
        for pair in first:
            if pair.expected_match:
                continue
            left = sample_by_id[pair.first_sample_id]
            right = sample_by_id[pair.second_sample_id]
            self.assertEqual(left["region"], right["region"])
            self.assertNotEqual(
                (left["patient_id"], left["lesion_id"]),
                (right["patient_id"], right["lesion_id"]),
            )

    def test_explicit_pair_manifest_rejects_split_leak_and_invalid_positive(self) -> None:
        samples = _samples()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairs.csv"
            row = {
                "pair_id": "bad-pair",
                "split": "train",
                "first_sample_id": "sample-0-0-0",
                "second_sample_id": "sample-1-0-0",
                "expected_match": "true",
                "pair_kind": "matched",
            }
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=PAIR_MANIFEST_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "both samples must belong"):
                load_pair_manifest(path, samples=samples)


class ThresholdAndGateTests(unittest.TestCase):
    def test_threshold_selection_is_validation_precision_first(self) -> None:
        scores = [0.99, 0.90, 0.80, 0.70, 0.60, 0.59]
        expected = [True, True, True, False, True, False]
        selected = select_precision_first_threshold(scores, expected, minimum_precision=0.95)
        self.assertGreaterEqual(float(selected["precision"]), 0.95)
        self.assertEqual(float(selected["threshold"]), 0.8)
        self.assertAlmostEqual(float(selected["recall"]), 0.75)

        locked = binary_match_metrics(scores, expected, threshold=float(selected["threshold"]))
        self.assertEqual(locked["true_positive_matches"], 3)
        self.assertEqual(locked["false_positive_matches"], 0)

    def test_release_stays_closed_until_counts_and_confidence_bound_pass(self) -> None:
        small = binary_match_metrics(
            [0.9] * 20 + [0.1] * 20,
            [True] * 20 + [False] * 20,
            threshold=0.5,
        )
        closed = release_gate_from_locked_test(
            small,
            matched_pairs=20,
            hard_negative_pairs=20,
            held_out_patients=10,
            patient_disjoint=True,
        )
        self.assertFalse(closed["enabled"])
        self.assertTrue(closed["user_confirmation_required"])
        self.assertFalse(closed["automatic_linking"])

        inconsistent = release_gate_from_locked_test(
            small,
            matched_pairs=200,
            hard_negative_pairs=200,
            held_out_patients=50,
            patient_disjoint=True,
        )
        self.assertFalse(inconsistent["enabled"])
        self.assertTrue(
            any("internally inconsistent" in reason for reason in inconsistent["reasons"])
        )

        passing = binary_match_metrics(
            [0.9] * 200 + [0.1] * 200,
            [True] * 200 + [False] * 200,
            threshold=0.5,
        )
        opened = release_gate_from_locked_test(
            passing,
            matched_pairs=200,
            hard_negative_pairs=200,
            held_out_patients=50,
            patient_disjoint=True,
        )
        self.assertTrue(opened["enabled"])
        self.assertEqual(opened["output_mode"], "candidate_suggestion_only")
        self.assertGreaterEqual(float(opened["precision_lower_95"]), 0.90)


if __name__ == "__main__":
    unittest.main()
