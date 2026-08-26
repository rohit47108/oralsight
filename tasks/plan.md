# Implementation Plan: OralSight Release Closure

## Overview

Finish the approved OralSight product work on the `main` branch. This plan covers the remaining release-critical gaps and handoff work; the original OralSight blueprint and `docs/REQUIREMENT_AUDIT.md` remain the product scope.

## Architecture Decisions

- A completed cloud deletion leaves a durable, keyed server tombstone. The short-lived receipt used for status polling is separate from the long-lived protection against silent account recreation.
- Direct object-storage uploads are considered live until their signed capability expires and the configured maximum upload-completion interval has also elapsed. Deletion completes only after a final rescan, delete, and absence check.
- Learned medical outputs remain disabled unless their fixed release gates pass. Shipping source code never substitutes fixture output for an arbitrary live capture.
- Vercel hosts the web application and stateless inference service. PostgreSQL, Redis, object storage, and the continuous worker require the documented container platform.

## Task List

### Phase 1: Deletion safety

- [ ] Task 1: Prove upload-capability quiescence through the completion interval.
- [ ] Task 2: Separate the polling receipt from the durable account-deletion tombstone.
- [ ] Task 3: Make mobile abandon cloud credentials and sync state on a tombstone response.

### Checkpoint: Deletion safety

- [ ] Focused platform and mobile regression tests pass.
- [ ] Migration upgrade and downgrade behavior is covered.
- [ ] A deleted subject cannot be silently reprovisioned after receipt expiry.

### Phase 2: Release evidence

- [ ] Task 4: Regenerate contracts, OpenAPI, legal notices, and checksums.
- [ ] Task 5: Run the complete TypeScript, Python, web, mobile-bundle, security, and repository gates.
- [ ] Task 6: Reconcile final verification and implementation-status documents with current evidence.

### Checkpoint: Release evidence

- [ ] Every claimed pass has fresh command output from the exact tree.
- [ ] External or hardware-only evidence is plainly identified as pending.

### Phase 3: Handoff and publishing

- [ ] Task 7: Review changed code and prose for readability, accessibility, safety, and human-maintained style.
- [ ] Task 8: Commit coherent changes with normal, specific commit messages and create a verified source ZIP.
- [ ] Task 9: Publish to the intended GitHub repository only when repository visibility and model redistribution are safe.
- [ ] Task 10: Configure and verify preview deployments only when the required Auth0, platform, signing, and storage settings exist.

### Checkpoint: Complete

- [ ] Source ZIP hash and contents are verified.
- [ ] GitHub branch and remote commit are verified after push.
- [ ] Deployed URLs are verified end to end, or the exact owner-provided setup still required is listed without claiming deployment.

## Risks and Mitigations

| Risk                                             | Impact                                       | Mitigation                                                                                                                |
| ------------------------------------------------ | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| A direct upload finishes after URL expiry        | Deleted medical bytes could reappear         | Enforce a maximum upload duration at ingress, wait that duration beyond capability expiry, then rescan and verify absence |
| A deleted OIDC subject is reprovisioned later    | Old local data could sync into a new account | Keep a keyed durable tombstone and require explicit, separately designed account recreation                               |
| Public source publishes restricted model weights | License breach                               | Keep the repository private or omit the weight until written redistribution rights exist                                  |
| Build success is mistaken for a live product     | Broken auth/cloud paths in production        | Require real environment values and preview end-to-end verification before promotion                                      |

## Rulings

- Ruling: Preserve the non-diagnostic, gate-closed product contract because the supplied blueprint makes it part of the product, and current evaluation evidence does not justify diagnostic claims. Cost if wrong: potentially less aggressive marketing; benefit: no fabricated clinical performance.
- Ruling: Do not push the restricted model weight to a public repository without written redistribution permission. Cost if wrong: publishing waits for a visibility/license decision; benefit: avoids an irreversible public disclosure.
