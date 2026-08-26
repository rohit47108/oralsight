# OralSight requirement audit

Audit date: 2026-08-13

This audit compares the current repository with:

1. the original **OralSight: Complete Product and Engineering Blueprint**;
2. the later **OralSight 2026 Competition Build Plan**; and
3. the later request to expand OralSight into an optional account/cloud product
   with multi-angle capture, calibration, generated artifacts, sharing, and a
   clinician portal.

The later fixed safety and data contracts still control conflicting details:

- the product uses the canonical eight regions, not the original ten-region
  example;
- results remain non-diagnostic and cannot claim cancer, harmlessness, clinical
  accuracy, HIPAA compliance, or unsupported physical precision;
- learned outputs remain hidden when their evidence gates fail;
- every proposed lesion match still requires a separate user decision; and

> **This result is not a diagnosis.** This is a software audit, not clinical or
> regulatory evidence.

## Verdict meanings

- **Implemented locally**: the source path exists and has direct local test,
  build, runtime, or artifact evidence.
- **Implemented; external setup**: the source path exists, but real use needs
  identity, hosting, storage, a domain, a clinician, or physical hardware.
- **Implemented; release gate closed**: the safe workflow exists, but a learned
  or numeric output remains suppressed because its required evidence is absent.
- **Partial**: a useful version exists, but an explicit part of the blueprint is
  absent.
- **Missing**: no real implementation or release evidence exists.

## Original 50-feature audit

