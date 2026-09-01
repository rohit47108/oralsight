# Stoma3D implementation checklist

Last updated: 2026-08-30

This is the working completion list for the Congressional App Challenge release.
Detailed evidence lives in [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md) and
[REQUIREMENT_AUDIT.md](REQUIREMENT_AUDIT.md).

## Repository and product

- [x] Keep all source, tests, commits, and deployment configuration in this repository.
- [x] Keep Parkinson's/NeuroSight out of the Stoma3D product.
- [x] Preserve the public repository and exclude secrets, private medical data, restricted datasets, and private model weights.
- [x] Complete the public website, mobile app, inference service, platform API, worker, shared contracts, ML tooling, assets, and release documents.

## Mobile experience

- [x] Consent, adaptive symptom intake, and the fixed eight-region workflow.
- [x] Real camera and photo input with stability guidance, quality/anatomy checks, retakes, interruption recovery, and offline errors.
- [x] Metadata stripping, signed analysis responses, encrypted local records, and complete local deletion.
- [x] Candidate highlighting, descriptors, explanations, confidence factors, oral observation map, history, and timeline.
- [x] User-confirmed comparison, registration, before/after controls, replay guidance, and suppression when data is not comparable.
- [x] Multi-angle capture, guided sweeps, valid calibration support, reminders, education, accessibility controls, and local PDF reports.
- [x] Optional account, encrypted sync, QR sharing, reports, artifacts, access history, recovery, and cloud deletion clients.
- [x] Android and iOS bundle exports and a successful Android release APK build.

## Web and hosted-product source

- [x] Responsive public website with complete navigation, metadata, accessibility, security headers, and clear product copy.
- [x] Patient, clinician, and administrator workspaces with real empty, loading, permission, and error states.
- [x] Account, consent, scan, encrypted sync, report, artifact, sharing, clinician review, analytics, export, and deletion APIs.
- [x] PostgreSQL migrations, Redis queue/outbox, private object storage, worker retries, retention, cancellation, and deletion tombstones.
- [x] Generated clinician PDF, captioned summary video, image-colored observation-map GLB, and recipient-encrypted export.
- [x] Local full-stack flow verified through PostgreSQL, Redis, object storage, platform API, and worker.

## Analysis and model controls

- [x] Stateless analyze, compare, model-card, and health routes with no retained inference jobs.
- [x] Production anatomy validation and candidate segmentation with descriptors, uncertainty, abstention, and signed responses.
- [x] Registration, paired-marker sizing, and gated color normalization.
- [x] Fail-closed adapters and model-card status for research heads that do not have releasable evidence.
- [x] Public source excludes the private academic-competition segmentation weight; the live inference deployment supplies it privately.

## Verification and release

- [x] Unit, integration, schema, migration, security, deletion, model-gate, and repository audits pass.
- [x] Type checking, ESLint, Ruff, Prettier, production web build, mobile exports, and Android release build pass.
- [x] JavaScript and Python dependency audits report no new known high-severity issues.
- [x] Vercel and Compose configuration validate; the local service stack reaches healthy/ready state.
- [x] Public website and production inference health are reachable before the final release push.
- [x] Commit and push the final verified tree to public `main`.
- [x] Verify hosted GitHub Actions for the final public `main` release.
- [x] Deploy and browser-check the final application commit on Vercel at desktop and mobile widths.

The public web project is connected to GitHub for automatic builds. The
inference project deliberately uses a controlled deployment from this checkout
because its hash-verified competition model is private and excluded from Git.

## Separate owner/resource follow-up

- [ ] Supply managed OIDC, PostgreSQL, TLS Redis, private object storage, worker hosting, and production secrets to host the optional account/clinician stack.
- [ ] Supply Apple/Google/Expo signing accounts for store-distributed iOS and Android builds.
- [ ] Run the planned two-iPhone/two-Android physical-device and assistive-technology matrix.
- [ ] Complete the evidence required before enabling closed research or quantitative-change gates.

These owner/resource items are follow-up for store distribution, the optional
hosted account platform, or later clinical research. They do not block the
current Congressional App Challenge build.
