"use client";

export default function WorkspaceError({ reset }: { reset: () => void }) {
  return (
    <section className="workspace-error" role="alert">
      <p className="workspace-kicker">Record unavailable</p>
      <h1>This page could not be verified.</h1>
      <p>Your records were not changed. Check the record ID or try again.</p>
      <button className="button" type="button" onClick={reset}>
        Try again
      </button>
    </section>
  );
}
