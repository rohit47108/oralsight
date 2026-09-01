import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ProductGate } from "@/components/product-gate";
import { VerificationForm } from "@/components/verification-form";
import { WorkspaceState } from "@/components/workspace-state";
import { getProductContext, productHomeForAccount } from "@/lib/product-auth";
import { clinicianApplicationMode } from "@/lib/clinician-application";
import {
  getCurrentClinicianVerification,
  PlatformApiError,
} from "@/lib/platform-api";

export const metadata: Metadata = {
  title: "Professional access application",
  robots: { index: false, follow: false, nocache: true },
};

export default async function ProfessionalApplicationPage() {
  const context = await getProductContext();
  if (context.state !== "ready") {
    return (
      <ProductGate
        context={context}
        returnTo="/professional-apply"
        embeddedInSiteMain
      />
    );
  }
  if (context.account.role !== "patient") {
    redirect(productHomeForAccount(context.account));
  }

  const prior = await getCurrentClinicianVerification().then(
    (value) => ({ state: "loaded" as const, value }),
    (error: unknown) =>
      error instanceof PlatformApiError && error.status === 404
        ? { state: "none" as const }
        : { state: "unavailable" as const },
  );
  const mode = clinicianApplicationMode(
    prior.state === "loaded"
      ? { state: "loaded", status: prior.value.status }
      : prior,
    context.account.clinicianApplicationEligible,
  );

  return (
    <div className="workspace-page professional-application-page page-width">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Professional access</p>
          <h1>Request a clinician workspace.</h1>
          <p>
            An Stoma3D identity administrator must invite the account first.
            Credential review and secure sign-in activation remain separate
            checks.
          </p>
        </div>
        <span className="account-state" data-state="pending">
          Access locked
        </span>
      </header>

      {mode === "unavailable" ? (
        <WorkspaceState
          title="Your verification history could not be checked."
          body="No new request was opened. Try again when the account service is available."
        />
      ) : null}
      {mode === "awaiting_review" && prior.state === "loaded" ? (
        <WorkspaceState
          title="Your credential review is in progress."
          body="A second request cannot be opened while this review is pending. Return here after the administrator records a decision."
        />
      ) : null}
      {mode === "approved" ? (
        <WorkspaceState
          title="Your credentials are approved."
          body="Professional records remain locked until the platform and your fresh sign-in both confirm clinician access. Sign out and back in to refresh your account."
          action={{
            href: "/auth/logout?returnTo=%2Fclinician",
            label: "Refresh secure sign-in",
          }}
        />
      ) : null}
      {mode === "reapply" && prior.state === "loaded" ? (
        <WorkspaceState
          title="A previous request was not approved."
          body={
            prior.value.decisionReason ??
            "Ask the verification administrator whether a new invitation is appropriate."
          }
        />
      ) : null}

      {mode === "invitation_required" ? (
        <section
          className="professional-boundary"
          aria-labelledby="invitation-title"
        >
          <h2 id="invitation-title">An invitation is required first</h2>
          <ol>
            <li>
              Ask the Stoma3D identity administrator for professional access and
              an invitation reference.
            </li>
            <li>
              The administrator assigns the clinician application role (
              <b>clinician_pending</b>) to the account.
            </li>
            <li>Sign out and back in, then return to this page.</li>
          </ol>
          <a
            className="button"
            href="/auth/logout?returnTo=%2Fprofessional-apply"
          >
            Sign out and check invitation
          </a>
        </section>
      ) : mode === "apply" || mode === "reapply" ? (
        <VerificationForm operationKey={crypto.randomUUID()} />
      ) : null}
    </div>
  );
}
