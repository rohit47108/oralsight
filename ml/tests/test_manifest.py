from __future__ import annotations

import unittest

from stoma3d_ml.manifest import validate_manifest

from .helpers import manifest_row


class ManifestValidationTests(unittest.TestCase):
    def test_accepts_patient_disjoint_synthetic_metadata(self) -> None:
        rows = [
            manifest_row(),
            manifest_row(
                sample_id="sample-2",
                patient_id="patient-beta",
                split="validation",
                image_path="images/sample-2.jpg",
                mask_path="masks/sample-2.png",
                lesion_id="lesion-beta",
                consent_scope="evaluation_only",
            ),
        ]
        report = validate_manifest(rows, require_audited=True)
        self.assertTrue(report.valid, report.as_dict())
        self.assertEqual(report.patient_count, 2)

    def test_rejects_patient_leakage_across_splits(self) -> None:
        rows = [
            manifest_row(),
            manifest_row(
                sample_id="sample-2",
                split="test",
                image_path="images/sample-2.jpg",
                mask_path="masks/sample-2.png",
                consent_scope="evaluation_only",
            ),
        ]
        report = validate_manifest(rows)
        self.assertFalse(report.valid)
        self.assertIn("patient_split_leakage", {issue.code for issue in report.issues})

    def test_rejects_unsafe_paths_and_unapproved_data(self) -> None:
        row = manifest_row(
            image_path="../private/patient.jpg",
            license_status="pending",
            audit_status="pending",
        )
        report = validate_manifest([row], require_audited=True)
        codes = {issue.code for issue in report.issues}
        self.assertTrue({"unsafe_image_path", "license_not_approved", "data_not_audited"} <= codes)

    def test_task_validation_requires_canonical_labels(self) -> None:
        report = validate_manifest([manifest_row(anatomy_label="roof_of_mouth")], task="anatomy")
        self.assertFalse(report.valid)
        self.assertIn("invalid_task_label", {issue.code for issue in report.issues})


if __name__ == "__main__":
    unittest.main()
