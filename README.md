# OralSight

OralSight is a real iOS and Android mouth-observation app with an intentionally
non-diagnostic safety boundary.

The normal user flow accepts a camera image or a photo selected from the device,
removes metadata, checks image quality, asks the user to confirm privacy and the
selected mouth region, encrypts accepted data locally, calls a stateless analysis
service, saves the signed response, and makes the observation available in history
and a local PDF report.

The installed app contains no sample mouth image or local fixture fallback. It
does not substitute made-up results when analysis fails. A disabled-by-default
backend fixture remains only for isolated service and contract testing.

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

## What is intentionally unavailable

The anatomy-validation head is enabled only for region matching. Its
patient-disjoint test reached macro F1 `0.9842`, with no region recall below
`0.9302`.

The segmentation head is enabled only for non-diagnostic candidate outlining.
Its exact frozen test reached Dice `0.7192` and boundary F1 `0.6256`, passing
the required aggregate gates. Positive-image scores were lower, so its
limitations remain visible and an empty mask is never treated as reassurance.

Disease-category research failed (`macro F1 0.3596`, calibration error
`0.0827`, inadequate held-out patients, and no signed clinical review).
Appearance classification and lesion re-identification lack the required labels
or longitudinal pairs. Those three heads remain disabled for real users.

The service has a hash-verified release-manifest and model-runtime boundary. A future
model is allowed to run only when its exact artifact, preprocessing contract,
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
- `packages/contracts`: canonical TypeScript schemas and cross-field safety rules
- `services/inference`: stateless FastAPI, OpenCV, signing, and model-release service
- `ml`: patient-disjoint manifest, training, evaluation, calibration, and release-gate
  tooling
- `assets/mouth`: versioned oral observation map metadata
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
py -3.12 -m uv run --frozen --all-packages pytest services/inference/tests ml/tests

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

The checked-in `preview` and `production` EAS profiles already contain the
deployed API URL and public response-verification key. The matching private key
exists only in the Vercel secret store. Never commit populated secret files.

## Deployment

The native app is distributed as an Android or iOS build, not as a Vercel website.
The OpenCV inference API can run either from the hardened container configuration
or from the repository's Vercel Services entry point. The production service is
live at `https://oralsight-inference.vercel.app/api`; health is available at
`https://oralsight-inference.vercel.app/api/healthz`.

Vercel is only the API host. It does not replace the installed mobile app, model
artifacts, release manifest, signing secrets, or Apple/Google distribution.
The supplied configuration uses the inference service's own Python workspace and
the mobile/API pipeline caps each image at 1.75 MB so two-image comparisons fit
under Vercel's request-body limit. The deployed service passed all four-route,
live-model, no-store, and detached-signature verification on July 28, 2026.

See [mobile build and deployment](docs/MOBILE_BUILD_AND_DEPLOY.md) and the inference
service [deployment notes](services/inference/README.md).

## Safety boundary

- Review priority remains disabled unless a versioned clinician-approved rule file
  is installed.
- Learned outputs remain disabled unless their locked evaluation and review gates
  pass.
- A failed live request never receives a fixture result.
- All measurements are image-normalized and approximate, never millimeters.
- Passing software tests does not establish clinical accuracy, regulatory status,
  effectiveness, or HIPAA compliance.
