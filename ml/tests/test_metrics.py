from __future__ import annotations

import unittest

from oralsight_ml.metrics import (
    classification_metrics,
    expected_calibration_error,
    multiclass_calibration_metrics,
    wilson_lower_bound,
)
from oralsight_ml.release_training import (
    _largest_connected_components,
    _presence_positive_weight,
    _segmentation_gate_selection_key,
    _segmentation_selection_score,
)


class MetricTests(unittest.TestCase):
    def test_expected_calibration_error_known_value(self) -> None:
        result = expected_calibration_error([0.9, 0.8], [True, False], bins=1)
        self.assertAlmostEqual(result, 0.35)

    def test_multiclass_metrics(self) -> None:
        labels = ["a", "b"]
        metrics = multiclass_calibration_metrics(
            ["a", "b"],
            [{"a": 0.8, "b": 0.2}, {"a": 0.3, "b": 0.7}],
            labels,
            bins=2,
        )
        self.assertEqual(metrics["sample_count"], 2)
        self.assertAlmostEqual(float(metrics["multiclass_brier_score"]), 0.13)

    def test_classification_report_has_recall_and_specificity(self) -> None:
        report = classification_metrics(["a", "a", "b"], ["a", "b", "b"], ["a", "b"])
        self.assertAlmostEqual(float(report["macro_f1"]), 2 / 3)
        self.assertEqual(report["per_class_recall"]["a"], 0.5)
        self.assertEqual(report["per_class_specificity"]["a"], 1.0)

    def test_wilson_lower_bound_is_conservative(self) -> None:
        lower = wilson_lower_bound(95, 100)
        self.assertLess(lower, 0.95)
        self.assertGreater(lower, 0.85)

    def test_rejects_invalid_probabilities(self) -> None:
        with self.assertRaises(ValueError):
            expected_calibration_error([1.2], [True])

    def test_segmentation_checkpoint_score_values_positive_mask_quality(self) -> None:
        aggregate_only = {
            "dice": 0.76,
            "boundary_f1": 0.62,
            "positive_dice": 0.40,
            "positive_boundary_f1": 0.30,
        }
        positive_quality = {
            "dice": 0.74,
            "boundary_f1": 0.60,
            "positive_dice": 0.60,
            "positive_boundary_f1": 0.50,
        }

        self.assertGreater(
            _segmentation_selection_score(positive_quality),
            _segmentation_selection_score(aggregate_only),
        )

    def test_segmentation_checkpoint_selection_prefers_passing_both_gates(self) -> None:
        higher_blended_but_boundary_fails = {
            "dice": 0.76,
            "boundary_f1": 0.599,
            "positive_dice": 0.68,
            "positive_boundary_f1": 0.36,
        }
        passes_both = {
            "dice": 0.74,
            "boundary_f1": 0.605,
            "positive_dice": 0.61,
            "positive_boundary_f1": 0.32,
        }

        self.assertGreater(
            _segmentation_gate_selection_key(passes_both),
            _segmentation_gate_selection_key(higher_blended_but_boundary_fails),
        )

    def test_segmentation_checkpoint_selection_prefers_positive_masks_after_gate(self) -> None:
        empty_image_dominated = {
            "dice": 0.77,
            "boundary_f1": 0.65,
            "positive_dice": 0.54,
            "positive_boundary_f1": 0.31,
        }
        stronger_positive_masks = {
            "dice": 0.75,
            "boundary_f1": 0.62,
            "positive_dice": 0.67,
            "positive_boundary_f1": 0.41,
        }

        self.assertGreater(
            _segmentation_gate_selection_key(stronger_positive_masks),
            _segmentation_gate_selection_key(empty_image_dominated),
        )

    def test_presence_weight_balances_one_sided_training_supplement(self) -> None:
        self.assertEqual(_presence_positive_weight(600, 225), 0.375)
        self.assertEqual(_presence_positive_weight(225, 225), 1.0)

    def test_largest_component_postprocessing_keeps_one_candidate(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("Optional research dependencies are not installed.")
        predictions = torch.zeros((1, 1, 8, 8), dtype=torch.bool)
        predictions[0, 0, 1:4, 1:4] = True
        predictions[0, 0, 6, 6] = True

        filtered = _largest_connected_components(torch, predictions)

        self.assertEqual(int(filtered.sum().item()), 9)
        self.assertFalse(bool(filtered[0, 0, 6, 6]))


if __name__ == "__main__":
    unittest.main()
