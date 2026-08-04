# Packaged model release

This directory is copied into the inference container.

- `anatomy.onnx` is enabled only for selected-region matching.
- `segmentation.onnx` is enabled only for non-diagnostic candidate-region
  outlining and approximate visual descriptors.
- `release-manifest.json` pins both hashes, tensor interfaces, release metrics,
  review files, and limitations.
- `locked-test-anatomy-evaluation.json` and
  `locked-test-segmentation-evaluation.json` are the patient-disjoint
  evaluation records.
- Appearance, disease-category research, and lesion re-identification remain
  disabled because the available data does not satisfy their specified gates.

No training images, patient data, private signing keys, or clinical claims
belong in this directory.

This result is not a diagnosis.
