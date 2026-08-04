# Intended use and forbidden claims

## Fixed intended use

The following is the proposed competition intended use, not a statement that every
capability is released in the current working tree. OralSight is a student-directed,
AI-assisted, non-diagnostic research prototype intended to help a person:

- follow a structured eight-region oral photography workflow;
- recognize and retake visibly poor photographs and, only after a validated release gate,
  anatomically mismatched photographs;
- view candidate regions and approximate visual descriptors with uncertainty;
- compare user-confirmed observations over time when images are sufficiently comparable;
- organize those observations on a generic oral observation map; and
- prepare a local observation report and questions for discussion with a dentist or
  physician.

It is not a substitute for a dentist, physician, biopsy, pathology, or clinical
examination. Image findings and symptoms can support communication, but they cannot
diagnose an oral condition. Every result screen and report must include:

> **This result is not a diagnosis.**

## Audience and operating limits

- Competition demonstration and supervised research-prototype evaluation only.
- Smartphone photographs of the fixed eight visible oral regions.
- One accepted image per region in v1; no video sweeps, depth reconstruction, physical
  calibration, or millimeter measurements.
- Generic anatomical mapping only. Use “oral observation map,” never “personalized
  digital twin.”
- Approximate normalized measurements only, always paired with image-quality,
  registration, and uncertainty limitations.

## Forbidden public, in-app, report, and judge-demo claims

Never state or imply that OralSight:

- diagnoses, detects, confirms, rules out, or predicts cancer or any other disease;
- proves that an area is benign, harmless, malignant, precancerous, or normal;
- replaces professional examination, biopsy, histopathology, or medical judgment;
- is clinically accurate, clinically validated, FDA approved/cleared, or a medical
  device exempt from oversight;
- is HIPAA compliant, privacy certified, secure under every threat, or legally compliant;
- measures lesion dimensions in millimeters without a validated physical reference;
- automatically knows two observations are the same lesion;
- produces a personalized anatomical reconstruction in the competition version; or
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
