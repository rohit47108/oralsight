# Stoma3D production runbook

`compose.yaml` is local development only. `compose.production.yaml` is the hardened
production surface. It starts application containers only; PostgreSQL, Redis, S3,
OIDC, TLS certificates, DNS, and the ingress proxy are external operator-owned
services.

## Required services

- PostgreSQL with TLS, continuous point-in-time recovery, encrypted storage, and
  automated backups.
- Redis with TLS, authentication, `noeviction`, multi-zone persistence, and AOF.
- A private S3 bucket with all four Block Public Access controls enabled, Bucket owner
  enforced Object Ownership (ACLs disabled), a TLS-only bucket policy, and server-side
  encryption. Prefer workload identity over static access keys.
- An OIDC application with HTTPS issuer/JWKS URLs, asymmetric signing keys, and
  the exact API access-token role claim configured in
  `STOMA3D_PLATFORM_OIDC_ROLE_CLAIM`. The platform does not accept a generic
  `roles` claim as a fallback.
- HTTPS routes for the platform and inference services. The proxy must attach to the
  external Docker network named by `STOMA3D_INGRESS_NETWORK`.
- Immutable, digest-pinned platform, inference, and worker images. The inference
  image must contain the locked release manifest and every hash-matched artifact.
- One Ed25519 response-signing key pair per environment. Store the private key
  only on inference. Pin the matching raw public key on the worker and mobile
  builds. The worker derives the key ID from that public key instead of trusting
  a separate configured ID.

Copy `production.env.example` to a secret-managed location outside Git. Replace every
placeholder, create the ingress network, validate the file, and deploy:

```sh
docker network create stoma3d-ingress
docker compose --env-file /secure/stoma3d-production.env \
  -f compose.production.yaml config --quiet
docker compose --env-file /secure/stoma3d-production.env \
  -f compose.production.yaml up -d
```

Do not add host ports for PostgreSQL, Redis, or S3-compatible storage. The production
compose file does not start or expose them. The service settings fail startup if
production uses local authentication, SQLite, non-TLS Redis, local object storage,
HTTP public URLs, default secrets, unsigned inference, or automatic schema creation.

New capture upload intents always target the platform's short-lived
`/v2/storage/uploads/` capability endpoint. That endpoint holds the account row lock
through the object-store write, so this serialization is the primary delete-all
guarantee for newly issued uploads.

Before upgrading any deployment that issued direct S3 PUT URLs, stop the old API
instances, revoke or rotate the object-store credentials that signed those URLs,
confirm the retired credentials can no longer authorize PUT, and drain for the
largest historical URL lifetime plus the maximum request-completion duration allowed
by the ingress and object store. Only then allow delete-all workers from the upgraded
release to complete. This is required because a PUT authorized before expiry or
credential revocation may already be in progress.

Keep `STOMA3D_PLATFORM_UPLOAD_COMPLETION_QUIET_SECONDS` at least as long as that
maximum request-completion duration. Delete-all continues to wait through recorded
capability expiry, delete, rescan, and verify object keys as defense in depth.
Migration `20260813_0010` conservatively drains pre-migration capabilities; do not
bypass or shorten that migration drain. Neither the migration nor the quiet interval
replaces the credential-rotation/drain step for legacy direct S3 URLs.

## Release check

Before routing traffic:

1. Confirm `platform-migrate` exited successfully.
2. Have the designated first administrator sign in once, run
   `stoma3d-bootstrap-admin` with the exact subject and confirmation phrase as
   `STOMA3D_PLATFORM_BOOTSTRAP_ADMIN_SUBJECT` and
   `STOMA3D_PLATFORM_BOOTSTRAP_CONFIRMATION`. Require the exact phrase
   `BOOTSTRAP STOMA3D FIRST ADMIN`, then remove both variables. The command
   must create or confirm the durable bootstrap seal, remain idempotent only for
   the same sole administrator, and refuse every different second account. The
   seal must remain closed even if administrator or audit rows are later removed.
3. Assign the administrator value in the configured OIDC access-token role
   claim and require a fresh sign-in. Verify that removing the token role locks
   the administrator routes on refresh and no later than the configured
   privileged-token maximum age plus clock leeway.
4. Confirm `platform-api`, `inference`, and `worker` are healthy.
5. Check `GET https://api.example.org/readyz` reports database, queue, and storage as
   ready.
6. Check inference `GET /healthz` reports `productionReady: true`, signing configured,
   no demo fixtures, and the expected release ID and enabled heads.
7. Send a synthetic analyze and compare request through a worker. Confirm the
   inference response echoes the worker's UUID request ID, includes
   `Cache-Control: no-store`, and reports the same signing key ID produced by
   `SHA-256(raw_public_key)[:16]`. A missing signature, altered body, wrong
   request ID, or wrong key ID must end as a permanent job failure.
8. Run one synthetic or expressly licensed end-to-end scan, report, encrypted export,
   share/revoke, and delete-all test. Never use restricted medical images for a smoke
   test.

