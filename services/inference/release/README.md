# Packaged model release

This directory is the redistributable public model release copied into the
inference container.

- `anatomy.onnx` is enabled only for selected-region matching.
- `release-manifest.json` enables anatomy and records candidate segmentation as
  externally supplied.
- `locked-test-anatomy-evaluation.json` and
  `locked-test-segmentation-evaluation.json` are the patient-disjoint
  evaluation records.
- Appearance, disease-category research, and lesion re-identification remain
  disabled because the available data does not satisfy their specified gates.

No training images, patient data, private signing keys, or clinical claims
belong in this directory.

The competition inference service receives `segmentation.onnx` and its original
release manifest through the ignored `services/inference/private-release`
directory or an equivalent read-only deployment mount.

This result is not a diagnosis.
