import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getProductContext, productHomeForRole } from "@/lib/product-auth";
import { getCurrentClinicianVerification } from "@/lib/platform-api";
import { readableDate } from "@/lib/presentation";

export const metadata: Metadata = { title: "Verification pending" };

export default async function ClinicianPendingPage() {
  const context = await getProductContext();
  if (context.state !== "ready") return null;
  if (context.account.role !== "clinician_pending") {
    redirect(productHomeForRole(context.account.role));
  }
  const verification = await getCurrentClinicianVerification().catch(
    () => null,
  );
  return (
    <div className="workspace-page verification-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Professional verification</p>
          <h1>Your review workspace is locked.</h1>
          <p>
            OralSight has your professional request, but the platform has not
            marked this account as verified. Patient shares and annotations
            remain unavailable.
          </p>
        </div>
        <span className="account-state" data-state="pending">
          Pending
        </span>
      </header>
      <ol className="verification-path">
        <li data-state="complete">
          <strong>Account created</strong>
          <span>Your secure sign-in is active.</span>
        </li>
        <li data-state="current">
          <strong>Credentials reviewed</strong>
          <span>
            {verification
              ? `Submitted ${readableDate(verification.submittedAt)}. A platform administrator must confirm the professional record.`
              : "Open Verification to submit the professional record."}
          </span>
        </li>
        <li>
          <strong>Workspace opened</strong>
          <span>Only then can shared patient records appear.</span>
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
    </div>
  );
}
