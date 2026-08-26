import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ClinicianActivationForm } from "@/components/clinician-activation-form";
import { WorkspaceState } from "@/components/workspace-state";
import { clinicianPendingMode } from "@/lib/clinician-application";
import { getProductContext, productHomeForAccount } from "@/lib/product-auth";
import {
  getCurrentClinicianVerification,
  PlatformApiError,
} from "@/lib/platform-api";
import { readableDate } from "@/lib/presentation";

export const metadata: Metadata = { title: "Verification pending" };

export default async function ClinicianPendingPage() {
  const context = await getProductContext();
  if (context.state !== "ready") return null;
  if (context.account.role !== "clinician_pending") {
    redirect(productHomeForAccount(context.account));
  }
  const verificationResult = await getCurrentClinicianVerification().then(
    (value) => ({ state: "loaded" as const, value }),
    (error: unknown) =>
      error instanceof PlatformApiError && error.status === 404
        ? { state: "none" as const }
        : { state: "unavailable" as const },
  );
  const verification =
    verificationResult.state === "loaded" ? verificationResult.value : null;
  const mode = clinicianPendingMode(
    verificationResult.state === "loaded"
      ? { state: "loaded", status: verificationResult.value.status }
      : verificationResult,
  );
  const approved = mode === "ready_to_activate";
  return (
    <div className="workspace-page verification-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Professional verification</p>
          <h1>
            {mode === "unavailable"
              ? "Verification status is unavailable."
              : approved
                ? "Your credentials are approved."
                : mode === "missing"
                  ? "No credential request was found."
                  : mode === "rejected"
                    ? "Your credential request was not approved."
                    : "Your credential review is in progress."}
          </h1>
          <p>
            {mode === "unavailable"
              ? "No access decision is shown until the account service confirms the record."
              : approved
                ? "One secure sign-in check remains before patient-authorized records can open."
                : mode === "missing"
                  ? "Submit your professional credentials before access can be reviewed. Patient shares and annotations remain unavailable."
                  : mode === "rejected"
                    ? "Patient shares and annotations remain unavailable. Review the decision before submitting new evidence."
                    : "OralSight has your professional request, but the platform has not marked this account as verified. Patient shares and annotations remain unavailable."}
          </p>
        </div>
        <span className="account-state" data-state="pending">
          {approved
            ? "Sign-in check"
            : mode === "awaiting_review"
              ? "Under review"
              : "Access locked"}
        </span>
      </header>
      {mode === "unavailable" ? (
        <WorkspaceState
          title="Your verification status could not be loaded."
          body="Professional access remains locked. Try again when the account service is available."
        />
      ) : (
        <>
          {mode === "missing" ? (
            <WorkspaceState
              title="Start credential review."
              body="Open Verification to submit your professional record."
              action={{
                href: "/clinician/verification",
                label: "Open Verification",
              }}
            />
          ) : null}
          {mode === "rejected" ? (
            <WorkspaceState
              title="Review the recorded decision."
              body={
                verification?.decisionReason ??
                "Open Verification to review the request and submit new evidence if appropriate."
              }
              action={{
                href: "/clinician/verification",
                label: "Open Verification",
              }}
            />
          ) : null}
          <ol className="verification-path">
            <li data-state="complete">
              <strong>Account created</strong>
              <span>Your secure sign-in is active.</span>
            </li>
            <li data-state={approved ? "complete" : "current"}>
              <strong>Credentials reviewed</strong>
              <span>
                {approved
                  ? "The professional record was approved."
                  : mode === "awaiting_review" && verification
                    ? "Submitted " +
                      readableDate(verification.submittedAt) +
                      ". A platform administrator must confirm the professional record."
                    : mode === "rejected"
                      ? "The last credential review was not approved."
                      : "No credential request is on file."}
              </span>
            </li>
            <li data-state={approved ? "current" : undefined}>
              <strong>Workspace opened</strong>
              <span>
                {approved
                  ? "Assign clinician access in the sign-in provider, sign out and back in, then check access."
                  : "Only then can shared patient records appear."}
              </span>
              {approved ? <ClinicianActivationForm /> : null}
            </li>
          </ol>
          <section className="professional-boundary">
            <h2>What remains protected</h2>
            <ul>
              <li>No patient directory or global record search.</li>
              <li>No access without a valid patient share.</li>
              <li>Every view and annotation is recorded by the platform.</li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
