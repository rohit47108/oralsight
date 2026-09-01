"use client";

export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <html lang="en">
      <body>
        <main className="state-page page-width" role="alert">
          <p className="section-label">Site error</p>
          <h1>Stoma3D could not open this page.</h1>
          <p>No record was changed. Try loading the site again.</p>
          <button className="button" type="button" onClick={reset}>
            Try again
          </button>
        </main>
        <footer className="disclaimer-band">
          <div className="page-width disclaimer-band__inner">
            <strong>This result is not a diagnosis.</strong>
          </div>
        </footer>
      </body>
    </html>
  );
}
