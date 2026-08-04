from __future__ import annotations

import unittest

from oralsight_ml.gates import evaluate_release_gates

from .helpers import copied_passing_evaluation, passing_evaluation


class ReleaseGateTests(unittest.TestCase):
    def test_exact_thresholds_pass(self) -> None:
        report = evaluate_release_gates(passing_evaluation())
        self.assertTrue(all(head["enabled"] for head in report["heads"].values()))

    def test_missing_evidence_fails_closed(self) -> None:
        report = evaluate_release_gates({"evaluation_id": "missing"})
        self.assertTrue(all(not head["enabled"] for head in report["heads"].values()))
        self.assertTrue(report["heads"]["disease"]["reasons"])

    def test_disease_requires_signed_review(self) -> None:
        payload = copied_passing_evaluation()
        payload["disease"]["clinical_review_signed"] = False
        report = evaluate_release_gates(payload)
        self.assertFalse(report["heads"]["disease"]["enabled"])
        self.assertTrue(
            any(
                "clinical_review_signed" in reason
                for reason in report["heads"]["disease"]["reasons"]
            )
        )

    def test_reidentification_uses_confidence_bound_not_only_point_precision(self) -> None:
        payload = copied_passing_evaluation()
        payload["reidentification"]["true_positive_matches"] = 19
        payload["reidentification"]["false_positive_matches"] = 1
        report = evaluate_release_gates(payload)
        decision = report["heads"]["reidentification"]
        self.assertFalse(decision["enabled"])
        self.assertEqual(decision["observed"]["precision"], 0.95)
        self.assertTrue(any("precision_lower_95" in reason for reason in decision["reasons"]))

    def test_metrics_outside_unit_interval_fail_closed(self) -> None:
        payload = copied_passing_evaluation()
        payload["segmentation"]["dice"] = 1.2
        payload["appearance"]["expected_calibration_error"] = -0.01
        payload["disease"]["per_class_specificity"]["normal"] = 1.01
        report = evaluate_release_gates(payload)
        self.assertFalse(report["heads"]["segmentation"]["enabled"])
        self.assertFalse(report["heads"]["appearance"]["enabled"])
        self.assertFalse(report["heads"]["disease"]["enabled"])

    def test_reidentification_counts_must_be_internally_consistent(self) -> None:
        payload = copied_passing_evaluation()
        payload["reidentification"]["true_positive_matches"] = 401
        payload["reidentification"]["false_positive_matches"] = 401
        report = evaluate_release_gates(payload)
        decision = report["heads"]["reidentification"]
        self.assertFalse(decision["enabled"])
        self.assertTrue(any("cannot exceed" in reason for reason in decision["reasons"]))


if __name__ == "__main__":
    unittest.main()
