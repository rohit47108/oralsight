# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

## Users

People using an iPhone or Android phone to create structured mouth-image observations for themselves or for someone who has given permission. A dentist or medical professional may later read the locally generated report.

## Product Purpose

OralSight helps a user capture one usable image for each of eight named mouth regions, keep those observations protected on the phone, request non-diagnostic image processing, review limitations, compare user-confirmed observations, and prepare a local PDF for a professional discussion.

Success means the ordinary flow works with real phone images and reports failures honestly. A synthetic example must never be mistaken for analysis of a real image.

## Positioning

The product combines a fixed eight-region capture path, transparent provenance, fail-closed research outputs, user-confirmed comparison, a generic oral observation map, and a local clinician-ready report. It does not present itself as a diagnostic product.

## Operating Context

- First-run consent and symptom intake.
- Camera or photo-library input on a physical phone.
- Pre-upload image checks, explicit privacy and region confirmation, protected local storage, and a sanitized upload to the inference service.
- A result that distinguishes completed analysis, abstention, unsupported input, and service failure.
- Reopening prior observations, confirming comparisons, viewing map/timeline context, generating a PDF, and deleting all local data.

## Capabilities and Constraints

- The canonical mouth regions are `dorsal_tongue`, `ventral_tongue`, `left_buccal_mucosa`, `right_buccal_mucosa`, `upper_lip`, `lower_lip`, `upper_dental_arch`, and `lower_dental_arch`.
- The product is non-diagnostic. Every screen and report states: "This result is not a diagnosis."
- A scan is complete after one quality-accepted, user-confirmed image is protected for every region. Model analysis may abstain without fabricating a result.
- Normal use must not rely on bundled images, synthetic coverage records, hard-coded scores, or fixture fallbacks.
- The observation map is generic and versioned, not a personalized digital twin.
- Measurements are approximate and image-normalized. No millimeter claims are allowed.
- Research heads remain disabled until their documented release gates and reviews pass.
- Review priority remains disabled until a versioned clinician-approved rule file is installed.
- The backend is stateless and retains no image jobs or accounts.
- Production phone use requires an HTTPS inference endpoint and a pinned response-signing public key.
- NeuroSight and Parkinson-specific assessment are outside the current product scope.

## Brand Commitments

The product name is OralSight. Its voice is calm, direct, and specific. It avoids medical hype, vague reassurance, invented precision, and technical language that does not help the user.

## Evidence on Hand

- A working Expo/React Native application and FastAPI service in this repository.
- Real image-quality preprocessing, encrypted local files, SQLCipher configuration, signed-response verification, local PDF generation, and a generic procedural oral map.
- The two released models are hash-pinned and backed by patient-disjoint engineering evaluations: eight-region anatomy matching and candidate-region segmentation. Their documented gates do not establish clinical validity.
- No independent clinical evaluation, released appearance or disease-category model, released re-identification or out-of-distribution model, or clinician-approved guidance file is present. Future work must not fabricate any of those.
- A CC0 synthetic fixture exists for automated tests and explicitly separated developer demonstration only.

## Product Principles

1. Real input, honest output.
2. Privacy before convenience.
3. Users stay in control of capture, comparison, sharing, and deletion.
4. Unavailable analysis is a valid state, never a reason to show fake results.
5. Familiar native controls, accessible layouts, and quiet purposeful feedback.

## Accessibility & Inclusion

Support VoiceOver and TalkBack labels, system text scaling, usable touch targets, safe areas, keyboard and permission states, high contrast, non-color status cues, optional spoken capture instructions, caregiver-assisted capture, and reduced motion.
