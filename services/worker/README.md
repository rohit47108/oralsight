# Stoma3D worker

This service runs slow Stoma3D work outside the request path. It processes
real captures and existing records; it never substitutes bundled images or
invented model output.

## What it runs

- image analysis, gated physical calibration, and comparison against the
  internal inference service;
- deterministic multi-view oral observation-surface rendering inside the
  worker;
- PDF report rendering through the platform service;
- captioned H.264 scan-summary video rendering inside the worker;
- public-key-encrypted portable account exports through the platform service;
- complete account deletion through the platform service.

Reconstruction and summary-video rendering do not require separate services.
The container includes the image and video tooling they need. Generated files
are uploaded to the protected platform asset store and the worker verifies that
the returned media type and SHA-256 match the bytes it created.

## Local observation-surface renderer

The reconstruction job downloads each hash-verified view one at a time, checks
decodeability, resolution, exposure, contrast, and sharpness, then discards the
image bytes. It requires at least three usable captures from three named angles.
If those checks fail, the job returns a documented abstention and no GLB.

A passing job creates a valid GLB containing the eight fixed named regions. The
geometry is a standard region map. A coarse, deterministic multi-view color
projection is baked into the observed region meshes from the verified captures;
the source pixels are not embedded and the projection does not reshape anatomy.
The GLB and result manifest contain:

- source capture, asset, and SHA-256 provenance;
- per-view quality evidence and rejection reasons;
- region coverage and named-mesh mappings;
- confirmed observation pins with region, named mesh, normalized UV location,
  date, status, asset version, and measurement provenance;
- the exact renderer version and deterministic generation time;
- abstention thresholds and limitations; and
- calibration status.

A calibration ID on a reconstruction remains a provenance reference only; it
does not rescale or reshape the observation surface. Physical estimates are
computed separately during analysis from the same hash-verified sanitized
capture. The versioned card uses a 20 mm ArUco marker (dictionary 4x4_50,
marker 17). A marker-plane transform is applied to the saved candidate polygon.
The worker returns estimated width, height, and area only when:

- the user confirmed that the marker and observation are on the same plane;
- the expected marker is found and is at least 40 pixels wide;
- marker-edge variation passes the pose check;
- the candidate boundary and normalized area are available; and
- the marker is close enough to the candidate for the configured gate.

Any failed gate returns null physical values plus specific reasons. Passing
values remain labeled "calibrated estimate," not exact clinical measurements.

The same optional calibration request can also normalize two approximate color
descriptors. The inference service projects the fixed interiors of all four
neutral patches (printed values 35, 100, 170, and 235) from the detected marker,
then requires sufficient pixels, uniform patches, monotonic channel values,
useful range, no clipping, and a bounded affine RGB fit. A passing fit adjusts
only candidate `meanRedness` and `meanBrightness` on a copied pixel array. It
does not alter the stored/sanitized image, candidate mask, anatomy, quality,
texture, appearance or disease heads, or guidance. It records
`descriptor_color_reference=neutral-grayscale-patches-affine-rgb-v1` in model
versions and explains the scope in limitations. A failed color gate leaves the
original descriptors in place with a suppression reason and does not invalidate
an independently passing size estimate.

The generated GLB may be labeled a "personalized oral observation surface" only
because it carries the user's image-colored observations and confirmed pins. Its
geometry remains the generic region map; it is never described as reconstructed
anatomy or a digital twin. Unconfirmed automated match suggestions are never
added.

## Local summary-video renderer

The summary-video job creates a silent 1280x720 MP4 using the bundled FFmpeg
runtime. It uses H.264 video with `yuv420p` pixel format, smooth crossfades, and
burned-in captions. Every scene includes the non-diagnostic statement.

The platform must select one to three real observations. The worker downloads
their hash-verified current images and any confirmed baseline images, draws the
saved candidate polygons, and shows a normalized change only when the user
confirmed the match and registration marked the pair comparable. A physical
area appears only when valid calibration evidence supplied a calibrated
estimate. The closing guidance scene accepts only fixed codes; professional or
prompt review wording requires a clinician-approved rule version. Missing or
invalid source evidence makes the render unavailable instead of producing a
generic substitute.

The current release contains no approved repeated-capture evidence at the fixed
10% area-error gate, so its live comparisons are not quantitatively comparable
and summary videos omit normalized and calibrated change. A client-safe
registration transform may still support an explicitly visual aligned reveal;
that transform is not measurement evidence.

The result manifest records source capture and asset provenance without image
bytes, candidate-outline presence, confirmation and comparability state,
guidance source, renderer and template versions, caption mode, duration, and
audio status.

## Queue guarantees

Jobs are strict `stoma3d.job.v1` envelopes on the
`stoma3d:jobs:v1` Redis Stream. A consumer group provides explicit claims and
stale-job recovery. The worker also provides:

- a per-worker and per-job heartbeat;
- an idempotency lease renewed during processing;
- cancellation checks before and during work;
- bounded exponential retry with jitter;
- a delayed Redis sorted set and atomic retry promotion;
- a dead-letter stream after the attempt or time budget is exhausted; and
- a retention index that deletes expired dead-letter entries.

