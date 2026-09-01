# Intended use and forbidden claims

## Fixed intended use

Stoma3D is a student-directed, AI-assisted, non-diagnostic research product
intended to help a person:

- follow a structured eight-region oral photography workflow;
- recognize and retake visibly poor photographs and, only after a validated release gate,
  anatomically mismatched photographs;
- view candidate regions and approximate visual descriptors with uncertainty;
- compare user-confirmed observations over time when images are sufficiently comparable;
- organize those observations on a generic oral observation map;
- prepare an observation report and questions for discussion with a dentist or
  physician; and
- optionally sync explicitly selected records to a private account for reports,
  time-limited sharing, generated observation artifacts, and clinician review.

It is not a substitute for a dentist, physician, biopsy, pathology, or clinical
examination. Image findings and symptoms can support communication, but they cannot
diagnose an oral condition. Every result screen and report must include:

> **This result is not a diagnosis.**

## Audience and operating limits

- Competition demonstration and supervised research-product evaluation. A public or
  clinical release requires the separate deployment, privacy, device, data-license,
  and professional-review checks in `docs/DEPLOYMENT.md`.
- Smartphone photographs of the fixed eight visible oral regions.
- One primary accepted image per region, with optional left/right views or a short
  best-frame sweep. Raw sweeps are discarded after selected frames are retained.
- Optional ArUco reference-card calibration may produce approximate millimeter and
  square-millimeter estimates only when the marker and same-plane checks pass.
- The in-app geometry is a generic oral observation map. A private generated GLB may
  project the user's selected images and confirmed pins onto that generic geometry; it
  is not a reconstruction of the person's anatomy or a digital twin.
- Approximate normalized and calibrated measurements are always paired with
  image-quality, registration, calibration, and uncertainty limitations.

## Forbidden public, in-app, report, and judge-demo claims

Never state or imply that Stoma3D:

- diagnoses, detects, confirms, rules out, or predicts cancer or any other disease;
- proves that an area is benign, harmless, malignant, precancerous, or normal;
- replaces professional examination, biopsy, histopathology, or medical judgment;
- is clinically accurate, clinically validated, FDA approved/cleared, or a medical
  device exempt from oversight;
- is HIPAA compliant, privacy certified, secure under every threat, or legally compliant;
- measures dimensions in millimeters without a valid in-frame physical reference and
  explicit approximate-estimate wording;
- automatically knows two observations are the same lesion;
- claims that the projected-color observation surface reconstructs patient anatomy; or
- offers treatment, medication, triage, or emergency-care instructions from an ML class.

Do not present a test-set threshold as a population performance claim. Do not use
“cancer risk heatmap”; use “scan-status map” or “candidate-region overlay.”

## Output hierarchy

1. Quality/anatomy checks may accept, reject, or abstain.
2. The primary analysis may show a candidate mask, normalized area, visual descriptors,
   uncertainty, and limitations only after its gate passes.
3. Appearance categories are descriptive and shown only after their gate passes.
4. Disease-category results, if gated, appear only under “experimental research output.”
   They never change care guidance.
5. Lesion re-identification is a suggestion; the user must confirm every link.
6. Change is shown only after the registration gate passes; otherwise report
   “insufficient comparable data.”
7. Review priority comes only from a versioned, enabled, clinician-signed deterministic
   rule file. Without it, show neutral seek-care information and no urgency level.

## Regulatory and privacy review references

Product wording must be re-reviewed against the current primary sources before release:

- [FDA: How to Determine if Your Product Is a Medical Device](https://www.fda.gov/medical-devices/classify-your-medical-device/how-determine-if-your-product-medical-device)
- [FTC: Complying with the Health Breach Notification Rule](https://www.ftc.gov/business-guidance/resources/complying-ftcs-health-breach-notification-rule-0)

These links guide review; including them does not establish compliance or legal advice.