|   # | Blueprint feature                                         | Current evidence                                                                                                                                                                                                                                    | Verdict                                                                                                                                                                               |
| --: | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|   1 | Intelligent onboarding, adaptive intake, symptom body map | Mobile onboarding captures the requested context, reveals dependent questions, records head/neck symptom locations, and feeds only gated rules/reminders                                                                                            | **Implemented locally**; clinician urgency rule remains closed                                                                                                                        |
|   2 | Anatomical 3D mouth navigator                             | Eight named meshes plus support anatomy, rotate, zoom, select, transparency, hide teeth, pins, and accessible region list                                                                                                                           | **Implemented locally** under the fixed eight-region contract                                                                                                                         |
|   3 | Exploded anatomical mode                                  | Map separates the observation regions and support structures with accessible controls                                                                                                                                                               | **Implemented locally**                                                                                                                                                               |
|   4 | Scan-path animation                                       | Guided region sequence, animated replay, phone-position/tongue/helper cues, and reduced-motion handling                                                                                                                                             | **Implemented locally**; uses a compact path cue rather than a detailed phone avatar                                                                                                  |
|   5 | Scan-completeness map                                     | 8/8 accepted/pending state appears in the map, native list, scan screen, and report                                                                                                                                                                 | **Implemented locally**                                                                                                                                                               |
|   6 | Lesion pins                                               | Explicitly confirmed pins store region, mesh, UV, version, dates, captures, status, symptoms, and measurement provenance                                                                                                                            | **Implemented locally**                                                                                                                                                               |
|   7 | 3D lesion/status heatmap                                  | Scan coverage, unavailable/quality state, changed observations, and confirmed pins have distinct text/shape/color states                                                                                                                            | **Implemented locally**; it is not a risk heatmap                                                                                                                                     |
|   8 | Personalized mouth model                                  | Worker creates a GLB from three or more hash-verified views, colors the standard region meshes from those images, and embeds confirmed pins                                                                                                         | **Partial; external setup**: it is an image-colored generic observation surface, not reconstructed patient anatomy                                                                    |
|   9 | Guided camera                                             | Live stability and framing overlay plus immediate focus/exposure/glare/obstruction/size/privacy/anatomy acceptance                                                                                                                                  | **Implemented locally** under the later capture contract                                                                                                                              |
|  10 | Stability ring and automatic capture                      | IMU-driven ring, automatic capture option, sensor fallback, and explicit manual capture                                                                                                                                                             | **Partial**: the ring represents device stability only; focus, lighting, and centering are checked after capture                                                                      |
|  11 | AR anatomical overlay                                     | Region-specific SVG/tissue target overlay on the live camera, with mirror support                                                                                                                                                                   | **Implemented locally**; it is a 2D guide rather than environment-tracked AR                                                                                                          |
|  12 | Ghost-image follow-up                                     | A prior encrypted capture is temporarily decrypted into a low-opacity camera guide and cleaned on exit                                                                                                                                              | **Implemented locally**                                                                                                                                                               |
|  13 | Multi-angle capture                                       | Straight/left/right capture sets plus a guided six-second sweep whose instructed temporal angle segments yield retained still frames                                                                                                                | **Implemented locally**; the sweep does not measure camera pose or lesion visibility, and cloud persistence needs the platform                                                        |
|  14 | Calibration reference                                     | Exact A4/Letter 20 mm ArUco card, QR payload, four neutral patches, same-plane confirmation, marker-plane geometry, nullable physical estimates, and fail-closed neutral-patch normalization for mean redness/brightness only                       | **Implemented locally; external evidence**: marker sizing and color correction are independent, and print/device repeatability remains unvalidated                                    |
|  15 | Caregiver-assisted mode                                   | Intake selects self/assisted use and capture guidance assigns patient/helper positioning responsibilities                                                                                                                                           | **Implemented locally**                                                                                                                                                               |
|  16 | Mirror mode                                               | User-controlled mirrored anatomical capture guide                                                                                                                                                                                                   | **Implemented locally**                                                                                                                                                               |
|  17 | Video-to-best-frame capture                               | Each instructed temporal angle segment is sampled, privacy/quality checked, reduced to its best accepted frame, and the raw sweep is deleted                                                                                                        | **Implemented locally**; selection uses timing plus image quality, not measured pose or candidate visibility                                                                          |
|  18 | Privacy preprocessing                                     | Metadata removal, randomized IDs, face checks, mouth-only confirmation, encrypted storage, bounded transport, and safe filenames                                                                                                                    | **Implemented locally**                                                                                                                                                               |
|  19 | Image-quality model/check                                 | Deterministic local/server checks cover blur, exposure, glare, obstruction, resolution, aspect ratio, face presence, and target mismatch                                                                                                            | **Partial**: there is no trained quality model or true camera-distance measurement; physical-device error-rate validation remains external                                            |
|  20 | Anatomical-region classification                          | Released hash-pinned eight-class anatomy ONNX with mismatch rejection and abstention                                                                                                                                                                | **Implemented locally**                                                                                                                                                               |
|  21 | Oral-cavity tissue segmentation                           | A separate model-head contract, runtime adapter, mask intersection, limitations, and fail-closed gate are implemented                                                                                                                               | **Implemented; release gate closed** because no licensed tissue-mask dataset and held-out boundary evidence are available                                                             |
|  22 | Lesion/candidate detection                                | Candidate bounding box is derived from the released candidate mask and may be absent                                                                                                                                                                | **Implemented locally** without a redundant second detector                                                                                                                           |
|  23 | Lesion/candidate segmentation                             | Released mask plus normalized area, perimeter, width/height, shape, border, color, and texture descriptors                                                                                                                                          | **Implemented locally**                                                                                                                                                               |
|  24 | Visual-pattern classification                             | Contracts, UI, model-card gate, abstention, and seven-class taxonomy exist; no real class is shown                                                                                                                                                  | **Implemented; release gate closed** because the required labels and held-out support do not exist                                                                                    |
|  25 | Uncertainty system                                        | Six honest factors cover quality, visibility, alignment, symptom completeness, dataset similarity, and model agreement, each with a value or unavailable reason                                                                                     | **Implemented locally**; learned similarity/agreement values remain unavailable until their heads pass release gates                                                                  |
|  26 | Out-of-distribution detection                             | Separate supported/unsupported model-head contract, runtime adapter, score, threshold, abstention, model card, and tests                                                                                                                            | **Implemented; release gate closed** because no licensed supported-versus-unsupported evaluation set is available                                                                     |
|  27 | Ensemble analysis                                         | Independent secondary-segmentation adapter, numeric agreement, disagreement suppression, and combined explanation are implemented                                                                                                                   | **Implemented; release gate closed** because no independently trained secondary artifact and locked agreement evidence are available                                                  |
|  28 | Explainable AI                                            | Mask overlay, descriptors, symptom/duration factors, structured explanation text, confidence/limitations, provenance, and no invented findings                                                                                                      | **Implemented locally**                                                                                                                                                               |
|  29 | Lesion re-identification                                  | Proposal/decision contracts, region/feature evidence, cloud persistence, and mandatory confirmation exist                                                                                                                                           | **Implemented; release gate closed** for the learned automatic head; the user-confirmed path works                                                                                    |
|  30 | Image registration                                        | ORB features, RANSAC homography, inlier ratio, normalized reprojection error, suppression reasons, and a bounded client-safe display transform                                                                                                      | **Implemented locally**; a display alignment is not quantitative comparability                                                                                                        |
|  31 | Change measurements                                       | Gated deltas cover normalized area, width, height, perimeter, border irregularity, redness, brightness, texture, ulceration-like contrast, symptoms, days, and confidence                                                                           | **Implemented; release gate closed**: the current release has no approved repeated-capture evidence demonstrating at most 10% area error, so all quantitative change stays suppressed |
|  32 | Time-lapse morph                                          | Motion-controlled replay crossfades the two captures and masks; when a gated alignment and both polygons exist, their outlines interpolate                                                                                                          | **Implemented locally** as a visual aid; it is not a physical measurement                                                                                                             |
|  33 | Before-and-after slider                                   | A true clipped reveal divider supports drag, tap, keyboard/screen-reader adjustment, untouched originals, masks, and an optional registered display                                                                                                 | **Implemented locally**                                                                                                                                                               |
|  34 | Trajectory graph                                          | Accessible visual-change chart for approximate area, symptoms, quality, confidence, and comparison status                                                                                                                                           | **Implemented locally**                                                                                                                                                               |
|  35 | Same-angle replay                                         | Ghost guide plus persisted tilt, rotation, lighting, and calibrated image-scale similarity, with unavailable reasons when evidence is absent                                                                                                        | **Implemented locally**; scale is a framing-distance proxy and is never represented as tissue identity                                                                                |
|  36 | Stability detection                                       | The implemented policy can classify stable, increased, decreased, color/texture change, shape change, or insufficient data with non-color cues                                                                                                      | **Implemented; release gate closed** for quantitative classifications in the current release; it reports insufficient comparable data                                                 |
|  37 | Smart reminder engine                                     | User-controlled local reminders adapt to quality, duration, and follow-up state; severe neutral seek-care copy does not depend on a model                                                                                                           | **Implemented locally**; clinician-derived urgency remains disabled without an approved rule file                                                                                     |
|  38 | Oral Health Digital Twin                                  | Map/timeline combines coverage, pins, dates, symptoms, comparisons, and review state; cloud GLB adds projected capture colors                                                                                                                       | **Implemented** as an oral observation map/surface, not a digital twin or patient-specific anatomy                                                                                    |
|  39 | Lesion identity card                                      | Result/timeline/report surfaces show location, date/persistence, descriptors, symptoms, quality, confidence, status, and gated change                                                                                                               | **Implemented locally**; no unsupported appearance/urgency is inserted                                                                                                                |
|  40 | Interactive explanation tree                              | Expandable steps connect verified image evidence, symptoms, duration, comparison, release gates, and limitations                                                                                                                                    | **Implemented locally**                                                                                                                                                               |
|  41 | Confidence constellation                                  | Accessible six-factor view shows quality, visibility, agreement, alignment, symptom completeness, and dataset similarity with explicit unavailable reasons                                                                                          | **Implemented locally** without collapsing uncertainty into one unexplained percentage                                                                                                |
|  42 | Clinician-ready report                                    | Local and cloud PDF paths contain real images/overlays, map, intake, timeline, comparisons, consent, model versions, uncertainty, and per-page disclaimer                                                                                           | **Implemented locally**; cloud rendering needs deployment                                                                                                                             |
|  43 | Expiring QR-share mode                                    | Selective share, fragment secret, browser QR, exchange cookie, expiry, revocation, report access, and access history                                                                                                                                | **Implemented; external setup**: needs live OIDC, platform, database, Redis, private storage, and web domain                                                                          |
|  44 | Appointment-preparation assistant                         | Fixed, non-prescriptive professional-discussion questions are included in app/report outputs                                                                                                                                                        | **Implemented locally**                                                                                                                                                               |
|  45 | Clinician annotation mode                                 | Reachable invitation-gated application, two-step clinician activation, verified queue, dates, protected images/reports, polygon editor, location correction, eight annotation kinds, insufficiency state, comparison, status, and follow-up message | **Implemented; external setup** for real OIDC, clinician verification, storage, and deployment                                                                                        |
|  46 | Scan summary video                                        | Worker renders a captioned H.264 MP4 that rotates the generic map to the selected region, then shows images, masks, confirmed progression, and allowed guidance                                                                                     | **Implemented; external setup** for private storage, report prerequisite, worker, and deployed playback                                                                               |
|  47 | Interactive oral anatomy atlas                            | Eight tappable region lessons with names, capture instructions, variations, and neutral professional-review education                                                                                                                               | **Implemented locally**                                                                                                                                                               |
|  48 | Normal-variation gallery                                  | Clearly separated educational variation cards with explicit non-reassurance language                                                                                                                                                                | **Implemented locally**; uses original non-patient educational artwork/text rather than a diagnostic look-up gallery                                                                  |
|  49 | Scan simulator                                            | Nine interactive, practice-only scenarios cover low/high light, too near/far framing, glare, blur, obstruction, incomplete coverage, and ready framing                                                                                              | **Implemented locally** with distinct visual states and no patient result                                                                                                             |
|  50 | Knowledge challenges                                      | Short adult-toned questions explain quality, persistence, AI limits, comparison, and sharing                                                                                                                                                        | **Implemented locally**                                                                                                                                                               |

