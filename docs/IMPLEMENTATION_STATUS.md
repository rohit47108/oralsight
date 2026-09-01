# Stoma3D implementation status

Last updated: 2026-08-30

> **This result is not a diagnosis.** Passing software and model engineering
> tests does not establish clinical accuracy, safety, effectiveness, regulatory
> clearance, or harmlessness.

## Plain-language result

Stoma3D is a real, local-first mouth-observation product, not a fixture-driven
photo demo. The repository contains an eight-region mobile workflow, the public
and authenticated web product, the account/cloud/clinician platform, the private
artifact worker, and the stateless image-analysis service. Normal installed-app
use never substitutes bundled results for a live capture.

The current source, mobile build, web build, and local full-stack verification
are green. The public website and production inference service are live. The
account, cloud, clinician, sharing, and worker stack has also been exercised
locally with PostgreSQL, Redis, object storage, and real queued jobs. Hosting
that full stack still needs the managed services and identity setup listed at
the end of this document.

## Implemented software paths

### Mobile

- Versioned consent, adaptive symptom intake, the fixed eight-region scan, and
  one quality-accepted capture per region.
- Standard, multi-angle, and video-sweep capture; live motion stability; saved
  photo review; post-capture focus, exposure, glare, obstruction, privacy, size,
  and anatomy checks; retake and interruption recovery. Sweep frames come from
  instructed temporal straight/left/right segments and image-quality scoring;
  the app does not claim measured camera pose or lesion visibility.
- Metadata stripping, sanitized upload, signed-response validation, SQLCipher
  metadata, encrypted files, SecureStore keys, offline retry, and delete-all
  with installation-key rotation.
- Oral observation map with eight selectable regions, confirmed pins, timeline,
  comparison states, capture replay guidance, and a reduced-motion/list fallback.
- User-confirmed re-identification proposals, registration diagnostics, a true
  clipped reveal slider, and a mask-aware timeline. A gated homography may align
  the visual display, but the current release suppresses all quantitative and
  calibrated longitudinal change until approved repeated-capture evidence shows
  no more than 10% area error.
- Optional calibration metadata reaches both direct and cloud-worker analysis.
  When all marker, pose, proximity, same-plane, patch-visibility, uniformity, and
  bounded-fit checks pass, the four neutral patches normalize only approximate
  mean redness and brightness. The stored image and every other analysis input
  and output remain unchanged; failure keeps the original descriptors and states
  the reason.
- Expandable explanation tree, six honest confidence factors with unavailable
  reasons, local PDF, reminders, learning atlas, accessibility settings, and
  normal-variation education. The practice simulator has nine distinct
  low/high-light, distance, glare, blur, obstruction, coverage, and ready states;
  it never produces a patient result.
- Optional OIDC account, explicit cloud consent, encrypted sync, resumable
  assets, reports, artifacts, shares, access history, jobs, recovery, and cloud
  deletion. Once deletion starts, normal cloud work and existing sharing stop;
  a minimal protected receipt survives app restarts only to poll deletion status,
  then credentials and remaining cloud keys are cleared. Local-only use remains
  available.

### Web, platform, and worker

- Responsive public site plus authenticated patient, clinician, and administrator
  workspaces. No fake patient records are inserted when an account has no data.
- Reachable `/professional-apply` entry, invitation-gated `clinician_pending`
  application, administrator credential review, and separate signed-token
  activation before clinician access opens.
- Durably sealed offline first-administrator bootstrap, trusted-operator
  additional-admin setup using an active administrator reference, and a separate
  sealed zero-admin recovery command. None is exposed as a public HTTP route, and
  the reference does not represent personal approval.
- Patient scan/report/artifact history, QR sharing, fragment-secret exchange,
  expiry, revocation, access history, clinician grants, eight annotation kinds,
  review status, verification, and privacy-thresholded opt-in analytics.
- PostgreSQL data model and migrations, OIDC/JWKS verification, database plus IdP
  role checks, encrypted sync, private S3/local storage, Redis Streams, a database
  outbox, retries, cancellation, dead letters, retention, deletion receipts, and
  no-resurrection cleanup.
- Server-rendered clinician PDF, captioned H.264 summary video with a rotating
  generic observation map, image-colored/pinned private GLB built on standard
  geometry, and recipient-encrypted portable export. The GLB is not reconstructed
  patient anatomy.
- Strict CSP nonces, no-index/no-store private surfaces, stable form idempotency
  keys, bounded request bodies, checksums, rate limits, safe logging, exact OIDC
  role-claim validation, bounded privileged-token age, Ed25519 verification of
  worker inference responses before JSON parsing, and hardened production
  configuration.

### Inference and model controls

- Stateless FastAPI/OpenCV/PyTorch service with only analyze, compare, model-card,
  and health routes.
- Real anatomy validation, candidate segmentation, descriptors, uncertainty,
  abstention, registration, comparison suppression, paired ArUco sizing, and
  independently gated four-patch color-descriptor normalization. The
  registration transform is available for an honest aligned display, but the
  quantitative comparison release gate is currently closed.
- Implemented fail-closed adapters and model-card contracts for appearance,
  disease research, learned quality, oral-tissue masks, OOD, secondary-model
  agreement, and automated re-identification. Those heads stay disabled without
  the required licensed artifacts and untouched release evidence.
