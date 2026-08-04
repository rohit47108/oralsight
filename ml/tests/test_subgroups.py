from __future__ import annotations

import json
import unittest

from oralsight_ml.subgroups import build_subgroup_report


class SubgroupTests(unittest.TestCase):
    def test_suppresses_small_groups_and_omits_patient_ids(self) -> None:
        records = [
            {
                "patient_id": "synthetic-a",
                "device": "ios",
                "y_true": "normal",
                "y_pred": "normal",
                "probabilities": {"normal": 0.9, "variation": 0.1},
            },
            {
                "patient_id": "synthetic-b",
                "device": "android",
                "y_true": "variation",
                "y_pred": "variation",
                "probabilities": {"normal": 0.2, "variation": 0.8},
            },
            {
                "patient_id": "synthetic-c",
                "device": "android",
                "y_true": "normal",
                "y_pred": "normal",
                "probabilities": {"normal": 0.7, "variation": 0.3},
            },
        ]
        report = build_subgroup_report(
            records, labels=["normal", "variation"], subgroup_fields=["device"], minimum_patients=2
        )
        self.assertTrue(report["subgroups"]["device"]["ios"]["suppressed"])
        self.assertFalse(report["subgroups"]["device"]["android"]["suppressed"])
        encoded = json.dumps(report)
        self.assertNotIn("synthetic-a", encoded)
        self.assertNotIn("synthetic-b", encoded)


if __name__ == "__main__":
    unittest.main()