To admit a clinician applicant, the identity administrator first assigns
`clinician_pending` in the configured access-token role claim and supplies a
searchable invitation reference. After a fresh sign-in, the applicant opens
`/professional-apply` and submits credentials. Approval alone must leave the
workspace locked. After approval, replace `clinician_pending` with `clinician`,
require another fresh sign-in, and have the clinician select **Check secure
access**. The first-observed timestamp records when the role first appeared in a
validated, signed access token; it is audit history, not a substitute for
checking the current token.

Before launch, use `stoma3d-add-admin` to create a distinct recovery
administrator. This is a trusted infrastructure-operator command, not proof that
another administrator personally approved the change. Supply target and active
administrator reference subjects only through temporary
`STOMA3D_PLATFORM_ADMIN_TARGET_SUBJECT` and
`STOMA3D_PLATFORM_ADMIN_REFERENCE_SUBJECT` values. Supply the confirmation
through `STOMA3D_PLATFORM_ADMIN_CONFIRMATION`, require the exact `ADD STOMA3D
ADMIN` phrase, verify the audit event, then clear all three values. The command
must reject a non-admin reference and a target that matches the reference. The
reference proves that this is an additional-admin operation rather than
zero-admin recovery. Assign `admin` in the exact configured token claim and
require a fresh sign-in; the database promotion alone does not open
administrator routes.

If a durably sealed installation reaches zero saved administrators, run
`stoma3d-recover-admin` with only temporary
`STOMA3D_PLATFORM_RECOVERY_ADMIN_SUBJECT` and
`STOMA3D_PLATFORM_RECOVERY_CONFIRMATION` values. Require the exact phrase
`RECOVER STOMA3D SEALED INSTALLATION WITH ZERO ADMINS`, then clear both values.
The command must refuse an unsealed installation and any database in which an
administrator still exists. Assign `admin` in the exact token claim and require
a fresh sign-in after recovery. Exercise this break-glass path in staging and
retain the operator evidence outside application logs.

The default `STOMA3D_PLATFORM_PRIVILEGED_TOKEN_MAX_AGE_SECONDS=900` bounds how
long an already-issued token can retain a removed administrator,
`clinician_pending`, or clinician role. Configure the provider to refresh access
tokens within that bound. This is bounded lockout, not instant token revocation.

## Backup and restore

Use a documented maximum backup lifetime; 35 days is the launch target. The same
period must appear in the user-facing privacy notice. Backups stay encrypted with a
separate key and access role.

- PostgreSQL: continuous WAL/PITR plus a daily provider snapshot. Alert on a missed
  backup and run an isolated restore drill at least monthly.
- S3: keep the live bucket private. If versioning is enabled, expire non-current
  versions within the published backup window. A normal object delete is not enough
  to purge old versions.
- Redis: keep AOF/provider snapshots for operational recovery, but treat PostgreSQL
  as the durable job ledger. The platform outbox republishes queued jobs whose stream
  delivery is missing or stale; worker callbacks are idempotent.
- Signing, HMAC, share-derivation, KMS, and OIDC secrets belong in a secret manager.
  Back up keys only through that manager's protected recovery process.

Restore into an isolated network first. Restore PostgreSQL to the latest safe point,
restore only S3 objects still referenced by live rows, run `alembic upgrade head`, and
verify foreign keys, object sizes/SHA-256 metadata, deletion tombstones, and health
checks. Do not restore a pre-deletion object or account after a completed deletion.
If the latest deletion state cannot be proven, keep the recovered service offline.

## Retention and deletion

The platform sweep runs every 15 minutes by default and deletes bytes before making
their metadata unavailable.

- encrypted exports: 7 days;
- opted-in product analytics: 30 days;
- successful job request/result payloads: 30 days;
- failed/dead-letter job payloads: 7 days;
- rendered reports and generated map/video artifacts: 365 days;
- share exchange credentials: their short expiry, with share records for 90 days;
- clinician/access/audit records: 7 years, unless delete-all applies;
- capture files: the capture's explicit expiry, or delete-all.

Delete-all removes live database rows and object bytes, clears reports and exports,
revokes access, tombstones the account identity, and tells the client to rotate its
installation key. Encrypted disaster-recovery copies must age out within the
published backup window and must never be replayed after deletion.

Record each monthly restore drill, retention sweep alert, key rotation, and deletion
verification without storing image content, tokens, filenames, or request bodies in
logs.

## Response-signing key rotation

Generate a fresh set with
`uv run --project services/inference python services/inference/scripts/generate_signing_key.py`.
Never copy the private value to a worker, mobile build, log, ticket, or source
file. Because clients pin one public key, rotate as a controlled cutover:

1. Stop publishing new analysis/comparison jobs and let active jobs finish.
2. Build the next worker and mobile release with the new public key. Do not route
   them to an inference instance that still uses the old private key.
3. Deploy an isolated inference/worker pair with the new private/public values
   and derived key ID, then run the tamper, request-ID, and canary checks.
4. Route the matching worker pair and new mobile release to the matching
   inference deployment. Keep old mobile clients on the old signed deployment
   during a planned overlap when the routing platform supports versioned origins.
5. If versioned overlap is unavailable, announce a maintenance cutover. Old
   clients must fail unavailable rather than accept a response under the wrong
   key. Remove the old private key only after the supported-client window ends.

An emergency key compromise uses the same fail-closed cutover but starts by
isolating the compromised signer. Never temporarily disable worker verification.
