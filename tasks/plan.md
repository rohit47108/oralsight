# Implementation Plan: OralSight Competition Completion

## Objective

Finish OralSight directly in `C:\Users\rohit\Projects\oralsight` as the permanent
source of truth, publish a coherent public GitHub repository, deploy and verify the
web product on Vercel, and keep the mobile, inference, platform, and worker paths
runnable from the same monorepo.

## Current baseline

- The completed local source history and the public GitHub history were merged into
  this repository on 2026-08-26.
- The eight-region mobile workflow, web workspaces, inference API, platform API,
  worker, contracts, deployment files, and tests already exist.
- The remaining work is public-distribution cleanup, fresh verification, product
  polish, live deployment, and end-to-end acceptance.

## Architecture decisions

- This directory and its `main` branch are the only active source tree.
- Vercel hosts the Next.js web application. The platform API and continuous worker
  remain container services; the stateless inference service may use Vercel or a
  container host depending on model size and runtime limits.
- The public repository will use an MIT source license and will not redistribute
  the Autooral-assisted segmentation weight. Deployments receive model artifacts
  through an explicit external artifact path or private model store.
- The normal product never substitutes a fixture result for a real capture.

## Phases

### 1. Repository recovery and public-source cleanup

- [x] Inspect the empty checkout, Git history, remote, older source, and Vercel link.
- [x] Merge the strongest local and remote histories into the permanent repository.
- [x] Add the repository license and public-distribution policy.
- [x] Remove the restricted segmentation weight from the public tree and configure
      an explicit external artifact path with fail-clear runtime behavior.
- [x] Update inventories, model cards, repository audits, and deployment examples.
- [ ] Remove the restricted blob from the public branch history before the next push.

### 2. Fresh source verification

- [x] Install from committed locks in the permanent repository.
- [x] Run contracts, TypeScript tests, type checks, formatting, and dependency audit.
- [x] Run inference, platform, worker, and ML tests plus Ruff checks.
- [x] Build the Next.js web product and export Android/iOS JavaScript bundles.
- [x] Run repository, model-hash, fixture-isolation, and secret scans.

### 3. Competition product polish

- [ ] Audit every public and signed-in web route for dead navigation, empty/error/
      loading states, responsive layout, accessibility, and plain product copy.
- [ ] Audit the principal mobile flow for scan recovery, permissions, touch targets,
      safe areas, reduced motion, large text, and clear accepted/rejected states.
- [ ] Verify the fast competition path from consent to a complete report.
- [x] Remove stale packaging and unrelated roadmap language.

### 4. Deployment and end-to-end verification

- [ ] Verify GitHub repository visibility, default branch, remote SHA, and Actions.
- [ ] Verify the Vercel project, root/build settings, environment contract, and domain.
- [ ] Deploy a preview, inspect build/runtime logs, and test public routes in a browser.
- [ ] Configure or precisely identify the remaining identity, database, Redis, object
      storage, worker-host, signing, and mobile-build credentials.
- [ ] Promote only a verified deployment and record the exact public URLs.

### 5. Final acceptance

- [ ] Run the complete main-journey acceptance suite against the final tree.
- [ ] Review code for correctness, security, accessibility, performance, and clarity.
- [ ] Update `docs/FINAL_VERIFICATION.md` with fresh evidence only.
- [ ] Confirm a clean working tree and matching local/remote commit.

## Risks and responses

| Risk                                               | Response                                                                                                                        |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Restricted model already exists in public history  | Remove it from the current tree, replace runtime loading with a private artifact path, and publish a cleaned branch history.    |
| Hosted services are not provisioned                | Finish all source and local verification, then request only the exact account or credential that blocks the next live boundary. |
| Web deployment builds but authenticated flows fail | Verify browser to API to storage boundaries before promotion.                                                                   |
| Existing release notes overstate old evidence      | Replace stale claims with fresh command and runtime evidence from this repository.                                              |
