import type { Metadata } from "next";

import { VerificationForm } from "@/components/verification-form";
import { WorkspaceState } from "@/components/workspace-state";
import { getProductContext } from "@/lib/product-auth";
import {
  PlatformApiError,
  getCurrentClinicianVerification,
} from "@/lib/platform-api";
import { readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Professional verification" };

export default async function VerificationPage() {
  const context = await getProductContext();
  if (context.state !== "ready") return null;
  const record = await getCurrentClinicianVerification().then(
    (value) => ({ ok: true as const, value }),
    (error: unknown) => ({ ok: false as const, error }),
  );
  const isAdmin = context.account.role === "admin";
  const verified = record.ok && record.value.status === "verified";
  const notSubmitted =
    !isAdmin &&
    !record.ok &&
    record.error instanceof PlatformApiError &&
    record.error.status === 404;
  return (
    <div className="workspace-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Professional verification</p>
          <h1>
            {isAdmin
              ? "Administrator access is active."
              : verified
                ? "Professional access is active."
                : notSubmitted
                  ? "Request professional access."
                  : "Credential review in progress."}
          </h1>
          <p>
            The platform verification record, not a profile label, controls
            access to patient-authorized reviews.
          </p>
        </div>
        <span
          className="account-state"
          data-state={verified || isAdmin ? "active" : "pending"}
        >
          {isAdmin
            ? "Administrator"
            : record.ok
              ? readableLabel(record.value.status)
              : "Not submitted"}
        </span>
      </header>
      {isAdmin ? (
        <WorkspaceState
          title="Administrator role confirmed."
          body="Administrator access is controlled by the platform role and does not substitute for a clinician verification record."
        />
      ) : record.ok ? (
        <dl className="record-ledger">
          <div>
            <dt>Profession</dt>
            <dd>{record.value.profession}</dd>
          </div>
          <div>
            <dt>Jurisdiction</dt>
            <dd>{record.value.licenseJurisdiction}</dd>
          </div>
          <div>
            <dt>License ending</dt>
            <dd>Ending in {record.value.licenseNumberSuffix}</dd>
          </div>
          <div>
            <dt>Submitted</dt>
            <dd>{readableDate(record.value.submittedAt)}</dd>
          </div>
          <div>
            <dt>Organization</dt>
            <dd>{record.value.organization ?? "Not provided"}</dd>
          </div>
          <div>
            <dt>Decision</dt>
            <dd>
              {record.value.reviewedAt
                ? readableDate(record.value.reviewedAt)
                : "Awaiting review"}
            </dd>
          </div>
        </dl>
      ) : notSubmitted ? (
        <VerificationForm operationKey={crypto.randomUUID()} />
      ) : (
        <WorkspaceState
          title="Verification status could not be loaded."
          body="Professional access remains locked until the service confirms a verified record."
        />
      )}
      {record.ok && record.value.status === "rejected" ? (
        <WorkspaceState
          title="The verification request was not approved."
          body={
            record.value.decisionReason ??
            "Contact the verification administrator for next steps."
          }
        />
      ) : null}
    </div>
  );
}
