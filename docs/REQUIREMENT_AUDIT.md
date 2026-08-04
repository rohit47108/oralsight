# OralSight requirement audit

Date: 2026-07-28

This audit compares the current repository with:

1. the original “OralSight: Complete Product and Engineering Blueprint”; and
2. the later “OralSight 2026 Competition Build Plan” that the user explicitly
   asked to implement.

The later plan controls where the documents conflict. In particular, it fixes
the scan at eight regions and one accepted image per region, describes the 3D
surface as an oral observation map, and defers multi-angle capture, physical
calibration, personalized reconstruction, QR sharing, clinician portals, and
scan-summary videos.

Verdicts:

- **Verified locally** means current code plus a test, build, runtime check, or
  inspected artifact directly supports the requirement.
- **Gate closed** means the product implements the safe unavailable state
  required by the plan because the evidence needed to expose that output did
  not pass.
- **Deferred by the controlling plan** means the feature must remain a static
  roadmap item rather than appear as working functionality.
- **External release work** means the repository is prepared, but completion
  requires a physical device, clinician, account, credential, or owner decision
  that is not present in the workspace.

> **This result is not a diagnosis.** This is an engineering audit, not evidence
> of clinical validity, safety, effectiveness, or regulatory status.

## Product and safety contract

| Requirement                                                         | Current evidence                                                                                                                                              | Verdict          |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| Fixed eight-region taxonomy everywhere                              | Canonical enum and region metadata in `packages/contracts/src/index.ts`; cross-language taxonomy repository audit                                             | Verified locally |
| Exactly one accepted image per region                               | Replacement and cleanup logic in `useOralSightStore.ts`; completeness logic and tests in `scanLogic.ts`                                                       | Verified locally |
| A scan completes only at 8/8 accepted regions                       | Mobile scan progress and report gate; contract and mobile tests                                                                                               | Verified locally |
| No fake normal-use photos or fallback results                       | Installed mobile bundle contains no mouth fixture; live-input policy rejects cached and fixture response origins; failed requests save `analysis unavailable` | Verified locally |
| Input and analysis provenance remain separate                       | Public contracts, result screen, timeline, comparisons, PDF, and API tests                                                                                    | Verified locally |
| Every screen and report repeats the exact disclaimer                | Shared `Screen` frame and locally generated report footer/header                                                                                              | Verified locally |
| No cancer, harmlessness, HIPAA, or clinical-accuracy claim          | Forbidden-claim documentation, repository text audit, fixed user-facing copy                                                                                  | Verified locally |
| Approximate, image-normalized measurements only                     | Contracts require `measurementLabel: "approximate"`; result, comparison, and report copy prohibit millimeter interpretation                                   | Verified locally |
| Review priority comes only from an approved deterministic rule file | Signed-payload, expiry, scope, and version checks in `guidanceRules.ts`; bundled configuration is deliberately disabled                                       | Gate closed      |

## Real mobile workflow

| Requirement                                  | Current evidence                                                                                                                                   | Verdict          |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| Consent and symptom intake                   | Age, assisted use, first-noticed date, duration, symptoms, change, exposures, prior conditions, prior examination, and two required consent checks | Verified locally |
| Adaptive intake                              | Bleeding questions appear only after bleeding is selected; region-specific capture instructions adapt to the selected scan region                  | Verified locally |
| Camera and saved-photo input                 | Expo Camera and image picker in the installed Android development build                                                                            | Verified locally |
| IMU stability guidance                       | Live accelerometer stability gate and accessible stability indicator                                                                               | Verified locally |
| Immediate quality checks                     | Local focus, exposure, glare, obstruction, resolution, aspect-ratio, and upload-size checks                                                        | Verified locally |
| Accidental face check                        | On-device ML Kit face detection is required before acceptance; server repeats a hash-pinned YuNet face check                                       | Verified locally |
| Anatomy mismatch rejection                   | Released eight-region model plus mobile storage policy; a real mismatch was rejected in the installed app                                          | Verified locally |
| Rejected images are not retained or uploaded | Cleanup paths and tests; emulator storage inspection after rejection                                                                               | Verified locally |
| Manual privacy and region confirmation       | Both checkboxes are required before protected storage and upload                                                                                   | Verified locally |
| Encrypted local capture                      | AES-256-GCM protected file with record-bound associated data; key in SecureStore                                                                   | Verified locally |
| Encrypted SQLCipher database                 | Expo SQLite is configured with SQLCipher; a random database key is stored in SecureStore; emulator file header was not plaintext SQLite            | Verified locally |
| Signed response validation                   | Ed25519 response verification and pinned public key required outside loopback development                                                          | Verified locally |
| Retry and honest failure states              | Offline, timeout, malformed response, canceled picker, and unavailable-analysis paths were exercised                                               | Verified locally |
| Complete local deletion and key rotation     | Database, vault, reports, temporary files, consent, and history are removed; database and vault keys are replaced                                  | Verified locally |

