import Link from "next/link";

import type { ProductContext } from "@/lib/product-auth";
import { hostedWorkspaceEnabled } from "@/lib/production-env";

export function ProductGate({
  context,
  returnTo = "/app",
  embeddedInSiteMain = false,
}: {
  context: ProductContext;
  returnTo?: string;
  embeddedInSiteMain?: boolean;
}) {
  const Root = embeddedInSiteMain ? "div" : "main";
  const mainContentId = embeddedInSiteMain ? undefined : "main-content";

  if (context.state === "signed_out") {
    const workspaceEnabled = hostedWorkspaceEnabled();
    return (
      <Root className="product-gate" id={mainContentId}>
        <div className="product-gate__content">
          <p className="workspace-kicker">Private workspace</p>
          <h1>
            {workspaceEnabled
              ? "Sign in to your Stoma3D account."
              : "Continue with the Stoma3D mobile app."}
          </h1>
          <p>
            {workspaceEnabled
              ? "Your account keeps web access separate from the images protected on your phone."
              : "The mobile app runs the guided scan, stores protected captures, and creates your observation report."}
          </p>
          {workspaceEnabled ? (
            <a
              className="button"
              href={"/auth/login?returnTo=" + encodeURIComponent(returnTo)}
            >
              Sign in securely
            </a>
          ) : (
            <Link className="button" href="/how-it-works#start">
              Explore the scan flow
            </Link>
          )}
          <Link className="text-link" href="/">
            Return to Stoma3D
          </Link>
        </div>
        <p className="product-gate__disclaimer">
          This result is not a diagnosis.
        </p>
      </Root>
    );
  }

  if (context.state === "service_unavailable") {
    return (
      <Root className="product-gate" id={mainContentId}>
        <div className="product-gate__content" role="alert">
          <p className="workspace-kicker">Account check unavailable</p>
          <h1>Your records were not opened.</h1>
          <p>{context.error.message}</p>
          <p className="quiet-copy">
            No health information is shown until the account service confirms
            your role and access.
          </p>
          <a className="button" href={returnTo}>
            Try again
          </a>
          <a className="text-link" href="/auth/logout">
            Sign out
          </a>
        </div>
        <p className="product-gate__disclaimer">
          This result is not a diagnosis.
        </p>
      </Root>
    );
  }

  return null;
}