## Non-numbered blueprint requirements

| Area                       | Current evidence                                                                                                                                                                                                                     | Verdict                                                                                                                                                |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Accessibility              | VoiceOver/TalkBack semantics, native map alternative, large text, high contrast, non-color status, haptics, spoken instructions, reduced motion/transparency, and motion-speed preference                                            | **Implemented locally**; physical VoiceOver/TalkBack and device-matrix checks remain external                                                          |
| Data strategy              | No restricted medical images in Git; source/license/checksum inventory; patient-disjoint manifests; DVC templates; model/data version hashes                                                                                         | **Implemented locally**; new licensed datasets are external                                                                                            |
| Training/evaluation        | Reproducible anatomy/segmentation training/evaluation, calibration, gates, model cards, failed disease evaluation, and fail-closed release manifest                                                                                  | **Implemented locally**; absent evidence cannot be manufactured                                                                                        |
| Mobile architecture        | Expo/React Native development build, Expo Router, Zustand, camera/sensors/Skia/Reanimated/Three, SQLCipher, SecureStore, encrypted files, local PDF                                                                                  | **Implemented locally**                                                                                                                                |
| Inference architecture     | Four-route stateless FastAPI service, PyTorch/ONNX/OpenCV boundary, no accounts/jobs, no-store, no body logging, cleanup in `finally`, response signing                                                                              | **Implemented locally**; only an older inference-only release is currently live                                                                        |
| Full-product platform      | OIDC accounts, PostgreSQL, S3, Redis outbox/stream, worker, analytics consent, retained jobs, sync, durably sealed admin bootstrap/recovery, reachable clinician application and two-step activation, reports, exports, and deletion | **Implemented; external setup**                                                                                                                        |
| Security/privacy           | EXIF removal, local encryption, private storage controls, mobile and worker Ed25519 response verification, HMAC worker calls, safe logging, deletion, retention, backup/restore contract                                             | **Implemented locally**; actual host/backup/ingress verification remains external                                                                      |
| Competition/source handoff | CI definitions, disclosures, model/license documents, demo script, release roadmap, source packager                                                                                                                                  | **Implemented in source**; the handoff ZIP is created and verified after source freeze; hosted CI, owner review, and submission assets remain external |