## Analysis and release gates

| Head or output                                         | Current evidence                                                                                                                                                           | Verdict                                              |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Image quality                                          | Local and server deterministic checks with calibration record; physical-device target still pending                                                                        | Verified locally; external device validation remains |
| Anatomy matching                                       | Released hash-pinned ONNX; macro F1 `0.9842`; lowest region recall `0.9302`; calibration error `0.0123`                                                                    | Verified locally                                     |
| Candidate segmentation                                 | Released hash-pinned ONNX; Dice `0.7192`; boundary F1 `0.6256`; visible installed-app mask and descriptors                                                                 | Verified locally                                     |
| Candidate bounding box                                 | Derived from the released segmentation mask, not from a separate detector or heuristic result                                                                              | Verified locally                                     |
| Area, perimeter, shape, color, and texture descriptors | Derived only from the released mask and analyzed pixels                                                                                                                    | Verified locally                                     |
| Uncertainty and limitations                            | Overall and image-quality confidence plus explicit limitations; unavailable dataset-similarity and ensemble factors are now `null` and shown as “Not assessed,” never `0%` | Verified locally                                     |
| Appearance classes                                     | Required labels and held-out class support are unavailable; no class is shown                                                                                              | Gate closed                                          |
| Disease-category research output                       | Locked test failed the required metrics and patient support; expandable panel exposes only the disabled explanation                                                        | Gate closed                                          |
| Automated lesion re-identification                     | Required matched longitudinal and hard-negative data are unavailable; the user may still review and manually confirm a pair                                                | Gate closed                                          |
| Review urgency                                         | No clinician-approved rule file is installed, so the app provides neutral seek-care information only                                                                       | Gate closed                                          |

The segmentation test is patient-disjoint, but earlier failed candidates were
evaluated on the same SMART-OM test split. The result is therefore not a pristine
project-wide test. Positive-image segmentation scores are also materially lower
than the aggregate scores. Both limitations remain in the model card and release
review.

## 3D map, progression, and reporting

| Requirement                             | Current evidence                                                                                                                                                                                              | Verdict                                                             |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Generic rotatable and zoomable oral map | React Three Fiber native procedural map with all eight named meshes, rotation, zoom, exploded mode, dental-arch fading, a named-region fallback, and retry after renderer failure                             | Verified locally                                                    |
| Scan completeness                       | Accepted and pending states appear on both the 3D view and accessible native region list                                                                                                                      | Verified locally                                                    |
| Versioned lesion pins                   | User-confirmed pins persist region ID, mesh ID, UV coordinates, and asset version; world position is calculated during render                                                                                 | Verified locally                                                    |
| Ghost-image follow-up                   | Prior protected capture can be locally decrypted as a temporary low-opacity camera guide and is cleaned up on exit                                                                                            | Verified locally                                                    |
| Mandatory pair confirmation             | Original baseline/current images are shown before the user can link observations                                                                                                                              | Verified locally                                                    |
| Geometric registration                  | ORB landmarks, RANSAC homography, inlier ratio, and normalized reprojection error are calculated from the two uploaded images                                                                                 | Verified locally                                                    |
| Confidence-gated change                 | Change requires user confirmation, 60% inliers, at most 3% reprojection error, a released mask on both images, and passed repeat-capture evidence                                                             | Gate closed for numeric change until repeat-capture evidence passes |
| Before/after comparison                 | Side-by-side originals plus a continuously draggable, tappable, and screen-reader-adjustable blend slider                                                                                                     | Verified locally                                                    |
| Timeline and visual trajectory          | Chronological observations plus an accessible graph of approximate area, symptoms, quality, confidence, comparison status, and map linkage; graph segments require an exact comparison that passed every gate | Verified locally                                                    |
| Clinician-ready local PDF               | Profile, symptoms, consent, generated oral map, original images with mask overlays, measurements, timeline, comparisons, limitations, provenance, model versions, and professional-discussion questions       | Verified locally                                                    |
| PDF protection and sharing              | PDF is generated locally, encrypted immediately, and decrypted only to a short-lived share file                                                                                                               | Verified locally                                                    |

