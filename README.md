# OralSight

OralSight is an iOS and Android app for taking consistent mouth photos and
tracking visible changes. It is not a diagnostic tool.

The normal user flow accepts a camera image or a photo selected from the device,
removes metadata, checks image quality, asks the user to confirm privacy and the
selected mouth region, encrypts accepted data locally, calls a stateless analysis
service, saves the signed response, and makes the observation available in history
and a local PDF report.

The installed app contains no sample mouth images and does not replace a failed
analysis with a made-up result. A disabled backend fixture exists only for
service and contract tests.

> **This result is not a diagnosis.** OralSight does not prove cancer,
> harmlessness, or the absence of disease.

## What works now

- Consent and symptom intake for every new scan
- The fixed eight-region mouth capture workflow
- Camera and saved-photo input, review, retake, and manual region/privacy
  confirmation
- IMU stability guidance when the device supports it
- Local focus, exposure, glare, obstruction, size, and aspect-ratio checks
- Server-side image decoding, metadata stripping, face detection, and quality checks
- A released eight-region anatomy model that rejects mismatched mouth regions
- A released segmentation model that outlines one possible visible candidate
  region and derives approximate area, shape, color, and texture descriptors
- Encrypted local image, metadata, analysis, and PDF storage
- Offline, timeout, malformed-response, unavailable-analysis, retry, and retake states
- Signed API-response verification for non-loopback deployments
- Saved-session resume, result reopening, deletion, and encryption-key rotation
- An accessible oral observation map with all eight named regions
- A two-step longitudinal flow: gated re-identification suggestion, mandatory
  user review, then confidence-gated ORB/RANSAC comparison
- A local clinician-discussion PDF after all eight regions have accepted captures

An image can count toward scan coverage after quality acceptance, explicit user
confirmation, and a matching anatomy result. Candidate outlining runs only when
both the quality and anatomy checks pass. An empty mask means only that the model
did not mark a candidate; it does not prove that the image is normal or harmless.
The app never invents a mask, disease class, or diagnosis.

## What is not available yet

The anatomy-validation head is enabled only for region matching. Its
patient-disjoint test reached macro F1 `0.9842`, with no region recall below
`0.9302`.

The segmentation head is enabled only for non-diagnostic candidate outlining.
Its exact frozen test reached Dice `0.7192` and boundary F1 `0.6256`, passing
the required aggregate gates. Positive-image scores were lower, so its
limitations remain visible and an empty mask is never treated as reassurance.

The released weight uses the Autooral training split under its authors'
academic-research and non-commercial terms. A clean-license SMART-OM-only
replacement was trained and evaluated once on a fresh patient holdout, but it
reached Dice `0.6809` and boundary F1 `0.5616`, below the fixed `0.70`/`0.60`
gate. It was rejected and is not bundled. The current weight is therefore for
the documented academic competition/research build unless broader written
permission is obtained.

Disease-category research failed (`macro F1 0.3596`, calibration error
`0.0827`, inadequate held-out patients, and no signed clinical review).
Appearance classification and lesion re-identification lack the required labels
or longitudinal pairs. Those three heads remain disabled for real users.

The service checks a hash-verified release manifest before loading a model. A
future model can run only when its exact artifact, preprocessing contract,
metrics, review evidence, and release state validate. Missing or invalid evidence
causes an abstention.

NeuroSight and Parkinson-related assessment are not implemented. The app contains
only a clearly labeled static roadmap entry for that deferred work.

See [implementation status](docs/IMPLEMENTATION_STATUS.md) for the exact remaining
external evidence and physical-device tests. The completed local checks are in
[final verification](docs/FINAL_VERIFICATION.md), and the original-plan audit is
in [requirement audit](docs/REQUIREMENT_AUDIT.md).

## Repository

- `apps/mobile`: Expo and React Native application
- `apps/web`: public, patient, clinician, and administrator Next.js product
- `packages/contracts`: canonical TypeScript schemas and cross-field safety rules
- `services/inference`: stateless FastAPI, OpenCV, signing, and model-release service
- `services/platform-api`: accounts, sync, storage, sharing, review, jobs,
  analytics, and deletion APIs
- `services/worker`: durable PDF, MP4, GLB, export, and retention worker
- `ml`: patient-disjoint manifest, training, evaluation, calibration, and release-gate
  tooling
- `assets/mouth`: versioned oral observation map metadata
- `deploy`: production Compose, environment contract, and operator runbook
- `docs`: architecture, safety, privacy, release, licensing, and build instructions

No restricted medical image, patient dataset, database, secret, or generated build
belongs in Git. The shipped anatomy and segmentation ONNX files are hash-pinned and
listed in the asset inventory. The repository's CC0 test fixture is not imported by
or compiled into the mobile app.

