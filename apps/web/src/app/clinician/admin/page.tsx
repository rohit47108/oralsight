import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { VerificationDecisionForm } from "@/components/verification-decision-form";
import { WorkspaceState } from "@/components/workspace-state";
import { getProductContext, productHomeForRole } from "@/lib/product-auth";
import { listClinicianVerifications } from "@/lib/platform-api";
import { readableDate } from "@/lib/presentation";

export const metadata: Metadata = { title: "Verification queue" };

export default async function AdminVerificationPage() {
  const context = await getProductContext();
  if (context.state !== "ready") return null;
  if (context.account.role !== "admin")
    redirect(productHomeForRole(context.account.role));
  const queue = await listClinicianVerifications().then(
    (value) => ({ ok: true as const, value }),
    () => ({ ok: false as const }),
  );
  return (
    <div className="workspace-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Administrator</p>
          <h1>Professional verification queue.</h1>
          <p>
            Each decision requires an evidence source and reference. Approval
            changes platform access; it does not establish clinical validation.
          </p>
        </div>
        <span className="account-state" data-state="active">
          Administrator
        </span>
      </header>
      {!queue.ok ? (
        <WorkspaceState
          title="Verification requests could not be loaded."
          body="No account role changes are made when the queue is unavailable."
        />
      ) : queue.value.items.length === 0 ? (
        <WorkspaceState
          title="No pending verification requests."
          body="New credential submissions will appear here for evidence-backed review."
        />
      ) : (
        <div className="verification-queue">
          {queue.value.items.map((item) => (
            <article key={item.verificationId}>
              <header>
                <div>
                  <p className="workspace-kicker">
                    Submitted {readableDate(item.submittedAt)}
                  </p>
                  <h2>{item.profession}</h2>
                </div>
                <span>
                  {item.licenseJurisdiction}, ending in{" "}
                  {item.licenseNumberSuffix}
                </span>
              </header>
              <dl>
                <div>
                  <dt>Applicant</dt>
                  <dd>{item.applicantUserId}</dd>
                </div>
                <div>
                  <dt>Organization</dt>
                  <dd>{item.organization ?? "Not provided"}</dd>
                </div>
                <div>
                  <dt>Evidence reference</dt>
                  <dd>{item.applicantEvidenceRef}</dd>
                </div>
              </dl>
              <VerificationDecisionForm
                verificationId={item.verificationId}
                operationKey={crypto.randomUUID()}
              />
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