## Additional full-product features beyond the numbered blueprint

The later expansion also added:

- OIDC/PKCE patient accounts and optional local-first cloud consent;
- encrypted sync, recovery code, background retry, resumable assets, and
  tombstones;
- durable job/cancel/retry/dead-letter/retention infrastructure;
- private cloud reports and generated-artifact viewers;
- X25519 recipient-encrypted portable export;
- administrator clinician verification and privacy-thresholded opt-in analytics;
- a public clinician-application entry gated by the exact `clinician_pending`
  token role, plus separate post-approval `clinician` activation;
- durably sealed offline first-administrator bootstrap, a trusted-operator
  additional-admin command using an active admin reference, and a separate
  sealed zero-admin recovery command, with no public role-promotion endpoint;
- exact configured OIDC role-claim validation and a bounded maximum age for
  privileged token roles;
- explicit share/access audit history; and
- production container hardening, migrations, readiness, backup, restore,
  retention, and no-resurrection deletion rules.

These are implemented software paths, not evidence that the required external
services are already running.

## Unresolved release boundaries

One explicit capture limitation is that the preview stability ring uses the
phone's motion sensors because Expo Camera does not expose live focus, luminance,
or anatomy frames to JavaScript. Focus, exposure, glare, obstruction, size,
privacy, and anatomy are checked immediately after capture before an image is
accepted. Replacing that boundary would require a custom native frame processor
and a new physical-device validation cycle; the fixed competition contract
explicitly calls for IMU preview guidance plus post-capture checks.

