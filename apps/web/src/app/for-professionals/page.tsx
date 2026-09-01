import type { Metadata } from "next";
import Link from "next/link";

import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = {
  title: "For professionals",
  description:
    "See how Stoma3D structures user-captured observations, provenance, comparisons, limitations, and reports for professional review.",
};

export default function ProfessionalsPage() {
  return (
    <>
      <PageIntro
        label="For professionals"
        title="A cleaner record for the conversation in front of you."
        description="Stoma3D organizes patient-captured observations into a consistent record that is faster to review alongside an examination."
      />

      <section
        className="professional-flow page-width"
        aria-label="Professional review workflow"
      >
        <div className="professional-flow__lead">
          <p className="section-label">The shared view</p>
          <h2>Start with provenance, not a conclusion.</h2>
          <p>
            Each capture remains tied to its named region, date, quality result,
            input origin, analysis origin, model versions, and any reason the
            model abstained.
          </p>
        </div>
        <ol>
          <li>
            <span>01</span>
            <div>
              <h3>Confirm the record</h3>
              <p>
                Check who captured it, which region was selected, and whether
                the session is complete.
              </p>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              <h3>Read the image context</h3>
              <p>
                Review quality, candidate outline, descriptors, uncertainty, and
                limitations together.
              </p>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <h3>Compare only when supported</h3>
              <p>
                See user confirmation and registration confidence before any
                normalized change.
              </p>
            </div>
          </li>
          <li>
            <span>04</span>
            <div>
              <h3>Add your own note</h3>
              <p>
                Professional annotations stay distinct from automated output and
                remain auditable.
              </p>
            </div>
          </li>
        </ol>
      </section>

      <section
        className="detail-band detail-band--dark"
        aria-labelledby="portal-heading"
      >
        <div className="page-width portal-preview">
          <div>
            <p className="section-label">Clinician workspace</p>
            <h2 id="portal-heading">
              Designed for fast review without hiding uncertainty.
            </h2>
            <p>
              The workspace groups shared cases, image pairs, session coverage,
              annotations, reports, and access history. Additional model output
              stays separate from the primary visual observation.
            </p>
          </div>
          <div
            className="portal-ledger"
            role="group"
            aria-label="Clinician workspace structure preview"
          >
            <div className="portal-ledger__head">
              <strong>Shared record</strong>
              <span>View-only access</span>
            </div>
            <dl>
              <div>
                <dt>Coverage</dt>
                <dd>Eight named regions</dd>
              </div>
              <div>
                <dt>Primary view</dt>
                <dd>Image, outline, descriptors, limits</dd>
              </div>
              <div>
                <dt>Comparison</dt>
                <dd>Confirmation and geometry status</dd>
              </div>
              <div>
                <dt>Additional analysis</dt>
                <dd>Separate, versioned, expandable</dd>
              </div>
            </dl>
            <p>Structure preview. No patient record is shown.</p>
          </div>
        </div>
      </section>

      <section
        className="page-width professional-boundaries"
        aria-labelledby="boundary-heading"
      >
        <div>
          <p className="section-label">Clear boundaries</p>
          <h2 id="boundary-heading">What Stoma3D leaves to you.</h2>
        </div>
        <ul>
          <li>Diagnosis and differential diagnosis</li>
          <li>Physical examination and clinical imaging</li>
          <li>Biopsy, referral, treatment, and follow-up decisions</li>
          <li>Interpretation of incomplete or low-quality user capture</li>
        </ul>
      </section>

      <section className="professional-close">
        <div className="page-width professional-close__inner">
          <h2>Review the analysis record, then request secure access.</h2>
          <p>
            Model versions, capture quality, confidence, and known limitations
            travel with every shared result.
          </p>
          <Link className="button button--light" href="/research">
            Review analysis & evidence
          </Link>
          <Link className="text-link" href="/professional-apply">
            Apply for clinician access
          </Link>
        </div>
      </section>
    </>
  );
}