- No request-body or exception-detail logging, no retained inference jobs, and
  exact hash-bound fixtures only in isolated tests.

## Released learned outputs

| Output                                                   | Runtime state                                       | Evidence and limit                                                                                                                                               |
| -------------------------------------------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Eight-region anatomy match                               | Enabled                                             | Macro F1 `0.9842`, minimum region recall `0.9302`, calibration error `0.0123`; 376 images from 47 held-out patients; SMART-OM CC BY 4.0                          |
| Candidate segmentation                                   | Enabled for the academic competition/research build | Dice `0.7192`, boundary F1 `0.6256`; 106 images from 39 held-out patients; the artifact used Autooral training data under academic-research/non-commercial terms |
| Appearance                                               | Disabled                                            | Required seven-class labels and held-out support are unavailable                                                                                                 |
| Disease-category research                                | Disabled                                            | Macro F1 `0.3596`, calibration error `0.0827`, inadequate per-class support, and no signed clinical review                                                       |
| Learned re-identification                                | Disabled                                            | Required longitudinal matched and hard-negative evidence is unavailable                                                                                          |
| Learned quality, tissue, OOD, and secondary segmentation | Disabled                                            | Runtime paths exist, but licensed artifacts and release evidence do not                                                                                          |
| Quantitative longitudinal change                         | Disabled                                            | No hash-bound, reviewer-approved repeated-capture evaluation has demonstrated area error at most 10%; visual registration does not satisfy this gate             |

The attempt to remove the segmentation licensing constraint was completed
honestly. A SMART-OM-only CC BY 4.0 replacement was selected on a fresh validation
split and evaluated once on a fresh patient holdout that excluded every earlier
holdout patient. It reached Dice `0.6809` and boundary F1 `0.5616`, below the fixed
`0.70`/`0.60` gates. It was rejected and is not bundled. See
[`SEGMENTATION_SMART_OM_ONLY_ATTEMPT.json`](licenses-model-cards/SEGMENTATION_SMART_OM_ONLY_ATTEMPT.json).

The private segmentation weight is therefore used only for the documented
academic competition scope. It is hash-verified at deployment and is not included
in the public repository.

## Current verification

| Check                                      | Current result                                                                                                          |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| TypeScript tests                           | `pnpm test` passed: repository 22, contracts 33, mobile 158, web 66                                                     |
| Type checking and web lint                 | TypeScript checks and the full web ESLint run passed                                                                    |
| Python tests                               | 339 passed, 1 intentionally skipped PostgreSQL-only bootstrap test                                                      |
| Ruff and Prettier                          | Ruff and Prettier checks passed                                                                                         |
| Web production build                       | Next 16 Turbopack production build passed from the short linked dependency store                                        |
| Mobile builds                              | Android and iOS bundle exports passed; the Android release APK build passed                                             |
| Contract/OpenAPI generation                | Checked schemas and OpenAPI regenerated; snapshot passed                                                                |
| Repository safety audit                    | Forbidden files, fixtures, hashes, provenance, inventory, and taxonomy checks passed; notices and SBOM are current      |
| JavaScript and Python dependency audits    | JavaScript high-severity audit passed; all three Python production locks reported no known vulnerabilities              |
| Standalone inference/platform/worker locks | Frozen lock checks passed                                                                                               |
| Vercel and Compose configuration           | Official schema validation, hosted web/inference builds, public proxy checks, and Compose parsing passed                |
| GitHub workflow hardening                  | Hosted TypeScript, Python, and repository-safety workflows passed on public `main`                                      |
| Local full-stack runtime                   | All six long-running services became healthy; migration and storage-init jobs exited 0; platform and worker were ready  |
| Product integration flow                   | Account, consent, scan, encrypted sync, QR share/revoke, clinician review, analytics, export job, and delete-all passed |
| Production web                             | Desktop and 390 px browser checks passed across key routes with no console warnings or horizontal overflow              |
| Production inference                       | Live health reports production-ready with signed responses and anatomy plus candidate segmentation enabled              |

The exact commands and boundaries are recorded in
[`FINAL_VERIFICATION.md`](FINAL_VERIFICATION.md).

## External release requirements

These cannot be manufactured inside the source tree:

- A broader model license or a replacement model is needed only for a future
  commercial distribution. The public source is MIT licensed and excludes the
  Autooral-assisted competition weight.
- Owner-registered iOS and Android identifiers, Expo/EAS project and signing
  accounts, Apple and Google credentials, and store records.
- Real OIDC tenant/roles, managed PostgreSQL, TLS Redis, private S3,
  secrets/KMS, a worker host, ingress limits, backups, alerts, and retention
  policies for the optional hosted account/clinician product.
- A deployed full-platform acceptance run once the managed account services
  listed above exist.
- Three complete scans on each of two physical iPhones and two physical Android
  phones, the planned false-accept/false-reject calculation, printed-card
  sizing/color-descriptor repeatability, VoiceOver/TalkBack, low-storage,
  interruption, backup/restore, sharing, and delete-all evidence.
- A hash-bound, reviewer-approved repeat-capture evaluation at no more than 10%
  area error before normalized or calibrated longitudinal change can be enabled.
- A clinician-approved guidance rule if urgency is to be enabled. Without it,
  urgency stays disabled and only neutral seek-care information is shown.

It is not part of this Stoma3D source-release verdict.
