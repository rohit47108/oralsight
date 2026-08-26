# OralSight Release Closure

## Task 1: Upload completion barrier

**Description:** Finish and verify the server-side quiescence rule for already-issued direct upload URLs.

**Acceptance criteria:**

- [x] Deletion waits through capability expiry plus the protected maximum upload duration.
- [x] A write that materializes during that interval is removed before completion.
- [x] Production configuration cannot disable or understate the interval.

**Verification:**

- [x] Focused platform config, migration, and deletion tests pass.

**Dependencies:** None

## Task 2: Durable deletion tombstone

**Description:** Keep account-recreation prevention separate from the short polling receipt.

**Acceptance criteria:**

- [x] Receipt retention can expire without removing the keyed subject tombstone.
- [x] `/v2/me` cannot provision the same subject while its durable tombstone exists.
- [x] No raw OIDC subject is stored or returned by the tombstone path.

**Verification:**

- [x] Focused platform deletion and retention tests pass.

**Dependencies:** Task 1

## Task 3: Mobile tombstone handling

**Description:** Treat a server tombstone as terminal for the local cloud session.

**Acceptance criteria:**

- [x] The app clears tokens, sync keys, installation identity, and cloud metadata.
- [x] Normal bootstrap, background sync, and analytics remain disabled.
- [x] Restart regression tests cover a missing local receipt and an expired server polling receipt.

**Verification:**

- [x] Focused mobile deletion tests and mobile typecheck pass.

**Dependencies:** Task 2

## Task 4: Generated artifacts

**Description:** Regenerate all checked contracts, OpenAPI, third-party notices, SBOM, and repository checksums.

**Acceptance criteria:**

- [x] Generation is deterministic and a second check produces no diff.
- [x] Checked artifacts match the current source.

**Verification:**

- [x] Contract, OpenAPI, license, and repository audit commands pass.

**Dependencies:** Task 3

## Task 5: Full release verification

**Description:** Run the complete source, build, bundle, security, and packaging checks on the exact final tree.

**Acceptance criteria:**

- [x] TypeScript and Python tests, type checks, lint, formatting, and web build pass.
- [ ] Dependency, workflow, Vercel, Compose, and repository audits pass.
- [ ] Unsupported Docker, physical-device, OIDC, and cloud checks remain explicitly external.

**Verification:**

- [x] Evidence is recorded in `docs/FINAL_VERIFICATION.md`.

**Dependencies:** Task 4

## Task 6: Final documentation

**Description:** Make release documentation match the exact verified tree and remove assistant-like or inflated claims.

**Acceptance criteria:**

- [ ] Counts, hashes, dates, and limitations are current.
- [ ] Product wording is natural, concise, non-diagnostic, and consistent across entry-point docs.

**Verification:**

- [ ] Writing review, link check, formatting, and diff check pass.

**Dependencies:** Task 5

## Task 7: Code and UI review

**Description:** Perform a final correctness, security, accessibility, visual, and maintainability review.

**Acceptance criteria:**

- [ ] No critical or required review finding remains unresolved.
- [ ] Browser checks cover the principal public and signed-in shells at representative widths.

**Verification:**

- [ ] Review findings and rendered evidence are recorded.

**Dependencies:** Task 6

## Task 8: Commits and source ZIP

**Description:** Create coherent commits and a verified, secret-free source archive.

**Acceptance criteria:**

- [ ] Commit messages describe real changes and the branch is clean.
- [ ] ZIP excludes secrets, local work, build outputs, caches, and Git metadata.
- [ ] SHA-256 checksum and archive inventory verification pass.

**Verification:**

- [ ] Git status, archive audit, and checksum comparison pass.

**Dependencies:** Task 7

## Task 9: GitHub publishing

**Description:** Push the verified branch to `rohit47108/oralsight` under safe visibility and licensing conditions.

**Acceptance criteria:**

- [ ] Remote visibility does not expose restricted weights.
- [ ] Remote branch SHA matches the local verified commit.
- [ ] GitHub Actions results are inspected.

**Verification:**

- [ ] Remote API and Actions evidence confirm the push.

**Dependencies:** Task 8

## Task 10: Preview deployment

**Description:** Deploy and verify the web and inference preview, with the stateful platform deployed separately.

**Acceptance criteria:**

- [ ] Required production-grade environment values exist and no placeholder is accepted.
- [ ] Browser-to-API-to-storage flows work with real consenting test accounts.
- [ ] Only a verified preview is promoted.

**Verification:**

- [ ] Deployment status, logs, routes, and end-to-end smoke evidence are recorded.

**Dependencies:** Task 9
