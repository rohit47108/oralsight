# OralSight verification record

Snapshot date: 2026-08-25

> **This result is not a diagnosis.** This record contains engineering evidence,
> not clinical validation, regulatory clearance, or a production-host sign-off.

The privileged-access contract changed after the previous release pass. Rows
marked pending must be replaced with exact evidence from the final rerun. This
the record does not guess counts, hashes, route totals, a commit, or an
archive filename.

## Source checks

The previous release pass covered the checks below. Rows marked pending changed
with the privileged-access work and need current evidence before sign-off.

| Surface                        | Evidence                                                                                            |
| ------------------------------ | --------------------------------------------------------------------------------------------------- |
| Locked install                 | `pnpm install --frozen-lockfile` passed                                                             |
| TypeScript tests               | `pnpm test` passed: contracts 33, mobile 155, web 56                                                |
| TypeScript checking            | `pnpm typecheck` passed                                                                             |
| Web lint                       | Pending final rerun                                                                                 |
| Python tests                   | Platform suite passed; inference/worker 151 passed                                                   |
| Python lint/format             | Ruff check and format passed                                                                        |
| Repository formatting          | `pnpm format:check` passed                                                                          |
| Contract generation            | Regenerated checked schemas successfully                                                            |
| Platform API contract          | OpenAPI regenerated and snapshot test passed                                                        |
| Web build                      | Production Next build passed with explicit CI-only dummy env bypass                                 |
| Missing web secrets            | Production config still fails closed when required values are missing                               |
| Android/iOS JavaScript bundles | Both Expo exports passed                                                                            |
| JavaScript dependency audit    | Patched `image-size` regression harness and high-severity audit passed                              |
| Python dependency audits       | Inference, platform, and worker production locks reported no known vulnerabilities                  |
| Standalone service locks       | Inference, platform, and worker `uv lock --check` passed in isolated directories                    |
| Deployment configuration       | Official Vercel schema/build-surface validator and both Compose parses passed                       |
| Vercel entry point             | Imported and exposed the expected inference application                                             |
| Workflow security              | Zizmor reported no findings; actions are immutable-SHA pinned and checkout credentials are disabled |
| Repository safety              | Forbidden-artifact, fixture, inventory, model hash, asset hash, and taxonomy audit passed           |

The web CSP implementation also has focused tests and a rendered response check on
the same code: a per-request nonce is present in the CSP and HTML, `strict-dynamic`
is enabled, `script-src` does not contain `unsafe-inline`, HSTS is declared, and
private/shared routes carry no-index/no-archive controls.

## Locked model decisions

| Head                                       | Decision                                                | Evidence                                                                                                                     |
| ------------------------------------------ | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Anatomy match                              | Enabled only for selected-region matching               | Macro F1 `0.9842`; minimum region recall `0.9302`; calibration error `0.0123`                                                |
| Current candidate segmentation             | Enabled only in the academic competition/research build | Dice `0.7192`; boundary F1 `0.6256`; current weight used Autooral training data under academic-research/non-commercial terms |
| SMART-OM-only replacement                  | Rejected                                                | Fresh untouched test Dice `0.6809`; boundary F1 `0.5616`; below fixed `0.70`/`0.60` gates                                    |
| Appearance                                 | Disabled                                                | Missing required licensed labels and held-out support                                                                        |
| Disease-category research                  | Disabled                                                | Failed performance/support/calibration/review gate                                                                           |
| Learned re-identification                  | Disabled                                                | Missing required longitudinal positive and hard-negative pairs                                                               |
| Learned quality/tissue/OOD/secondary heads | Disabled                                                | Implemented adapters, but no release-grade artifact/evidence                                                                 |

The SMART-OM-only replacement evidence is in
[`SEGMENTATION_SMART_OM_ONLY_ATTEMPT.json`](licenses-model-cards/SEGMENTATION_SMART_OM_ONLY_ATTEMPT.json).
It was evaluated once and not promoted. No threshold or gate was lowered after
the result.

## Checks that need an external environment

Docker Desktop's Linux engine is unavailable on this machine. The Windows service
is stopped and this session lacks permission to start it. Consequently these
operator checks must run in hosted CI or an elevated Docker environment:

- build and health-smoke the inference container;
- build the platform and worker containers;
- start PostgreSQL and Redis, apply the Alembic chain to head, and run
  `alembic check` against the real PostgreSQL dialect; and
- exercise the production Compose services together.

The source still has strong coverage for those paths: Compose parses, standalone
locks pass, all platform/worker tests pass, every table compiles for PostgreSQL,
and migrations are checked into the repository. That is not a substitute for the
real container/migration run.

The following also require owner accounts or physical resources:

- hosted GitHub workflows and full-history secret scan;
- Auth0/OIDC, managed PostgreSQL, TLS Redis, private S3, secret manager/KMS,
  container host, DNS/TLS, ingress limits, backup/restore, and alerts;
- current-tree preview and production deployment;
- EAS, Apple, and Google signing plus permanent bundle identifiers;
- two physical iPhones and two physical Android phones for the required scan,
  accessibility, camera-quality, calibration, and deletion matrix; and
- clinician review of wording, demo cases, and any urgency-rule file.

## Packaging acceptance

Create the final source archive only after the release commit is clean. Read the
destination at release time so this record does not claim an archive that does
not exist:

```powershell
$releaseArchive = Read-Host "Absolute path for the final OralSight source archive"
.\scripts\package-source.ps1 `
  -OutputPath $releaseArchive `
  -Force
```

The packager uses Git's tracked plus non-ignored source list and excludes ignored
dependencies, build outputs, secrets, local databases, datasets, captures, and
training runs. After extraction, rerun the repository audit and confirm the
required application/service/model files before publishing the archive hash.

## Sign-off boundary

The source can be handed off as a complete academic competition/research build.
It must not be represented as a fully deployed, clinically validated, or
commercially licensed public medical product until the external checks and model
rights above are complete.
