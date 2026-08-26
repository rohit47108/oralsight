# Repository Guidelines

## Project Structure

OralSight is a pnpm/uv monorepo. The mobile client is in `apps/mobile` and the
Next.js web product is in `apps/web`. Shared TypeScript contracts live in
`packages/contracts`. Python services are split into `services/inference`
(stateless image analysis), `services/platform-api` (accounts, storage, sync,
sharing, and jobs), and `services/worker` (durable report and artifact work).
Training and evaluation code is under `ml`; the versioned observation-map
metadata is under `assets/mouth`; deployment files are in `deploy`; and product,
safety, release, and licensing documentation is in `docs`.

## Build, Test, and Development Commands

From the repository root:

```powershell
corepack enable
pnpm install --frozen-lockfile
pnpm test                         # all JavaScript workspace tests
pnpm typecheck                    # all TypeScript checks
pnpm format:check                # Prettier verification
py -3.12 -m uv sync --frozen --all-packages --extra dev
py -3.12 -m uv run --frozen --all-packages pytest services/inference/tests services/platform-api/tests services/worker/tests ml/tests
```

Use `pnpm dev:mobile` for the Expo development build. Service-specific setup
and required environment variables are documented in `README.md` and
`docs/DEPLOYMENT.md`. Regenerate shared schemas with `pnpm contracts:generate`.

## Coding Style and Naming

Use two-space indentation for TypeScript, four spaces for Python, and let
Prettier and Ruff enforce formatting. TypeScript components and types use
PascalCase; variables and functions use camelCase. Python modules and
functions use `snake_case`, classes use PascalCase, and API fields remain
camelCase through the shared contract aliases. Keep public interfaces typed and
validate untrusted request and service responses at boundaries.

## Testing Guidelines

Add a focused test before changing behavior. Vitest covers TypeScript; pytest
covers Python services and ML tooling. Name tests after observable behavior,
for example `test_recreation_requires_explicit_confirmation`. Run the focused
test while developing, then the full commands above before committing.

## Security and Configuration

Never commit secrets, restricted medical images, patient data, databases, or
generated local builds. Use `.env.local` or deployment secret stores. Preserve
the non-diagnostic safety gates, signed response checks, encryption, deletion
behavior, and no-store response headers when modifying APIs.

## Commits and Pull Requests

Use short imperative commit subjects, such as `Add durable deletion tombstones`
or `Refine observation map controls`. Keep commits focused. Pull requests
should explain the user-visible change, list tests run, call out migrations or
configuration changes, and include screenshots for UI changes. Do not claim
clinical validity, diagnosis, or production readiness without the evidence
required by the release documentation.
