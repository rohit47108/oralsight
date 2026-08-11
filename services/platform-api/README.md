# OralSight Platform API

This service owns product accounts, versioned consent, scan/capture metadata, private
object storage, durable jobs, encrypted exports, clinician sharing, audit events,
retention, and delete-all. Image inference remains in the separate stateless
inference service.

## Local development

PostgreSQL is required outside automated tests. Copy `.env.example` to `.env`, change
the credentials and local signing secret, then run:

```powershell
uv sync --all-extras
uv run alembic upgrade head
uv run oralsight-platform-api
```

The container uses the locked production dependencies and runs as a non-root user:

```powershell
docker build -t oralsight-platform-api .
```

The repository-level `compose.yaml` is for local development. Production uses
[`compose.production.yaml`](../../compose.production.yaml) and the backup, restore,
retention, and release checks in
[`deploy/production/RUNBOOK.md`](../../deploy/production/RUNBOOK.md).

The development-only issuer accepts HS256 tokens signed with the configured local
secret. Staging and production reject that mode and require an HTTPS OIDC issuer,
JWKS endpoint, expected audience, and asymmetric signing algorithms.

## Current endpoints

- `GET /healthz` confirms that the process is alive.
- `GET /readyz` performs bounded database, queue, and object-storage checks.
- `GET /v2/me` provisions and returns the signed-in patient account.
- `GET /v2/consent-documents/current`, `GET /v2/consents`, and `POST /v2/consents`
  expose the exact version/hash accepted by a scan. Withdrawal blocks new cloud work
  and revokes active shares and clinician grants without silently deleting records.
- `POST /v2/me/deletion-requests` queues delete-all using an `Idempotency-Key`.
- `GET /v2/me/deletion-requests/{request_id}` returns the owning user's status.
- `/v2/scan-sessions`, `/v2/capture-sets`, and `/v2/capture-assets` persist
  accepted standard or multi-angle capture metadata without making cloud use mandatory.
- `/v2/analysis-runs`, `/v2/match-proposals`, `/v2/lesions`, `/v2/reports`, and
  `/v2/jobs` persist signed provenance, explicit match decisions, and durable outputs.
- Report jobs render a real local PDF from integrity-checked accepted images, mask
  overlays, intake context, map locations, confirmed comparisons, limitations, and
  provenance. The disclaimer is printed on every page.
- Data exports are deterministic ZIP archives encrypted to the recipient's X25519
  public key before storage. Product analytics is allowlisted, aggregate-only for
  administrators, opt-in, and retained for 30 days.
- `POST /v2/sync/push` and `GET /v2/sync/pull` synchronize encrypted client
  payloads with opaque cursors. A deletion tombstone permanently defeats later stale
  upserts, including upserts with a larger client version.

Delete-all is represented as a durable job and deletion request. A worker can move it
through `requested`, `in_progress`, and a terminal state without doing destructive
cloud work in an HTTP request.

Redis Streams delivery is at least once. PostgreSQL is the durable outbox; unpublished
or stale queued envelopes are republished automatically, so a Redis restore does not
depend on the mobile client repeating its request.

Persistent analysis rejects `analysisOrigin=unavailable`. Cached or manual fixture
output is accepted only for bundled input. Match proposals always remain proposals
until a separate patient decision is stored. Millimeter fields are nullable and the
database accepts them only alongside complete, passing calibration evidence.

Every response carries `Cache-Control: no-store` and an opaque request ID. The access
logger accepts only method, route template, response status, duration, and request ID;
request bodies, query strings, tokens, subjects, filenames, and idempotency keys are
never logged.

## Tests

Tests are the only supported SQLite use:

```powershell
uv run --extra dev pytest
```

After changing a request, response, or enum contract, regenerate and verify the
checked OpenAPI document:

```powershell
uv run python scripts/generate_openapi.py
uv run --extra dev pytest tests/test_openapi_snapshot.py
```

The encrypted export download is not itself a ZIP. Save the artifact response JSON,
the downloaded ciphertext, and the raw/base64 X25519 private key in protected files,
then decrypt to a new path (the command refuses to overwrite):

```powershell
uv run python scripts/decrypt_export.py export.oralsight-export metadata.json recipient-private.key export.zip
```
