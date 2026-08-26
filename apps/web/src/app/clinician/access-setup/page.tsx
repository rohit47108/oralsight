import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getProductContext, productHomeForAccount } from "@/lib/product-auth";
import { readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Access setup" };

export default async function PrivilegedAccessSetupPage() {
  const context = await getProductContext();
  if (context.state !== "ready") return null;
  const requiredRole = context.account.requiredOidcRole;
  if (!requiredRole || context.account.privilegedAccessReady) {
    redirect(productHomeForAccount(context.account));
  }

  return (
    <div className="workspace-page verification-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Account access</p>
          <h1>One sign-in step remains.</h1>
          <p>
            Your OralSight platform role is ready. Your sign-in account still
            needs the matching {readableLabel(requiredRole)} access level before
            protected records can open.
          </p>
        </div>
        <span className="account-state" data-state="pending">
          Access locked
        </span>
      </header>
      <ol className="verification-path">
        <li data-state="complete">
          <strong>Platform role recorded</strong>
          <span>OralSight has saved the approved account role.</span>
        </li>
        <li data-state="current">
          <strong>Sign-in access assigned</strong>
          <span>
            Ask the identity administrator to assign the <b>{requiredRole}</b>{" "}
            role in the access-token role claim.
          </span>
        </li>
        <li>
          <strong>Fresh sign-in checked</strong>
          <span>Sign out, then sign back in after the role is assigned.</span>
        </li>
      </ol>
      <section className="professional-boundary">
        <h2>Why the workspace stays locked</h2>
        <p>
          OralSight requires the saved platform role and a freshly verified
          sign-in role. Either one alone is not enough.
        </p>
        <a className="button" href="/auth/logout?returnTo=%2Fsignin">
          Sign out and check again
        </a>
      </section>
    </div>
  );
}
