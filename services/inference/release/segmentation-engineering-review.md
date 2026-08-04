# OralSight segmentation-head engineering release review

Review date: 2026-07-28  
Review type: engineering model-contract and release-gate review  
Clinical review: no  
Decision: approved only for non-diagnostic candidate-region outlining

This review approves the model only for drawing an approximate mask around one
possible visible observation. It does not approve diagnosis, disease
classification, cancer detection, harmlessness claims, care guidance, or
millimeter measurements.

## Evidence checked

- Evaluation source: SMART-OM Figshare dataset `31341790`, version 1, CC BY
  4.0.
- Training-only supplement: Autooral author training split, under the authors'
  academic-research and non-commercial terms. No Autooral validation or test
  image was used.
- Split: SMART-OM patients are disjoint across training, validation, and test,
  with zero patient overlap.
- Exact frozen test set: 106 images from 39 patients, including 53 masks with a
  candidate region and 53 empty masks.
- Dice: `0.719180`, above the required `0.70`.
- Boundary F1: `0.625561`, above the required `0.60`.
- Positive-image Dice: `0.513831`.
- Positive-image boundary F1: `0.326593`.
- Negative-pixel specificity: `0.981921`.
- The exact exported ONNX SHA-256 is
  `6e0d74557960001b60a181e1fd7444c21c50ca4a30175c8c4449b40298352ac5`.
- OpenCV loaded the exact ONNX file and returned a finite `1 x 1 x 512 x 512`
  output in a CPU inference smoke test.

## Required runtime behavior

- The backend uses the pinned `0.55` mask threshold and retains only the
  largest connected component.
- An empty thresholded mask is reported as no candidate detected, not as proof
  that the image is normal or harmless.
- The result is shown only after image quality and selected-region anatomy
  checks pass.
- Area, shape, color, and texture descriptions are approximate image
  descriptors.
- Every stored result retains the model version and artifact hash.
- If the model file, hash, manifest, tensor contract, or startup inference
  check fails, segmentation remains unavailable.

## Limitations

The aggregate gate passed narrowly and does not establish clinical validity.
Positive-image scores are substantially lower than the aggregate scores.
The SMART-OM test patients were never used for training or threshold selection,
but the same project test split had been evaluated by earlier failed model
candidates. It is therefore patient-disjoint, but no longer a pristine
project-wide test set. This final artifact and its thresholds were frozen from
validation before its exact evaluation.
Performance can change with phone model, lighting, saliva, blur, skin tone,
age, anatomy, lesion type, and capture distance. Physical-device and subgroup
testing remain required before a public competition release.

This result is not a diagnosis.
