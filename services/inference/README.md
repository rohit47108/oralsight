# OralSight inference service

This directory contains the stateless FastAPI service for OralSight. It performs
deterministic capture-quality checks, runs release-gated ONNX heads through OpenCV DNN,
and computes confidence-gated registration diagnostics. The public source includes
the hash-pinned anatomy model. The competition deployment loads candidate segmentation
from a private, hash-verified release bundle. Anatomy rejects mismatched mouth regions;
segmentation outlines one possible candidate region. Neither model diagnoses disease.
Appearance, disease-category research, and re-identification remain disabled.

> **This result is not a diagnosis.** Candidate masks and changes are approximate
> research outputs. Millimeter estimates appear only when the versioned physical
> marker and same-plane checks pass, and they remain approximate.

The competition segmentation weight used the Autooral training split under
academic-research/non-commercial terms. A SMART-OM-only CC BY 4.0 replacement
was evaluated on a fresh patient holdout and rejected because Dice `0.6809` and
boundary F1 `0.5616` missed the fixed `0.70`/`0.60` gate. The current weight is
therefore stays outside the public repository and is supplied only to the
academic competition inference deployment. See the checked release review and
[SMART-OM-only attempt evidence](../../docs/licenses-model-cards/SEGMENTATION_SMART_OM_ONLY_ATTEMPT.json).

For local candidate outlining, set `ORALSIGHT_RELEASE_MANIFEST_PATH` to the
manifest in `services/inference/private-release`. The expected bundle layout and
public-source boundary are documented in
[`docs/PUBLIC_DISTRIBUTION.md`](../../docs/PUBLIC_DISTRIBUTION.md).

For a private competition container, run
`docker build -f Dockerfile.private -t oralsight-inference:competition .` from
this directory. That build deliberately fails when the local private bundle is
absent. The regular `Dockerfile` remains safe to build from a public clone.

## Run locally

Python 3.12 or 3.13 is recommended. The root `uv.lock` is the authoritative workspace
lockfile, and `requirements.lock.txt` is its hash-pinned, inference-only container
export. The service-local `uv.lock` is the standalone deployment lock consumed by
Vercel; CI recreates its project context and rejects lock drift.
From the repository root:

```powershell
py -3.12 -m pip install --upgrade uv
py -3.12 -m uv sync --frozen --package oralsight-inference --extra dev
py -3.12 -m uv run --frozen --package oralsight-inference `
  uvicorn oralsight_api.main:app --reload --port 8000 --no-access-log
py -3.12 -m uv run --frozen --package oralsight-inference pytest services/inference/tests
py -3.12 -m uv run --frozen --package oralsight-inference `
  python services/inference/scripts/smoke_http.py
```

