# Stoma3D Platform API

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
uv run stoma3d-platform-api
```

The container uses the locked production dependencies and runs as a non-root user:

```powershell
docker build -t stoma3d-platform-api .
```

The repository-level `compose.yaml` is for local development. Production uses
[`compose.production.yaml`](../../compose.production.yaml) and the backup, restore,
retention, and release checks in
[`deploy/production/RUNBOOK.md`](../../deploy/production/RUNBOOK.md).

The development-only issuer accepts HS256 tokens signed with the configured local
secret. Staging and production reject that mode and require an HTTPS OIDC issuer,
JWKS endpoint, expected audience, and asymmetric signing algorithms.

## Administrator setup and clinician activation

There is no public role-promotion endpoint. To create the first administrator,
the intended account must sign in once so it exists in PostgreSQL. Run the
one-time command with process-scoped environment variables:

```powershell
$bootstrapSubject = Read-Host "Exact OIDC subject for the first administrator"
$env:STOMA3D_PLATFORM_BOOTSTRAP_ADMIN_SUBJECT = $bootstrapSubject
$env:STOMA3D_PLATFORM_BOOTSTRAP_CONFIRMATION = "BOOTSTRAP STOMA3D FIRST ADMIN"
uv run stoma3d-bootstrap-admin
Remove-Item Env:STOMA3D_PLATFORM_BOOTSTRAP_ADMIN_SUBJECT
Remove-Item Env:STOMA3D_PLATFORM_BOOTSTRAP_CONFIRMATION
$bootstrapSubject = $null
```

The command refuses a missing or inactive account and rejects every different
target after bootstrap. The first successful bootstrap creates a durable,
identity-free database seal. That seal does not reopen if administrator accounts
or audit records are later removed. The command uses a PostgreSQL transaction
lock and writes an audit event without storing the OIDC subject in event details
or output. Assign the `admin` value in the configured access-token role claim,
then require a fresh sign-in. Both the PostgreSQL role and the validated token
role are required for administrator routes.

Add a second administrator with `stoma3d-add-admin`. This is a trusted
infrastructure-operator action, not proof that another administrator personally
approved it. Supply distinct target and active-administrator reference subjects
through temporary `STOMA3D_PLATFORM_ADMIN_TARGET_SUBJECT` and
`STOMA3D_PLATFORM_ADMIN_REFERENCE_SUBJECT` values, plus
`STOMA3D_PLATFORM_ADMIN_CONFIRMATION=ADD STOMA3D ADMIN`. The active reference
proves that this is a normal addition rather than zero-administrator recovery.
The audit event records the operator method without identifying an approving
person or printing either subject. Assign `admin` in the exact configured
access-token role claim and require a fresh sign-in after the command; the
database promotion alone does not open administrator routes.

If a previously sealed installation has zero saved administrators, use the
separate recovery command. It refuses an unsealed database and any database that
still has an administrator:

```powershell
$recoverySubject = Read-Host "Exact OIDC subject for the recovery administrator"
$env:STOMA3D_PLATFORM_RECOVERY_ADMIN_SUBJECT = $recoverySubject
$env:STOMA3D_PLATFORM_RECOVERY_CONFIRMATION = "RECOVER STOMA3D SEALED INSTALLATION WITH ZERO ADMINS"
uv run stoma3d-recover-admin
Remove-Item Env:STOMA3D_PLATFORM_RECOVERY_ADMIN_SUBJECT
Remove-Item Env:STOMA3D_PLATFORM_RECOVERY_CONFIRMATION
$recoverySubject = $null
```

Recovery is also a trusted infrastructure operation. Assign `admin` in the
configured token claim and require a fresh sign-in after it succeeds.

Clinician onboarding begins with an identity-provider invitation. The identity
administrator assigns `clinician_pending` and a searchable invitation reference.
After a fresh sign-in, the applicant opens `/professional-apply` and submits
credentials with that reference. Approval records the credential decision but
leaves the account pending. After the identity administrator replaces the token
role with `clinician`, the clinician signs in again and selects **Check secure
access**. Stoma3D promotes the saved role only while observing that value in a
validated token.

The recorded timestamp is when the required role was first observed in a
validated, signed access token; it is historical audit information, not a
current-access signal. Every protected request still checks the current token. Privileged roles
are stripped 900 seconds after token `iat` by default, plus clock leeway.
Provider-role removal is immediate on token refresh and otherwise bounded by
that age; it is not an instant revocation channel.
The validator reads only `STOMA3D_PLATFORM_OIDC_ROLE_CLAIM`; it does not fall
back to a generic `roles` claim.

## Current endpoints

- `GET /healthz` confirms that the process is alive.
- `GET /readyz` performs bounded database, queue, and object-storage checks.
- `GET /v2/me` provisions and returns the signed-in patient account.
- `POST /v2/clinician-verifications/current/activate` completes clinician
  activation only when an approved record and a currently validated
  `clinician` token role are both present.
- `GET /v2/consent-documents/current`, `GET /v2/consents`, and `POST /v2/consents`
  expose the exact version/hash accepted by a scan. Withdrawal blocks new cloud work
  and revokes active shares and clinician grants without silently deleting records.
- `POST /v2/me/deletion-requests` queues delete-all using an `Idempotency-Key`.
- The deletion transaction immediately blocks normal account routes, revokes
  active consent, shares, exchange tokens, and clinician grants, and cancels
  non-deletion work before the worker removes live rows and objects. `GET /v2/me`
  and the fingerprint-bound status receipt remain available only for visibility
  and polling.
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
uv run python scripts/decrypt_export.py export.stoma3d-export metadata.json recipient-private.key export.zip
```
