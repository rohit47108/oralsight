# OralSight worker

This service runs slow OralSight work outside the request path. It processes
real captures and existing records; it never substitutes bundled images or
invented model output.

## What it runs

- image analysis, gated physical calibration, and comparison against the
  internal inference service;
- deterministic multi-view oral observation-surface rendering inside the
  worker;
- PDF report rendering through the platform service;
- captioned H.264 scan-summary video rendering inside the worker; and
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
geometry is a standard region map. Saved capture coverage and conservative
image-color summaries personalize its observation layer; they do not reshape
the anatomy. The GLB and result manifest contain:

- source capture, asset, and SHA-256 provenance;
- per-view quality evidence and rejection reasons;
- region coverage and named-mesh mappings;
- the exact renderer version and deterministic generation time;
- abstention thresholds and limitations; and
- calibration status.

A calibration ID on a reconstruction remains a provenance reference only; it
does not rescale or reshape the observation surface. Physical estimates are
computed separately during analysis from the same hash-verified sanitized
capture. The versioned card uses a 20 mm ArUco marker (dictionary 4x4_50,
marker 17). The worker returns estimated width, height, and area only when:

- the user confirmed that the marker and observation are on the same plane;
- the expected marker is found and is at least 40 pixels wide;
- marker-edge variation passes the pose check;
- the candidate boundary and normalized area are available; and
- the marker is close enough to the candidate for the configured gate.

Any failed gate returns null physical values plus specific reasons. Passing
values remain labeled "calibrated estimate," not exact clinical measurements.
The generated GLB is labeled a "personalized oral observation surface," never
an anatomical digital twin.

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

The result manifest records source capture and asset provenance without image
bytes, candidate-outline presence, confirmation and comparability state,
guidance source, renderer and template versions, caption mode, duration, and
audio status.

## Queue guarantees

Jobs are strict `oralsight.job.v1` envelopes on the
`oralsight:jobs:v1` Redis Stream. A consumer group provides explicit claims and
stale-job recovery. The worker also provides:

- a per-worker and per-job heartbeat;
- an idempotency lease renewed during processing;
- cancellation checks before and during work;
- bounded exponential retry with jitter;
- a delayed Redis sorted set and atomic retry promotion;
- a dead-letter stream after the attempt or time budget is exhausted; and
- a retention index that deletes expired dead-letter entries.

The platform requests cancellation by setting
`oralsight:job-cancelled:v1:{jobId}` with a TTL no longer than the job expiry.
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

## Internal authentication

Outbound calls can be signed with a short-lived HMAC proof over the HTTP method,
path, timestamp, nonce, and exact body hash. Set
`ORALSIGHT_WORKER_SERVICE_HMAC_SECRET` from a secret manager. Staging and
production fail at startup when the secret is shorter than 32 bytes or an
internal service URL is not HTTPS. Development can run unsigned against local
services.

Receiving services must reject stale timestamps, reused nonces, unknown service
IDs, bad body hashes, and invalid signatures. Authorization still belongs to
the platform service; a valid worker signature is not permission to access a
different account.

## Local development

```powershell
cd services/worker
Copy-Item .env.example .env
uv sync --extra dev
uv run pytest
uv run uvicorn oralsight_worker.main:app --host 127.0.0.1 --port 8010 --no-access-log
```

Run Redis and the platform/inference services separately, then add a valid
envelope to `oralsight:jobs:v1` under the `envelope` field. The platform API is
the intended producer; clients must not publish directly to Redis.

Health endpoints:

- `GET /healthz` proves that the process is alive.
- `GET /readyz` also checks that the worker loop is running and Redis responds.
- `oralsight-worker health --url http://127.0.0.1:8010/readyz` is suitable for a
  container health check.

## Internal endpoint contract

The worker expects these authenticated internal endpoints:

- Platform: `GET /internal/v2/assets/{assetId}/content`
- Platform: `POST /internal/v2/assets/generated` for signed multipart artifact
  and JSON metadata upload
- Platform: `POST /internal/v2/jobs/{jobId}/result`
- Platform: `POST /internal/v2/jobs/{jobId}/retention`
- Platform: `POST /internal/v2/reports/render`
- Platform: `POST /internal/v2/deletion-requests/{requestId}/execute`
- Inference: `POST /v1/analyze` and `POST /v1/compare`

The generated-asset response must include an artifact ID, SHA-256, and exact
media type. A mismatch is a permanent job failure; the worker never reports an
unpublished or substituted artifact as complete.

## Production deployment

Build from this directory:

```powershell
docker build -t oralsight-worker .
```

The image installs FFmpeg, DejaVu fonts, and the headless OpenCV runtime. The
process still runs as the unprivileged `oralsight` user, and temporary render
directories are removed after each job.

Run at least two consumers with unique `ORALSIGHT_WORKER_CONSUMER_NAME` values.
Use managed Redis with TLS, private service networking, a secret manager, and
restricted service identities. Do not enable HTTP access logs or debug logging
for job requests. Alerts should cover a stale worker heartbeat, growing retry
depth, any dead-letter entry, and repeated cleanup failures.
