import Link from "next/link";

import type { ProductContext } from "@/lib/product-auth";

export function ProductGate({ context }: { context: ProductContext }) {
  if (context.state === "signed_out") {
    return (
      <main className="product-gate" id="main-content">
        <div className="product-gate__content">
          <p className="workspace-kicker">Private workspace</p>
          <h1>Sign in to your OralSight account.</h1>
          <p>
            Your account keeps web access separate from the images protected on
            your phone.
          </p>
          <a className="button" href="/auth/login?returnTo=%2Fapp">
            Sign in securely
          </a>
          <Link className="text-link" href="/">
            Return to OralSight
          </Link>
        </div>
        <p className="product-gate__disclaimer">
          This result is not a diagnosis.
        </p>
      </main>
    );
  }

  if (context.state === "service_unavailable") {
    return (
      <main className="product-gate" id="main-content">
        <div className="product-gate__content" role="alert">
          <p className="workspace-kicker">Account check unavailable</p>
          <h1>Your records were not opened.</h1>
          <p>{context.error.message}</p>
          <p className="quiet-copy">
            No health information is shown until the account service confirms
            your role and access.
          </p>
          <a className="button" href="/app">
            Try again
          </a>
          <a className="text-link" href="/auth/logout">
            Sign out
          </a>
        </div>
        <p className="product-gate__disclaimer">
          This result is not a diagnosis.
        </p>
      </main>
    );
  }

  return null;
}