Equivalent `pip` commands are:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
```

Build the container with this directory as the Docker context. The command below is
loopback-only local development; it is unsigned and is not a production deployment:

```powershell
docker build -t oralsight-inference services/inference
docker run --rm -p 8000:8000 oralsight-inference
```

## Public API

Only four routes are exposed; interactive docs and the OpenAPI route are disabled in production code.

- `GET /healthz`
- `GET /v1/model-card`
- `POST /v1/analyze`
- `POST /v1/compare`

`POST /v1/analyze` is `multipart/form-data` with:

- `image`: one JPEG, PNG, or WebP image, at most 1.75 MB.
- `metadata`: a JSON string matching `AnalyzeMetadata` in `packages/contracts`.
  It may include the exact versioned calibration-card metadata. When provided,
  the service independently gates optional neutral-patch color normalization.

`POST /v1/compare` is `multipart/form-data` with:

- `baseline_image`: the earlier image, at most 1.75 MB.
- `current_image`: the newer image, at most 1.75 MB.
- `metadata`: a JSON string matching `CompareMetadata`, including required `baselineAnalysis` and `currentAnalysis` references. Each reference carries its capture ID, region, status, provenance, quality acceptance, candidate normalized area, and model versions. The service rejects references whose capture ID or region does not match the top-level comparison request.

Example:

```powershell
$metadata = '{"contractVersion":"1.1.0","captureId":"capture-1","selectedRegion":"lower_lip","inputOrigin":"live_capture","requestedHeads":["segmentation","anatomy"]}'
curl.exe -X POST http://127.0.0.1:8000/v1/analyze -F "image=@sample.png;type=image/png" -F "metadata=$metadata"
```

All JSON fields use the exact camelCase names from `packages/contracts`. Every response, including errors, includes `Cache-Control: no-store`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, and `X-Request-ID`. Only a canonical UUIDv4 caller request ID is echoed; otherwise the service generates a UUIDv4 so caller-controlled text cannot enter request-ID logs.

`GET /healthz` is both a liveness and explicit readiness report. `status: "ok"` and
`serverAlive: true` mean only that the HTTP process is running. `analysisReady` is true
only when verified segmentation and anatomy heads have operational runtime adapters.
`productionReady` additionally requires production mode, response signing, and disabled
demo fixtures. The response exposes only safe reason codes, never configured paths or
secrets.

## Analysis behavior

The upload boundary decodes the source, applies EXIF orientation, rejects decompression bombs and animation, converts to RGB, resizes the longest edge to at most 2,048 pixels, and re-encodes an EXIF-free JPEG. Analysis uses only those sanitized pixels.

Quality fields have these semantics:

- `blurScore` and `exposureScore`: pass confidence, where higher is better.
- `glareScore` and `obstructionScore`: problem severity, where lower is better.
- `faceDetected`: a conservative OpenCV frontal-face privacy check.

Quality-accepted live images run the released anatomy head first. A supported match
then runs the released segmentation model and returns
`analysisOrigin: "live_model"`. An anatomy mismatch or anatomy abstention rejects the
selected-region capture. There is no color-rule fallback. A candidate polygon, bounding
box, normalized area, and visual descriptors are produced only from the thresholded
probability map returned by the released segmentation ONNX model. An empty mask means
only that no candidate crossed the threshold. Appearance,
disease-category, and re-identification values likewise come only from their
corresponding released heads.

When the exact OralSight card is requested and detected, the service may use all
four neutral patches to normalize only the candidate's approximate mean-redness
and mean-brightness descriptors. The correction is applied to a copied pixel
array only after the marker, pose, proximity, same-plane, patch-visibility,
uniformity, range, clipping, and bounded-fit checks pass. It never changes the
stored or sanitized image, candidate mask, anatomy and quality results, texture
descriptor, classifier inputs, or guidance. A failed color-reference gate keeps
the uncorrected descriptors and reports the reason; it does not invalidate an
otherwise valid physical-size estimate.

Anatomy is run before segmentation. A calibrated anatomy abstention or a predicted region
that does not match the user-selected region prevents candidate output. Request-time
model errors expose no partial mask or class prediction. Optional appearance and disease
outputs are explicitly labeled experimental research output and never drive guidance.

`GET /v1/model-card` reports `enabledHeads: ["segmentation", "anatomy"]`. Its
`artifactHashes` contains SHA-256 digests of the exact deployed processing, model-adapter,
release-loader, and signing source bytes. Weight entries are derived from the release
loader. A head is enabled only when its declared artifact exists, matches its pinned
SHA-256, parses as ONNX, and passes a startup dummy inference with the declared
input/output names and shapes. A version label is never presented as an artifact hash.

Comparison uses ORB features, cross-checked Hamming matches, RANSAC homography, an
inlier-ratio gate of 0.60, and a reprojection-error gate of 3% of the current image
diagonal. Automatic learned re-identification remains disabled, but a user-selected
same-region proposal can be confirmed and compared. The service recomputes both masks
from the sanitized images; caller-supplied areas never drive a measurement. Comparable
results require confirmation, registration thresholds, and the configured repeated-
capture evidence. They may include approximate normalized width, height, area,
perimeter, border, color, texture, and ulceration-like contrast changes. Paired
millimeter changes appear only when both images pass the same physical-calibration
contract. Failed gates return explicit suppression reasons and no change value.

## Model release manifest

`ORALSIGHT_RELEASE_MANIFEST_PATH` may point to a read-only JSON manifest. See
`release-manifest.example.json` for the fail-closed shape. The schema is implemented in
`src/oralsight_api/release_manifest.py`; the ONNX-capable schema version is `1.1` and
requires:

- a fixed schema version, release ID, UTC creation time, and code revision;
- one unique entry per declared model head;
- safe manifest-relative artifact paths and pinned SHA-256 digests;
- dated aggregate metrics, no unmet requirements, reviewer approval and evidence;
- `artifactFormat: "onnx"` and a `.onnx` manifest-relative artifact path;
- a `sanitized_full_image` input scope plus exact input/output tensor names,
  NCHW RGB layout, stretch resize with linear interpolation, dimensions, scale,
  and per-channel normalization;
- exact output kind and fixed class ordering;
- a sigmoid segmentation threshold, calibrated softmax temperature and abstention
  threshold for classifiers, or L2-normalized minimum dimensions for embeddings;
- optional pinned comparison validation for repeated-capture area error.

The loader limits manifest size, forbids URL/absolute/parent-traversal artifact paths,
verifies artifact bytes, parses enabled ONNX models with the CPU-only OpenCV backend, and
creates an immutable runtime state. It runs one zero-image startup prediction per enabled
head to validate tensor names, output rank and size, finite numeric output, class count,
and configured probability transform. Networks are retained and reused behind a
per-network lock because OpenCV `Net` mutation is not assumed thread-safe. Invalid,
missing, unreadable, hash-mismatched, unparsable, wrongly shaped, or non-finite model
configuration disables that head while liveness and quality-only abstention remain
available.

The manifest and adapter are deployment mechanisms, not a model, training result, or
claim of clinical validity. A real head still requires locked patient-disjoint evaluation
and the review evidence represented by the release manifest. Do not mark a head enabled
merely because an ONNX file can execute.

## Fixture isolation and privacy

Synthetic fixture responses are disabled by default. They are available only when the
service starts with `ORALSIGHT_ENABLE_DEMO_FIXTURES=true`; use that setting only for a
clearly separated demonstration deployment. When disabled, any `bundled_demo` analyze or
compare request returns `403 demo_fixtures_disabled` before image processing.

When explicitly enabled, the direct manual demonstration result is possible only when all
of these match the canonical synthetic fixture in
`packages/contracts/fixtures/bundled-demo.json`:

- `inputOrigin` is `bundled_demo`;
- `selectedRegion` is `left_buccal_mucosa`;
- `fixtureSha256` equals the actual uploaded bytes;
- the actual SHA-256 is `61b49da924681f2a8dc6aab6380d7f197483925677af3a4c0a9db63c55a10338`.

Filename, content type, and a caller-declared hash can never trigger fixture behavior by
themselves. Fixture results are labeled `analysisOrigin: "manual_fixture"`, not as a cached
or live model result. An arbitrary capture receives `analysisOrigin: "unavailable"` after
a runtime failure.

For manual fixture comparison, both image byte hashes must be canonical and both
prior-analysis references must identify complete, quality-accepted fixture results with
the canonical normalized area. If the bytes are canonical but those references are
ineligible, the service returns the specific prior-analysis suppression reasons without
invoking live image processing. An arbitrary or merely caller-labeled demonstration
capture stays fail-closed.

## Response signatures

JSON responses can carry detached Ed25519 signatures. Configure a raw 32-byte Ed25519 private key as standard base64 in `ORALSIGHT_RESPONSE_SIGNING_PRIVATE_KEY_B64`. When configured, every JSON response adds:

- `X-OralSight-Signature`: the standard-base64 Ed25519 signature.
- `X-OralSight-Key-Id`: the first 16 lowercase hexadecimal characters of SHA-256 over the raw 32-byte public key.

The exact signed message is the UTF-8/byte concatenation:

```text
oralsight-response-v1\n${X-Request-ID}\n${exact raw JSON response body}
```

Clients must verify the signature over the unparsed response bytes and compare the
derived public-key ID before parsing or trusting the JSON.
`ORALSIGHT_RESPONSE_SIGNING_KEY_ID` may be set, but startup rejects it unless it exactly
equals the derived key ID. Local development defaults to
`ORALSIGHT_DEPLOYMENT_MODE=development`, may be unsigned, and omits both signature headers
when no key is configured.

Production must set both:

```text
ORALSIGHT_DEPLOYMENT_MODE=production
ORALSIGHT_REQUIRE_RESPONSE_SIGNING=true
```

Production startup then fails unless a valid private key is available. The repository
`compose.yaml` publishes port 8000 on host loopback only; do not broaden that binding
without HTTPS, signing-required configuration, encrypted ephemeral temporary storage,
and ingress connection/rate/request-timeout limits.

### Vercel Services

The repository root `vercel.json` defines `services/inference` as a FastAPI
service, maps `vercel_entrypoint:app`, and rewrites `/api/*` to the service after
stripping the public prefix. Configure the production variables from
`.env.example` as protected project variables. The deployed service exposes
health at `https://oralsight-inference.vercel.app/api/healthz`, and the mobile
base URL is `https://oralsight-inference.vercel.app/api`.

The 1,750,000-byte per-image boundary and 3,762,144-byte compare request budget
leave 737,856 bytes of headroom below a conservative 4,500,000-byte
interpretation of Vercel's documented 4.5 MB function request-body limit. The
regression suite encodes a real multipart request with two maximum-size images
and maximum-size metadata to keep that deployment constraint tested.

The Vercel entry point does not bypass any gate. The production deployment
contains the hash-matched anatomy and segmentation artifacts, requires response
signing, disables demonstration fixtures, and passed live requests to all four
routes. Its direct runtime dependencies use exact tested pins so the Vercel
installer cannot silently select newer allowed versions. Disabled appearance,
disease-category, re-identification, and numeric change outputs remain
disabled. Verify platform-level upload-spool cleanup, rate limits, and log
configuration during final host review.

The service has no database, object store, accounts, retained jobs, analytics, or
application-managed upload copy. FastAPI/python-multipart may spool a bounded upload to
its temporary-file backing store before application code runs. Upload streams are closed
in `finally`, decoded image pixels remain in process memory only for the request, and the
production server disables access logging. Deploy the process temp directory on encrypted
ephemeral storage or `tmpfs`, then verify spool cleanup on success and every error path.
Application logs are designed not to include bodies, filenames, query strings, image
hashes, response results, or request headers; production proxy/log configuration still
requires independent verification.

## Concurrency and availability

Pillow/OpenCV sanitization, quality analysis, and registration run through `asyncio.to_thread`, so CPU-heavy image work does not execute on the FastAPI event-loop thread. A process-local semaphore bounds active image-processing calls. `ORALSIGHT_MAX_CONCURRENT_INFERENCE` accepts an integer from 1 through 32 and defaults to the smaller of two or the detected CPU count; invalid explicit values fail service startup.

The semaphore is not a durable job system: waiting work belongs to the active HTTP
request, and no payload or result is persisted. Python cannot forcibly stop an OpenCV
worker thread, so cancellation deliberately holds its semaphore slot until the current
function exits; this prevents disconnected requests from exceeding the configured CPU
bound. When explicitly enabled, the exact hash-verified bundled fixture bypasses image
processing and the semaphore. Production ingress should still enforce the existing
request-size limit plus appropriate connection limits, request timeouts, and rate limits,
because waiting requests retain their in-flight upload bytes until completion or
cancellation cleanup.

## Locked container dependencies

The container installs the hash-pinned runtime dependency export in `requirements.lock.txt` with `--require-hashes --no-deps`. This keeps container dependency resolution tied to the root `uv.lock` instead of resolving version ranges during a build.

After an intentional dependency update, refresh the export from the repository root:

```powershell
py -3.12 -m uv export --frozen --package oralsight-inference --no-dev --no-emit-project --format requirements.txt --no-header --output-file services/inference/requirements.lock.txt
```

CI regenerates this file into a temporary path and compares it byte-for-byte before running the test suite.
