# OralSight web

Next.js App Router site for the public OralSight pages plus authenticated patient,
shared-viewer, `clinician_pending`, clinician, and administrator workspaces.

## Local use

```powershell
pnpm --filter @oralsight/web dev
pnpm --filter @oralsight/web verify
```

Set `NEXT_PUBLIC_SITE_URL` to the public HTTPS origin before a production build.
If omitted, metadata, robots, and sitemap use `https://oralsight.org`.

Copy `.env.example` to `.env.local`. Create an Auth0 **Regular Web Application**
and register:

- callback: `http://localhost:3000/auth/callback`
- logout: `http://localhost:3000`
- web origin: `http://localhost:3000`

Create an Auth0 API whose identifier matches `AUTH0_AUDIENCE`, then configure the
platform API with the same audience and Auth0 issuer/JWKS URL. The SDK uses the
authorization-code flow with PKCE and encrypted, HTTP-only session cookies. API
access tokens remain on the server; the browser access-token endpoint is disabled.

`ORALSIGHT_PLATFORM_API_URL` must point to `services/platform-api`; the supplied
local Compose stack publishes it at `http://127.0.0.1:8001`. Outside local
development it must use HTTPS.

Production builds fail before compilation when any Auth0, site-origin, audience,
or platform-API value is missing or still looks like a placeholder. GitHub CI
uses `ORALSIGHT_ALLOW_CI_DUMMY_WEB_ENV=true` with explicit dummy values so it can
exercise the optimized build without production credentials. That bypass works
only when `CI=true` and is deliberately ignored when `VERCEL=1`; never configure
it in a deployment project.

## Service boundary

The web app uses the live `/v2` account, scan, capture-set, report, job,
generated-artifact, access-grant, sharing, access-history, clinician-verification,
clinician-review, annotation, review-status, analytics-consent, and account-deletion
routes. Patient pages list the signed-in user's real records and stream authorized
PDF, MP4, GLB, and capture content through same-origin server routes. Empty service
responses stay empty; the interface never inserts sample health records.

The GLB viewer preserves the standard oral-map geometry and displays the worker's
coarse projected region colors when a validated `COLOR_0` stream is present.
Administrators can review only privacy-thresholded, opt-in product-use totals;
groups smaller than five are never returned or estimated by the web app.

Share secrets remain in the URL fragment until a same-origin POST exchanges them
for a short-lived, HTTP-only share cookie. QR codes are rendered in the browser and
never sent to a third-party image service. Shared and clinician report files use
their separate, authorization-checked platform routes.

The public `/calibration` route provides tested A4 and US Letter PDFs for the
`oralsight-calibration-v1` card: ArUco `DICT_4X4_50`, marker ID 17, an exact 20 mm
marker, a 50 mm reference line, grayscale patches, and the versioned QR payload.
The browser print view preserves the same physical dimensions. Printing alone
does not make a measurement valid; millimeter values appear only when the related
analysis contains a valid calibration result, and they are still approximate.

Analytics are off until the account owner opts in and saves the setting. Account
deletion uses the platform deletion job and reports its live status. Professional
workspaces require a verified platform clinician record and the exact configured
access-token role; an Auth0 profile field or generic `roles` claim cannot grant
access by itself.

New applicants begin at `/professional-apply`. The identity administrator first
assigns `clinician_pending` and supplies a searchable invitation reference. The
applicant signs in again and submits credentials. Approval still leaves the
workspace locked until the identity administrator replaces that role with
`clinician`, the applicant signs in again, and **Check secure access** observes
the fresh signed role. Removing a provider role is effective on refresh and no
later than the configured privileged-token maximum age plus clock leeway.

The platform reads only `ORALSIGHT_PLATFORM_OIDC_ROLE_CLAIM` from the signed API
access token. It does not accept a generic `roles` claim as a fallback. Keep the
provider's access-token lifetime and refresh policy within the configured
privileged-token age limit.

The first administrator and recovery-administrator operator commands are
documented in [the deployment guide](../../docs/DEPLOYMENT.md#bootstrap-the-first-administrator).
The same guide documents the
[clinician approval path](../../docs/DEPLOYMENT.md#complete-a-clinician-approval).

## Vercel

Use the repository root as the Vercel project root and select `apps/web` as the
application directory, or point a standalone Vercel project directly at this
folder. Build with `pnpm build` and serve the `.next` output. Set
`NEXT_PUBLIC_SITE_URL` to the stable HTTPS web origin; it is used only for public
metadata, robots, and the sitemap.

Set Auth0 and platform variables in every Vercel environment. Register each stable
production and preview callback/logout URL with Auth0 before testing sign-in. The
stateful platform API and its workers are deployed separately; the web project
must be able to reach their HTTPS API origin.
