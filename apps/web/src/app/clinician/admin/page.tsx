import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { VerificationDecisionForm } from "@/components/verification-decision-form";
import { WorkspaceState } from "@/components/workspace-state";
import { getProductContext, productHomeForAccount } from "@/lib/product-auth";
import { listClinicianVerifications } from "@/lib/platform-api";
import { readableDate } from "@/lib/presentation";

export const metadata: Metadata = { title: "Verification queue" };

export default async function AdminVerificationPage() {
  const context = await getProductContext();
  if (context.state !== "ready") return null;
  if (
    context.account.role !== "admin" ||
    !context.account.privilegedAccessReady
  )
    redirect(productHomeForAccount(context.account));
  const loadQueue = (status: "pending" | "verified") =>
    listClinicianVerifications(status).then(
      (value) => ({ ok: true as const, value }),
      () => ({ ok: false as const }),
    );
  const [queue, verifiedQueue] = await Promise.all([
    loadQueue("pending"),
    loadQueue("verified"),
  ]);
  return (
    <div className="workspace-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Administrator</p>
          <h1>Professional verification queue.</h1>
          <p>
            Each decision requires an evidence source and reference. Approval
            records the credential review. The matching sign-in role is checked
            separately before protected access opens.
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
                  <dt>Identity-provider reference</dt>
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
      <section
        className="settings-section"
        aria-labelledby="role-handoff-title"
      >
        <div>
          <p className="workspace-kicker">Sign-in role handoff</p>
          <h2 id="role-handoff-title">Approved clinician accounts</h2>
          <p>
            Locate the reviewed account using its identity-provider invitation
            reference, assign the required role, and ask the clinician to sign
            out and back in. OralSight records only when that role is later
            observed in a validated token.
          </p>
        </div>
        {!verifiedQueue.ok ? (
          <WorkspaceState
            title="Approved accounts could not be loaded."
            body="No sign-in role state is inferred while the service is unavailable."
          />
        ) : verifiedQueue.value.items.length === 0 ? (
          <WorkspaceState
            title="No approved clinician accounts."
            body="Approved requests will appear here with their required sign-in role."
          />
        ) : (
          <div className="verification-queue">
            {verifiedQueue.value.items.map((item) => (
              <article key={item.verificationId}>
                <header>
                  <div>
                    <p className="workspace-kicker">
                      Approved{" "}
                      {item.reviewedAt
                        ? readableDate(item.reviewedAt)
                        : "date unavailable"}
                    </p>
                    <h2>{item.profession}</h2>
                  </div>
                  <span>
                    {item.identityRole.observationStatus === "observed"
                      ? "Role observed"
                      : "Waiting for role"}
                  </span>
                </header>
                <dl>
                  <div>
                    <dt>Applicant</dt>
                    <dd>{item.applicantUserId}</dd>
                  </div>
                  <div>
                    <dt>Required claim</dt>
                    <dd>{item.identityRole.requiredClaim}</dd>
                  </div>
                  <div>
                    <dt>Required value</dt>
                    <dd>{item.identityRole.requiredValue}</dd>
                  </div>
                  <div>
                    <dt>First observed in a signed token</dt>
                    <dd>
                      {item.identityRole.oidcRoleObservedAt
                        ? readableDate(item.identityRole.oidcRoleObservedAt)
                        : "Not observed yet"}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
