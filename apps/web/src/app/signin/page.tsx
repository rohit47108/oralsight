import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { BrandMark } from "@/components/brand-mark";
import { getProductContext, productHomeForAccount } from "@/lib/product-auth";
import { hostedWorkspaceEnabled } from "@/lib/production-env";

export const metadata: Metadata = { title: "Sign in" };

export default async function SignInPage() {
  const workspaceEnabled = hostedWorkspaceEnabled();
  if (!workspaceEnabled) {
    return (
      <main className="signin-stage" id="main-content">
        <section className="signin-sheet" aria-labelledby="signin-title">
          <BrandMark />
          <div>
            <p className="workspace-kicker">OralSight mobile</p>
            <h1 id="signin-title">The complete scan starts on your phone.</h1>
            <p>
              Use the mobile app for guided capture, image checks, observation
              mapping, comparison, and report creation. This site explains the
              same product flow used in the competition build.
            </p>
          </div>
          <Link className="button" href="/how-it-works#start">
            Explore the scan flow
          </Link>
          <Link className="text-link" href="/">
            Back to OralSight
          </Link>
        </section>
        <aside className="signin-context" aria-label="What OralSight includes">
          <p className="workspace-kicker">Inside the app</p>
          <dl>
            <div>
              <dt>Eight-region scan</dt>
              <dd>Capture the same complete set of mouth views each time.</dd>
            </div>
            <div>
              <dt>Observation timeline</dt>
              <dd>
                Review confirmed areas and comparisons by date and region.
              </dd>
            </div>
            <div>
              <dt>Portable report</dt>
              <dd>Create a local PDF or a controlled share when configured.</dd>
            </div>
          </dl>
          <strong>This result is not a diagnosis.</strong>
        </aside>
      </main>
    );
  }
  const context = await getProductContext();
  if (context.state === "ready")
    redirect(productHomeForAccount(context.account));
  if (context.state === "service_unavailable") redirect("/app");

  return (
    <main className="signin-stage" id="main-content">
      <section className="signin-sheet" aria-labelledby="signin-title">
        <BrandMark />
        <div>
          <p className="workspace-kicker">Private workspace</p>
          <h1 id="signin-title">Your observations, under your control.</h1>
          <p>
            Sign in to open synced records, reports, or a clinical review
            workspace. Capture still happens in the OralSight mobile app.
          </p>
        </div>
        <a className="button" href="/auth/login?returnTo=%2Fapp">
          Continue to secure sign in
        </a>
        <p className="signin-sheet__note">
          OralSight uses an encrypted session cookie. Health images and results
          are not stored in your sign-in profile.
        </p>
        <Link className="text-link" href="/">
          Back to OralSight
        </Link>
      </section>
      <aside className="signin-context" aria-label="What this account opens">
        <p className="workspace-kicker">After sign in</p>
        <dl>
          <div>
            <dt>Patients</dt>
            <dd>Open scans and reports that belong to your account.</dd>
          </div>
          <div>
            <dt>Clinicians</dt>
            <dd>Review only records a patient has shared with you.</dd>
          </div>
          <div>
            <dt>Shared viewers</dt>
            <dd>Open only the time-limited record named by a share link.</dd>
          </div>
        </dl>
        <strong>This result is not a diagnosis.</strong>
      </aside>
    </main>
  );
}
