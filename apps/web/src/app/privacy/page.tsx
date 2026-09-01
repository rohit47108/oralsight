import type { Metadata } from "next";
import Link from "next/link";

import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = {
  title: "Privacy",
  description:
    "Understand what Stoma3D stores, what leaves your phone, optional sync, sharing, retention, and deletion.",
};

export default function PrivacyPage() {
  return (
    <>
      <PageIntro
        label="Privacy"
        title="Your record follows your choices."
        description="Local use, optional sync, and sharing are separate decisions. Stoma3D does not require you to make your observations public."
      />

      <section
        className="principle-row page-width"
        aria-label="Privacy principles"
      >
        <div>
          <span>01</span>
          <h2>Local first</h2>
          <p>
            Guest mode can keep sessions, images, results, and PDFs on your
            device.
          </p>
        </div>
        <div>
          <span>02</span>
          <h2>Sync is optional</h2>
          <p>
            Signing in and syncing is a separate choice, not a requirement to
            scan.
          </p>
        </div>
        <div>
          <span>03</span>
          <h2>Sharing expires</h2>
          <p>
            You choose what a link contains and can revoke it before its end
            time.
          </p>
        </div>
      </section>

      <section className="detail-band" aria-labelledby="image-path-heading">
        <div className="page-width detail-split">
          <div>
            <p className="section-label">Image path</p>
            <h2 id="image-path-heading">A rejected image goes no further.</h2>
          </div>
          <div className="long-copy">
            <p>
              The app checks framing, quality, faces, and the selected mouth
              region before accepting a capture. If it fails, the image is not
              saved and is not uploaded.
            </p>
            <p>
              For accepted captures, the app removes image metadata and prepares
              a sanitized copy for analysis. The protected local original stays
              separate from that copy.
            </p>
          </div>
        </div>
      </section>

      <section
        className="page-width data-choice"
        aria-labelledby="choices-heading"
      >
        <div className="data-choice__heading">
          <p className="section-label">Your choices</p>
          <h2 id="choices-heading">What changes when you sign in.</h2>
        </div>
        <div
          className="comparison-table"
          role="table"
          aria-label="Guest and signed-in privacy choices"
        >
          <div className="comparison-table__header" role="row">
            <span role="columnheader">Choice</span>
            <span role="columnheader">Guest mode</span>
            <span role="columnheader">Signed-in sync</span>
          </div>
          {[
            [
              "Where records live",
              "On this device",
              "This device and your protected account",
            ],
            ["Works without an account", "Yes", "No"],
            ["Move between devices", "No", "Yes, for selected synced records"],
            [
              "Create an expiring link",
              "From an exported local report",
              "From records you select",
            ],
          ].map((row) => (
            <div className="comparison-table__row" role="row" key={row[0]}>
              {row.map((cell, index) => (
                <span role={index === 0 ? "rowheader" : "cell"} key={cell}>
                  {cell}
                </span>
              ))}
            </div>
          ))}
        </div>
      </section>

      <section
        className="detail-band detail-band--dark"
        aria-labelledby="retention-heading"
      >
        <div className="page-width detail-split">
          <div>
            <p className="section-label">Retention and deletion</p>
            <h2 id="retention-heading">Delete means more than hiding a row.</h2>
          </div>
          <div className="long-copy">
            <p>
              Delete all removes local database rows, images, cached analysis,
              generated reports, and share material, then rotates the
              installation encryption key. A signed-in deletion request also
              tracks cloud cleanup to completion.
            </p>
            <p>
              Short-lived processing input and expired shares are removed on
              fixed schedules. Encrypted exports are kept for 7 days; opted-in
              product analytics and successful job payloads for 30 days; failed
              job payloads and deletion polling receipts for 7 days; share
              records for 90 days after expiry; and rendered reports and
              generated map/video files for up to 365 days. Clinician, access,
              and audit records can be kept for up to 7 years unless delete-all
              applies. Capture files follow the expiry you select or delete-all.
              Encrypted disaster-recovery backups age out within 35 days and
              completed deletions are not restored from backup.
            </p>
            <Link className="arrow-link arrow-link--light" href="/security">
              See the security controls <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
      </section>

      <section className="page-width readable-section">
        <h2>Analytics is limited by design.</h2>
        <p>
          Analytics is opt-in and uses a small event list. It does not collect
          mouth images, symptoms, observation text, model output, capture
          identifiers, or replay recordings. Events are linked to the account
          for consent and deletion, retained for 30 days, and exposed to admins
          only as grouped counts once at least five matching events exist. The
          product must still work when analytics is off.
        </p>
      </section>
    </>
  );
}
