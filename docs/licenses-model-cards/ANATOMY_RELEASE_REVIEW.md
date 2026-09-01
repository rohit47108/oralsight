# Stoma3D anatomy-head engineering release review

Review date: 2026-07-27  
Review type: engineering model-contract and release-gate review  
Clinical review: no  
Decision: approved for the non-diagnostic anatomy-matching role described below

This review approves only the model's use as an automated check that the
photographed mouth region matches the region selected by the user. It does not
approve diagnosis, care guidance, appearance classification, disease
classification, or clinical-accuracy claims.

## Evidence checked

- Source: SMART-OM Figshare dataset `31341790`, version 1, CC BY 4.0.
- Split: patient-disjoint, with zero patient overlap among training,
  validation, and test partitions.
- Test set: 376 images from 47 patients.
- Test macro F1: 0.984174.
- Lowest individual region recall: 0.930233.
- Expected calibration error: 0.012302.
- Release requirements: macro F1 at least 0.80 and every region recall at
  least 0.70. Both requirements passed.
- The exported ONNX SHA-256 is
  `335cacfa5ceab8d32d6b903c65d482c246ac6ac2a7e7a831f6ede27d62a553a9`.
- The OpenCV backend loaded the pinned ONNX file and completed startup
  inference validation.

## Required runtime behavior

- The model abstains below its calibrated confidence threshold of 0.77.
- A mismatch or abstention prevents the capture from completing that scan
  region.
- The model output is not displayed as a diagnosis.
- Every stored result retains the model version and artifact hash.
- If the file, hash, manifest, or runtime check fails, this head remains
  disabled.

## Limitations

SMART-OM is a research dataset and does not establish general clinical
validity. Device, lighting, skin-tone, age, anatomy, and capture differences
can reduce performance outside the test data. Physical-device subgroup testing
remains required before competition release.

This result is not a diagnosis.
