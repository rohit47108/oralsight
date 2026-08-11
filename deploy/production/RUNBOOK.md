# OralSight production runbook

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
- An OIDC application with HTTPS issuer/JWKS URLs and asymmetric signing keys.
- HTTPS routes for the platform and inference services. The proxy must attach to the
  external Docker network named by `ORALSIGHT_INGRESS_NETWORK`.
- Immutable, digest-pinned platform, inference, and worker images. The inference
  image must contain the locked release manifest and every hash-matched artifact.

Copy `production.env.example` to a secret-managed location outside Git. Replace every
placeholder, create the ingress network, validate the file, and deploy:

```sh
docker network create oralsight-ingress
docker compose --env-file /secure/oralsight-production.env \
  -f compose.production.yaml config --quiet
docker compose --env-file /secure/oralsight-production.env \
  -f compose.production.yaml up -d
```

Do not add host ports for PostgreSQL, Redis, or S3-compatible storage. The production
compose file does not start or expose them. The service settings fail startup if
production uses local authentication, SQLite, non-TLS Redis, local object storage,
HTTP public URLs, default secrets, unsigned inference, or automatic schema creation.

## Release check

Before routing traffic:

1. Confirm `platform-migrate` exited successfully.
2. Confirm `platform-api`, `inference`, and `worker` are healthy.
3. Check `GET https://api.example.org/readyz` reports database, queue, and storage as
   ready.
4. Check inference `GET /healthz` reports `productionReady: true`, signing configured,
   no demo fixtures, and the expected release ID and enabled heads.
5. Run one synthetic or expressly licensed end-to-end scan, report, encrypted export,
   share/revoke, and delete-all test. Never use restricted medical images for a smoke
   test.

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