## Install and verify

Requirements:

- Node.js 22 to 24
- Corepack and pnpm 11.9.0
- Python 3.12 or 3.13
- `uv`
- Android Studio or Xcode for native builds

From the repository root:

```powershell
# Run this once after extracting the ZIP if the folder is not already a Git repository.
git init

corepack enable
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck

py -3.12 -m pip install --upgrade uv
py -3.12 -m uv sync --frozen --all-packages --extra dev
py -3.12 -m uv run --frozen --all-packages pytest `
  services/inference/tests services/platform-api/tests services/worker/tests ml/tests

python .github/scripts/audit_repository.py
```

To create a clean source archive after verification:

```powershell
.\scripts\package-source.ps1 -OutputPath ..\OralSight-source.zip
```

The packager uses Git's non-ignored source-file list, so it omits local
dependencies, exports, caches, secrets, medical data, databases, and model
training artifacts. It includes the three audited, hash-pinned ONNX files used
for face-presence privacy checks, anatomy matching, and candidate-mask inference.

## Run locally

Start the stateless service:

```powershell
$env:ORALSIGHT_DEPLOYMENT_MODE = "development"
$env:ORALSIGHT_REQUIRE_RESPONSE_SIGNING = "false"
$env:ORALSIGHT_ENABLE_DEMO_FIXTURES = "false"
$env:ORALSIGHT_RELEASE_MANIFEST_PATH = (
  Resolve-Path "services/inference/release/release-manifest.json"
).Path
py -3.12 -m uv run --frozen --package oralsight-inference `
  uvicorn oralsight_api.main:app --reload --port 8000 --no-access-log --no-server-header
```

In another terminal, create or run an Expo development build:

```powershell
$env:EXPO_PUBLIC_INFERENCE_URL = "http://127.0.0.1:8000"
pnpm dev:mobile
```

This app requires a development build; Expo Go is not enough for SQLCipher and the
other native modules. On Android hardware, `adb reverse tcp:8000 tcp:8000` lets the
phone use the loopback URL. A physical iPhone needs an HTTPS service endpoint.

Every non-loopback mobile build requires:

- an HTTPS inference URL;
- an Ed25519 private key stored only on the service;
- the matching raw public key pinned with
  `EXPO_PUBLIC_RESPONSE_SIGNING_PUBLIC_KEY_B64`; and
- production ingress rate, connection, and timeout limits.

The checked-in EAS profiles contain public inference configuration. A complete
account/cloud build also needs the platform, OIDC, web, and share-viewer values
documented in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). Private signing keys
belong only in the deployment secret store. Never commit populated secret files.

## Deployment

The native app is distributed as an Android or iOS build, not as a Vercel website.
Vercel can host the Next.js web product and the stateless OpenCV inference API.
The account API and continuous worker are stateful container services and are not
replaced by Vercel. An older inference-only source release is live at
`https://oralsight-inference.vercel.app/api`; it is not proof that the current web,
platform, worker, or full source tree is deployed.

The supplied Vercel configuration keeps the web and inference build surfaces
separate. The mobile/API pipeline caps each image at 1.75 MB so two-image
comparisons fit within the documented request-body limit. The older inference
service passed its four-route, live-model, no-store, and detached-signature checks
on July 28, 2026, but it remains rollback evidence rather than the current release.

See the complete [deployment handoff](docs/DEPLOYMENT.md),
[mobile build instructions](docs/MOBILE_BUILD_AND_DEPLOY.md), and inference
service [deployment notes](services/inference/README.md).

Optional accounts, cloud sync, clinician review, QR sharing, server-rendered reports,
encrypted exports, and durable jobs run through the separate platform and worker
services. `compose.yaml` is the local stack. The hardened production surface and its
external PostgreSQL, TLS Redis, private S3, OIDC, backup, restore, and retention
requirements are documented in
[`deploy/production/RUNBOOK.md`](deploy/production/RUNBOOK.md).

## Safety boundary

- Review priority remains disabled unless a versioned clinician-approved rule file
  is installed.
- Learned outputs remain disabled unless their locked evaluation and review gates
  pass.
- A failed live request never receives a fixture result.
- Measurements are image-normalized unless a versioned reference-card calibration
  passes; calibrated millimeter values remain clearly labeled approximate estimates.
- Passing software tests does not establish clinical accuracy, regulatory status,
  effectiveness, or HIPAA compliance.

## Distribution boundary

No repository-wide source license has been selected by the owner. The bundled
segmentation weight is documented for academic research/non-commercial use and
is not cleared here for unrestricted public or commercial redistribution. A
private competition repository and local source ZIP can be used within that
scope. Before a public GitHub release, choose the source license and obtain
written model permission or replace the weight with a properly licensed model
that passes a new untouched release test.