## Backend, contracts, ML, and packaging

| Requirement                              | Current evidence                                                                                                                                                                       | Verdict                                                              |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Only four public routes                  | `POST /v1/analyze`, `POST /v1/compare`, `GET /v1/model-card`, and `GET /healthz`                                                                                                       | Verified locally and on production                                   |
| Stateless processing                     | No accounts, retained jobs, PostgreSQL, S3, Redis, analytics, or image persistence                                                                                                     | Verified locally                                                     |
| No request-body logs or response caching | Access logging disabled; structured logs exclude bodies; `Cache-Control: no-store` enforced and tested                                                                                 | App verified; proxy configuration awaits host review                 |
| Sanitized in-memory processing           | Bounded JPEG/PNG/WebP decode, orientation, metadata stripping, re-encoding, and analysis in memory                                                                                     | Verified locally                                                     |
| Public schema parity                     | TypeScript contract `1.1.0`, mirrored Pydantic models, generated JSON Schema, repository parity audit, and tested migration of encrypted `1.0.0` mobile state                          | Verified locally                                                     |
| Patient-disjoint ML tooling              | Manifest validation rejects patient overlap, duplicate samples, invalid licenses, absolute paths, and traversal                                                                        | Verified locally                                                     |
| Release artifact integrity               | Model interfaces, hashes, metrics, approval evidence, and gates are validated before adapters load                                                                                     | Verified locally                                                     |
| CI                                       | Contract generation, tests, type checking, formatting, dependency audits, mobile exports, repository audit, container build, and health smoke workflows                                | Verified locally in source; hosted GitHub run awaits repository push |
| Clean source ZIP                         | Packager includes audited models and excludes dependencies, data, secrets, caches, exports, and training artifacts; the distributed archive is reread and hash-verified after creation | Verified locally                                                     |

## Accessibility

| Requirement                             | Current evidence                                                                                      | Verdict                                        |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Large text and reflow                   | System scaling plus app larger-text mode; responsive phone, landscape, and tablet widths              | Verified locally                               |
| Screen-reader semantics                 | Labels, roles, selected/checked/busy states, adjustable comparison slider, and native map alternative | Verified locally on Android accessibility tree |
| High contrast and non-color status      | Light/dark high-contrast palettes and persistent text/icon status                                     | Verified locally                               |
| Reduced motion                          | Operating-system preference and app setting jointly disable custom motion                             | Verified locally                               |
| Haptics and spoken capture instructions | Optional haptic results and Expo Speech region instructions                                           | Verified locally                               |
| Physical VoiceOver and TalkBack runs    | Requires physical iPhones and Android phones                                                          | External release work                          |

## Explicitly deferred by the controlling plan

Only static roadmap entries are present for:

- NeuroSight and every Parkinson-related test, model, score, report, and care
  flow;
- personalized 3D reconstruction;
- multi-angle capture and video sweeps;
- physical calibration cards and millimeter measurements;
- clinician portal and annotation workflow;
- expiring QR sharing;
- scan-summary video; and
- the original blueprint's symptom body map, automatic stability capture,
  mirrored scan directions, animated scan path, time-lapse morph, adaptive
  reminders, 3D heatmap, anatomy atlas, variation gallery, scan simulator, and
  knowledge challenges.

## Remaining external release work

These are not code substitutions and must not be fabricated:

1. Test three complete scans on each of two physical iPhones and two physical
   Android devices and calculate the required quality false-accept and
   false-reject rates.
2. Exercise VoiceOver, TalkBack, low storage, interruption, OS backup/restore,
   physical camera thresholds, GPU rendering, PDF sharing, and deletion on that
   device matrix.
3. Obtain clinician approval for an exact versioned guidance-rule payload or
   keep review priority disabled.
4. Obtain production Expo, Apple, and Google signing credentials.
5. Select the source-code license and complete the final human license and
   wording review.
6. Run the final GitHub-hosted CI and deployed ingress, temporary-file, and
   proxy-log verification.

Until those items are complete, OralSight is a working local research
application and codebase, but not a publicly deployed, clinically validated, or
submission-frozen release.