The platform requests cancellation by setting
`stoma3d:job-cancelled:v1:{jobId}` with a TTL no longer than the job expiry.
The worker clears that key after a terminal result; per-job heartbeat keys also
expire automatically.

The queue contains opaque asset IDs, hashes, and operation metadata. It never
contains image bytes or signed asset URLs. Worker logs use an allowlist and do
not include payloads, images, response bodies, URLs, tokens, or exception text.

## Retention

Every envelope carries explicit deadlines and cleanup targets. Validation caps
sanitized input retention at 24 hours, successful generated results at 30 days,
and failed/dead-letter data at 7 days. The platform receives the retention
policy after each terminal outcome so its blob/database cleanup can run. The
worker removes expired dead-letter entries from Redis. Deployments may delete
sooner.

## Portable data export

An export job never places a password, private key, record payload, or file byte
in Redis. It carries only a raw X25519 recipient public key and fixed options.
The platform creates a normal ZIP, encrypts the complete archive with a fresh
ephemeral X25519 key, HKDF-SHA-256, and AES-256-GCM, publishes the encrypted
artifact, and deletes plaintext work in `finally`. The worker accepts completion
only when the response includes the expected request, private artifact metadata,
SHA-256, byte size, and the ephemeral public key, salt, and nonce needed by the
recipient. The matching private key remains in protected device storage.

## Internal authentication

Outbound calls can be signed with a short-lived HMAC proof over the HTTP method,
path, timestamp, nonce, and exact body hash. Set
`STOMA3D_WORKER_SERVICE_HMAC_SECRET` from a secret manager. Staging and
production fail at startup when the secret is shorter than 32 bytes or an
internal service URL is not HTTPS. Development can run unsigned against local
services.

Receiving services must reject stale timestamps, reused nonces, unknown service
IDs, bad body hashes, and invalid signatures. Authorization still belongs to
the platform service; a valid worker signature is not permission to access a
different account.

## Inference response integrity

The analyze and compare calls use a fresh UUIDv4 `X-Request-ID`. Before parsing
JSON, the worker buffers the bounded response bytes and requires
`Cache-Control: no-store` plus the exact echoed request ID. When
`STOMA3D_WORKER_INFERENCE_RESPONSE_SIGNING_PUBLIC_KEY_B64` is configured, it
also requires `X-Stoma3D-Key-Id` and `X-Stoma3D-Signature`, derives the
expected key ID from the pinned raw Ed25519 public key, and verifies the
signature over:

```text
stoma3d-response-v1\n<request-id>\n<exact-response-body>
```

The worker requests `Accept-Encoding: identity` and rejects an encoded response
so the verified bytes are the bytes supplied to JSON parsing.

Staging and production cannot start without the pinned public key. Development
may omit it only for a loopback inference URL. Configuring a key in any
environment makes signatures mandatory; there is no unsigned fallback after a
verification failure.

## Local development

```powershell
cd services/worker
Copy-Item .env.example .env
uv sync --extra dev
uv run pytest
uv run uvicorn stoma3d_worker.main:app --host 127.0.0.1 --port 8010 --no-access-log
```

Run Redis and the platform/inference services separately, then add a valid
envelope to `stoma3d:jobs:v1` under the `envelope` field. The platform API is
the intended producer; clients must not publish directly to Redis.

Health endpoints:

- `GET /healthz` proves that the process is alive.
- `GET /readyz` also checks that the worker loop is running and Redis responds.
- `stoma3d-worker health --url http://127.0.0.1:8010/readyz` is suitable for a
  container health check.

## Internal endpoint contract

The worker expects these authenticated internal endpoints:

- Platform: `GET /internal/v2/assets/{assetId}/content`
- Platform: `POST /internal/v2/assets/generated` for signed multipart artifact
  and JSON metadata upload
- Platform: `POST /internal/v2/jobs/{jobId}/result`
- Platform: `POST /internal/v2/jobs/{jobId}/retention`
- Platform: `POST /internal/v2/reports/render`
- Platform: `POST /internal/v2/exports/render`
- Platform: `POST /internal/v2/deletion-requests/{requestId}/execute`
- Inference: `POST /v1/analyze` and `POST /v1/compare`

The generated-asset response must include an artifact ID, SHA-256, and exact
media type. A mismatch is a permanent job failure; the worker never reports an
unpublished or substituted artifact as complete.

## Production deployment

Build from this directory:

```powershell
docker build -t stoma3d-worker .
```

The image installs FFmpeg, DejaVu fonts, and the headless OpenCV runtime. The
process still runs as the unprivileged `stoma3d` user, and temporary render
directories are removed after each job.

Run at least two consumers with unique `STOMA3D_WORKER_CONSUMER_NAME` values.
Use managed Redis with TLS, private service networking, a secret manager, and
restricted service identities. Do not enable HTTP access logs or debug logging
for job requests. Alerts should cover a stale worker heartbeat, growing retry
depth, any dead-letter entry, and repeated cleanup failures.
