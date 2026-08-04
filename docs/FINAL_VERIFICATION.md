# Final local verification

Date: 2026-07-28

This is the current engineering record. It does not claim clinical accuracy,
physical-device approval, or app-store approval.

## Automated checks passed

| Check                              | Result                                                          |
| ---------------------------------- | --------------------------------------------------------------- |
| TypeScript contracts               | 9 tests passed                                                  |
| Mobile policies and utilities      | 66 tests passed                                                 |
| Inference and ML                   | 88 passed; 1 optional Torch-only test skipped                   |
| TypeScript type checking           | Passed                                                          |
| Prettier                           | Passed                                                          |
| Ruff lint and format               | Passed                                                          |
| Repository safety audit            | Passed                                                          |
| Expo Doctor                        | 20/20 checks passed                                             |
| Expo public configuration          | Passed                                                          |
| Android JavaScript export          | Passed; 2,157 modules                                           |
| iOS JavaScript export              | Passed; 2,081 modules                                           |
| Mobile production endpoint         | Live HTTPS URL and response key embedded on both platforms      |
| Mobile fixture absence             | Neither bundle contains the fixture hash, bytes, ID, or version |
| Live loopback HTTP smoke           | All four routes passed; anatomy and segmentation ready          |
| Vercel production deployment       | `READY`; all four routes signed and verified                    |
| JavaScript dependency audit        | No known vulnerabilities                                        |
| Production Python dependency audit | No known vulnerabilities                                        |

The Python test suite includes EXIF removal, bounded upload handling, closed
multipart streams, request-log redaction, safe error envelopes, signed-response
verification, release-manifest failure cases, model-adapter validation, and
comparison suppression.

Contract version `1.1.0` represents unavailable dataset-similarity and
independent-ensemble factors as `null`. The installed UI and report render those
fields as “Not assessed” instead of showing an invented-looking `0%`.
Encrypted state written by contract `1.0.0` has a tested migration to the
current schema. Legacy live-model records drop those unsupported scores during
migration; exact fixture-derived records preserve them.

## Locked model decisions

| Head                      | Decision                         | Evidence                                                                                                           |
| ------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Anatomy                   | Enabled for region matching only | Macro F1 `0.9842`; lowest region recall `0.9302`; calibration error `0.0123`; 376 images from 47 held-out patients |
| Segmentation              | Enabled for candidate masks only | Dice `0.7192`; boundary F1 `0.6256`; 106 images from 39 held-out patients                                          |
| Disease-category research | Disabled                         | Macro F1 `0.3596`; calibration error `0.0827`; insufficient held-out patients; no signed clinical review           |
| Appearance                | Disabled                         | Required seven-class labels and held-out support are unavailable                                                   |
| Re-identification         | Disabled                         | Required longitudinal matched and hard-negative pairs are unavailable                                              |

Passing the anatomy and segmentation engineering gates does not establish
clinical validity.

The segmentation artifact was selected from validation before its exact
evaluation, with no patient overlap. Earlier failed candidates had already
been evaluated on the same SMART-OM test split, so the result is
patient-disjoint but not a pristine project-wide test.

## Android native flow passed

The installed development build and real FastAPI service completed:

- a fresh cold-boot launch of the final source bundle;
- current 3D map rendering, an interactive rotation, and persisted pin display;
- a live in-app model-card fetch showing segmentation and anatomy enabled while
  appearance, disease research, and re-identification remain disabled;
- two separate eight-region scan sessions;
- one accepted saved photo for each region in both sessions;
- a real anatomy mismatch rejection;
- local quality and on-device face checks;
- manual mouth-only and region confirmation;
- signed API-response verification with the released anatomy model;
- a released segmentation-model run on a separately licensed right-inner-cheek
  image, producing a visible approximate candidate outline and area `16.1%`;
- explicit privacy, selected-region, and observation-pin confirmation;
- persistence of the live-model result, confirmed pin, timeline entry, and
  `1 of 8` scan state after app restart;
- a mandatory user-confirmed cross-session comparison;
- registration diagnostics with suppressed numeric change;
- persisted timeline and oral observation map state;
- an encrypted eight-image PDF generated in 33 seconds;
- a generated eight-region report map showing accepted/pending regions and
  user-confirmed observation pins;
- temporary PDF sharing and cleanup.

No fixture or cached demonstration output was used in these flows.

## Android privacy, recovery, and accessibility checks passed

- Offline analysis saved the real photo encrypted and showed `Analysis
unavailable`.
- The offline result said no substitute result was created and remained
  retryable after restart.
- A later signed retry ran the live anatomy model successfully.
- A signed but malformed JSON response was rejected as unreadable.
- A request exceeding the 18-second client deadline showed the timeout message
  and kept the encrypted photo.
- Camera permission denial kept the photo-library fallback available.
- Canceling the photo picker created no observation or temporary copy.
- Private image and database prefixes were not readable JPEG or SQLite headers.
- No plaintext private JPG, PNG, or PDF remained in app storage after leaving
  the screen.
- Delete-all removed 18 encrypted blobs, cleared records and consent, recreated
  an empty database, rotated both key records, and remained empty after restart.
- Large system text plus the app's large-text, high-contrast, and reduced-motion
  settings remained readable and scrollable together.
- Android accessibility nodes exposed labels, roles, checked states, and
  non-color status text for the tested controls.

## Packaging

`scripts/package-source.ps1` creates a source ZIP from Git's tracked and
non-ignored source-file list. It excludes local dependencies, exports, caches,
secrets, medical images, databases, temporary test files, unapproved model
artifacts, and generated native build output. It includes the two audited
release ONNX files needed by the service. The packaging command reports the
archive path, file count, byte size, and SHA-256. It includes the three audited
release ONNX files needed for face-presence checks, anatomy matching, and
candidate-mask inference.

## Production API passed

The exact Vercel production deployment is `dpl_HZ8iohaU7dP7wseU5z2fEk8whG79`
and is aliased at `https://oralsight-inference.vercel.app`.

- `GET /api/healthz` reported the production service and both released heads
  ready, no retained data, and demonstration fixtures disabled.
- `GET /api/v1/model-card` exposed the exact artifact hashes, passed anatomy
  and segmentation gates, disabled failed or unavailable heads, and limitations.
- `POST /api/v1/analyze` ran the live anatomy model on newly generated request
  bytes and returned `analysisOrigin: live_model`.
- `POST /api/v1/compare` required the supplied prior-analysis contract and
  suppressed comparison without user confirmation.
- All four responses returned `Cache-Control: no-store`, echoed a unique
  request ID, and passed exact-body Ed25519 verification against key ID
  `284e2295626048d0`.
- Vercel installs the exact tested runtime dependency versions from the service
  package metadata rather than resolving broad version ranges.

## Not completed locally

- No physical iPhone run was possible from the Windows workspace.
- The required two-iPhone/two-Android physical-device matrix is not complete.
- VoiceOver and TalkBack were not exercised on physical devices.
- Physical low-storage, OS backup/restore, and device-specific camera thresholds
  are not verified.
- No production `.aab` or `.ipa` was created because Apple, Google, and Expo
  account credentials are external.
- Review priority remains disabled because no clinician-approved rule file is
  installed.
- No source-wide license has been selected by the project owner.
- NeuroSight and Parkinson-related assessment remain a static roadmap only.

> **This result is not a diagnosis.** Passing software checks does not establish
> safety, effectiveness, regulatory status, or clinical validity.
