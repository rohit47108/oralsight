# Stoma3D image-quality calibration note

Date: 2026-07-27  
Status: software calibration evidence; physical-device release testing pending

This result is not a diagnosis.

## Face privacy check

The backend uses the MIT-licensed OpenCV Zoo YuNet model
`face_detection_yunet_2023mar.onnx`, pinned by SHA-256:

`8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`

The previous Haar cascade falsely treated close-up mouth anatomy as a face. On a
64-image patient-disjoint SMART-OM test sample covering all eight regions, the
YuNet check produced zero face flags. These mouth-only images are not a full
face-negative benchmark, so physical-device and real-face rejection testing is
still required.

If the YuNet file is missing, altered, unreadable, or cannot run, backend quality
checking fails closed and rejects the upload as `face_check_unavailable`.

## Blur threshold

The backend blur threshold is `0.09` on the documented normalized Laplacian
score.

- The threshold was selected from the patient-disjoint SMART-OM validation
  partition, where fewer than 15% of source research images fall below it.
- On 80 validation images with a controlled Gaussian blur of sigma 1.0, 7 of 80
  remained above the threshold, a synthetic false-acceptance rate of 8.75%.
- Stronger synthetic blur was rejected more often.

These figures are development evidence, not the required two-iPhone and
two-Android physical-device study. Lighting, camera processing, framing, and
motion differ on real phones. The competition release still requires the
specified physical-device false-acceptance and false-rejection measurements.
