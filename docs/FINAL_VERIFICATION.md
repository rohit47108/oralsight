# OralSight verification record

Snapshot date: 2026-08-30

> **This result is not a diagnosis.** This record contains engineering evidence,
> not clinical validation, regulatory clearance, or a production-host sign-off.

This record covers the current source tree, local runtime, Android release
build, public website, and production inference service. Physical-device and
full hosted-platform checks remain separate.

## Source checks

The checks below were rerun after the final implementation and build fixes.

| Surface                        | Evidence                                                                                            |
| ------------------------------ | --------------------------------------------------------------------------------------------------- |
| Locked install                 | `pnpm install --frozen-lockfile` passed                                                             |
| TypeScript tests               | `pnpm test` passed: repository 22, contracts 33, mobile 158, web 64                                 |
| TypeScript checking            | `pnpm typecheck` passed                                                                             |
| Web lint                       | Full ESLint run passed                                                                              |
| Python tests                   | 337 passed; 1 PostgreSQL-only bootstrap test skipped in the default run                             |
| Python lint/format             | Ruff check and format passed                                                                        |
| Repository formatting          | `pnpm format:check` passed                                                                          |
| Contract generation            | Regenerated checked schemas successfully                                                            |
| Platform API contract          | OpenAPI regenerated and snapshot test passed                                                        |
| Web build                      | Next 16 Turbopack production build passed with the linked dependency-store root                     |
| Missing web secrets            | Production config still fails closed when required values are missing                               |
| Android/iOS JavaScript bundles | Both Expo exports passed; the Android release APK also built successfully                           |
| JavaScript dependency audit    | Optional patched-package harness and high-severity audit passed                                     |
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

## Local full-stack evidence

The Compose stack ran with healthy inference, platform API, worker, PostgreSQL,
and Redis services. The storage-initialization and Alembic migration jobs exited
successfully. Platform readiness reported database, queue, and object storage as
ready; worker readiness also passed.

The live local platform flow provisioned an account, recorded consent, created a
scan, pushed and pulled encrypted sync data, created and revoked a QR share,
recorded access history, completed clinician application and review, accepted an
opt-in analytics event, generated and downloaded an encrypted export through the
worker, verified its hash, and completed delete-all. The deleted account could
not continue normal work, clinician review data was gone, and object storage was
empty.

## Checks that still need outside resources

The following also require owner accounts or physical resources:

- hosted GitHub workflows for the final release commit;
- Auth0/OIDC, managed PostgreSQL, TLS Redis, private S3, secret manager/KMS,
  container host, DNS/TLS, ingress limits, backup/restore, and alerts;
- production deployment of the optional account/clinician platform stack;
- EAS, Apple, and Google signing plus permanent bundle identifiers;
- two physical iPhones and two physical Android phones for the required scan,
  accessibility, camera-quality, calibration, and deletion matrix; and
- clinician review of wording, demo cases, and any urgency-rule file.

## Source handoff

The authoritative source is the public `main` branch at
`https://github.com/rohit47108/oralsight`. A ZIP is not required for normal
handoff. Generated dependencies, local builds, secrets, databases, captures,
datasets, and training runs remain excluded from Git.

## Current deployment status

- Public web: `https://oralsight-sigma.vercel.app`
- Production inference: `https://oralsight-inference.vercel.app/api`

The inference health route reports production-ready, signed responses, no data
retention, fixtures disabled, and the anatomy plus candidate-segmentation heads
enabled. The optional hosted account/clinician platform still needs its managed
identity, database, Redis, private storage, worker, and secrets before those web
routes can be used with real accounts.

## Sign-off boundary

The repository, public site, live analysis service, Android release build, and
local full-product stack are ready for the competition demonstration. Store
distribution, the hosted account/clinician stack, the physical-device matrix,
and the closed research gates remain separate release work.
