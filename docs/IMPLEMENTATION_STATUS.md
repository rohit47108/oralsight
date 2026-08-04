# OralSight implementation status

Last updated: 2026-07-28

> **This result is not a diagnosis.** OralSight is a non-diagnostic research
> application. No result establishes that an area is cancerous or harmless.

## What is working

The installed mobile app uses real camera or photo-library input. It does not
contain a sample mouth photo or substitute a fixture result for a live failure.

The working flow is:

1. Record consent and symptom context.
2. Start a scan with the fixed eight mouth regions.
3. Capture or choose one photo per region.
4. Re-encode the photo without source metadata.
5. Run local image-quality and face-presence checks.
6. Require the user to confirm mouth-only framing and the selected region.
7. Encrypt the accepted photo locally.
8. Send only the sanitized copy to the stateless service.
9. Verify the signed response, request ID, schema, region, capture ID, and
   provenance before saving it.
10. Reopen or retry the protected observation.
11. Compare confirmed observations from separate scan sessions.
12. Show history on the oral observation map and create an encrypted local PDF
    after all eight regions are complete.
13. Delete all local data and rotate both installation keys.

Two separate real 8/8 sessions completed on the Android emulator. Each accepted
photo passed the phone checks and the live FastAPI service. A deliberately
mismatched mouth-region photo was rejected and did not count. The app then
completed a real user-confirmed comparison, stored its honest suppression
reasons, rendered the timeline and oral map, and generated an eight-image PDF.

After segmentation promotion, a separately licensed right-inner-cheek image
also completed the installed-app flow. The phone reported 100% focus and
exposure scores, required privacy and region confirmation, returned a live
candidate outline and approximate area `16.1%`, saved a confirmed observation
pin, and preserved the result after app restart. The raw picker files were
removed from the emulator afterward.

## Learned model state

The anatomy model is enabled for one narrow job: checking that the photo matches
the selected mouth region. Its patient-disjoint locked test passed:

- macro F1: `0.9842`;
- lowest region recall: `0.9302`;
- calibration error: `0.0123`;
- test set: 376 images from 47 held-out patients.

The lesion-segmentation model is enabled only for non-diagnostic candidate
outlining and approximate visual descriptors. Its exact frozen,
patient-disjoint test passed the required aggregate gate:

- Dice: `0.7192`, above the required `0.70`;
- boundary F1: `0.6256`, above the required `0.60`;
- positive-image Dice: `0.5138`;
- positive-image boundary F1: `0.3266`;
- test set: 106 images from 39 held-out patients.

The lower positive-image scores and same-dataset evaluation remain important
limitations. A missing candidate mask is never presented as reassurance.
Earlier failed candidates had already been evaluated on the same SMART-OM test
split, so it remains patient-disjoint but is not a pristine project-wide test.

The disease-category research model is not enabled. Its final locked test also
failed:

- macro F1: `0.3596`, below `0.80`;
- calibration error: `0.0827`, above `0.05`;
- held-out patients: normal 43, variation 17, OPMD 9, oral cancer 2;
- no signed clinical review.

SMART-OM does not provide the required seven-class appearance labels or
longitudinal re-identification pairs. Appearance and re-identification therefore
remain disabled. The app can show a released candidate mask and lesion pin, but
it shows no appearance class, disease class, automated lesion identity, or
numeric longitudinal change while those gates are closed.

## Privacy and failure checks completed

On the Android emulator:

- the database and image/report files were confirmed encrypted;
- no plaintext private JPG, PNG, or PDF remained after leaving its screen;
- picker, capture, preview, and share temporary files were removed;
- a signed API response was accepted and a signed malformed response was
  rejected;
- offline, timeout, camera-denied, canceled-picker, mismatched-region, and retry
  paths kept or removed data as specified;
- a failed live request produced `Analysis unavailable` and no substitute
  fixture result;
- delete-all removed 18 encrypted blobs, replaced the database, cleared consent
  and history, rotated both keys, and stayed empty after restart;
- large system text, the app's larger-text option, high contrast, and reduced
  motion remained usable together;
- accessible labels were present for switches, scan regions, map controls,
  comparison controls, and deletion.

## Software verification

- 9 contract tests passed.
- 66 mobile tests passed.
- 88 inference and ML tests passed; 1 optional Torch-only test was skipped in
  the lightweight verification environment.
- TypeScript type checking passed.
- Prettier passed.
- Ruff lint and format checks passed.
- Expo Doctor passed 20/20 checks.
- Fresh Android and iOS production JavaScript exports passed.
- Neither mobile export contains the backend test fixture.
- The production API is live and all four signed routes passed remote checks.
- Repository and dependency audits passed.

See `FINAL_VERIFICATION.md` for the exact snapshot.
See `REQUIREMENT_AUDIT.md` for the requirement-by-requirement verdict.

## Work that still requires external access or evidence

The code is implemented, but competition release still requires:

1. Runs on two physical iPhones and two physical Android phones, including
   VoiceOver/TalkBack, camera thresholds, GPU rendering, low storage, sharing,
   backup behavior, interruption, and complete deletion.
2. A clinician-approved review-priority rule file. Until then, urgency levels
   remain disabled and the app gives neutral seek-care information.
3. Human review of final wording, demo cases, source licensing, and third-party
   license inventory.
4. Platform-level ingress, upload-spool, and proxy-log review for the live API.
5. Expo, Apple, and Google credentials for installable signed store builds.
6. Better licensed data and passed locked gates before appearance,
   disease-category, or re-identification output can be enabled.

The live Vercel deployment hosts the FastAPI service. It cannot replace the
installed iOS/Android app; native builds still come from Expo/EAS or the
platform build tools.

## Parkinson feature

NeuroSight and every Parkinson-related capture, model, score, report, and care
flow remain unimplemented. The app contains only the requested static roadmap.
That work starts only after OralSight's remaining release checks are complete.
