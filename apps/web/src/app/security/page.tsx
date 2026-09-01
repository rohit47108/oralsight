import type { Metadata } from "next";

import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = {
  title: "Security",
  description:
    "Review Stoma3D security controls for local records, requests, accounts, sharing, logs, and deletion.",
};

export default function SecurityPage() {
  return (
    <>
      <PageIntro
        label="Security"
        title="Protection is a set of checks, not a badge."
        description="Stoma3D separates local storage, analysis, accounts, and sharing so each part can fail safely and be tested on its own."
      />

      <section
        className="security-ledger page-width"
        aria-label="Security controls"
      >
        {[
          [
            "On the device",
            "Local records use a SQLCipher-backed database. Images and reports are stored as protected files, and keys are kept in the device secure store.",
          ],
          [
            "Before analysis",
            "Accepted images are re-encoded and stripped of metadata. The service refuses request-body logging and returns no-store cache instructions.",
          ],
          [
            "On the service",
            "Image processing uses memory or short-lived temporary files. Cleanup runs even after an error. Stored cloud records use managed access controls and encryption at rest.",
          ],
          [
            "For accounts",
            "Sign-in uses standard authorization-code flow with PKCE. Roles and record ownership are checked by the platform API; health data is not placed in identity-provider profile fields.",
          ],
          [
            "For shared reports",
            "Share secrets are not stored in plain text. Links are view-only, time-limited, revocable, and scoped to the report the user selected.",
          ],
          [
            "For deletion",
            "Deletion removes records and blobs, clears reports and shares, rotates the local installation key, and exposes cloud deletion status rather than claiming instant completion.",
          ],
        ].map(([title, body], index) => (
          <article key={title}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <h2>{title}</h2>
            <p>{body}</p>
          </article>
        ))}
      </section>

      <section
        className="detail-band detail-band--amber"
        aria-labelledby="not-claim-heading"
      >
        <div className="page-width detail-split">
          <div>
            <p className="section-label">Plain limits</p>
            <h2 id="not-claim-heading">What these controls do not prove.</h2>
          </div>
          <div className="long-copy">
            <p>
              Security controls do not by themselves establish HIPAA compliance,
              clinical approval, or freedom from risk. Stoma3D does not describe
              optional cloud sync as end-to-end encrypted.
            </p>
            <p>
              Production releases still require dependency review, threat
              modeling, device testing, deployment hardening, backup and restore
              tests, access review, and an incident-response owner.
            </p>
          </div>
        </div>
      </section>

      <section className="page-width readable-section">
        <h2>Report a security concern</h2>
        <p>
          A production contact and disclosure policy must be published with the
          deployed service. Until then, do not send private health images
          through a public issue tracker or source-code repository.
        </p>
      </section>
    </>
  );
}