The personalized visualization is also deliberately bounded: it colors generic
named-region geometry from accepted captures and adds confirmed pins. It does
not reconstruct the user's anatomical geometry, depth, or tissue surface.

Several learned paths are present but correctly unavailable because the
repository does not contain the required licensed data and evaluation evidence:
learned quality, appearance, oral-tissue, OOD, secondary segmentation,
disease-category research, and automatic re-identification. The current release
also has no hash-bound, reviewer-approved repeat-capture study at no more than
10% area error, so it may render a gated alignment but cannot report normalized
or calibrated longitudinal change. The clinician-approved urgency rule is also
absent. These are evidence gates, not permission to insert placeholder results.

The current segmentation head passed the competition engineering gate, but it used
Autooral training data under academic-research/non-commercial terms. A SMART-OM-only
CC BY 4.0 replacement was trained and evaluated once on a new patient holdout that
excluded every earlier holdout patient. It scored Dice `0.6809` and boundary F1
`0.5616`, below the fixed `0.70`/`0.60` gate, and was rejected. The current weight
therefore stays in the private academic-competition deployment bundle. Public source
distribution excludes it; a future commercial model still needs broader rights or a
new untouched-test pass.

The following implemented features also need outside proof before they can be
called production-complete:

- image-colored generic GLB generation, calibration, QR sharing, clinician access, cloud
  reports/video/export, analytics, and cloud deletion in one deployed stack;
- the deployed sealed first-admin, normal additional-admin, zero-admin recovery,
  `/professional-apply`, credential review, signed-role activation, and
  provider-role removal paths with real OIDC accounts;
- the required two-iPhone/two-Android scan and accessibility matrix;
- printed-card sizing/color-descriptor and repeated-capture measurement validation;
- a clinician-approved urgency-rule file, if urgency is to be enabled;
- hosted GitHub CI, container/Vercel builds, app signing, store artifacts, and
  domain deployment;
- deployed retention and backup settings that match the web privacy notice's published
  35-day maximum backup window;
- deployment verification that the private Autooral-derived segmentation bundle
  remains inaccessible from public source and public downloads; and
- final wording, demo-case, and competition review.

## Overall verdict

OralSight is not a fixture-driven photo demo: the core capture, live analysis,
local records, optional account/cloud, clinician, artifact, sharing, and deletion
paths are implemented. It is also not accurate to call every blueprint item
complete. Personalized geometry remains a generic image-colored surface;
quantitative longitudinal change and several learned heads are release-gated;
preview quality has the documented device boundary; and deployment, device,
clinical-review, and comparison-repeatability evidence remains
outside the repository. The current source is an academic competition/research
build, not a fully deployed, physically or clinically validated, commercially
licensed medical product.
