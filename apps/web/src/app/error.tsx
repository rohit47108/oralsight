"use client";

import Link from "next/link";

export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <section className="state-page page-width" role="alert">
      <p className="section-label">Page error</p>
      <h1>This page did not load.</h1>
      <p>Your records were not changed. Try the page again or return home.</p>
      <div className="state-page__actions">
        <button className="button" type="button" onClick={reset}>
          Try again
        </button>
        <Link className="arrow-link" href="/">
          Return home <span aria-hidden="true">→</span>
        </Link>
      </div>
    </section>
  );
}
