import type { Metadata } from "next";
import Link from "next/link";

import { PageIntro } from "@/components/page-intro";
import { RegionMap } from "@/components/region-map";
import { scanSteps } from "@/content/site";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "See the OralSight path from consent and eight-region capture to review, comparison, and a report you control.",
};

export default function HowItWorksPage() {
  return (
    <>
      <PageIntro
        label="How it works"
        title="The same eight views. Every time."
        description="A complete session follows one fixed path. Clear quality checks stop unusable images before they become part of your record."
      />

      <section
        className="process-layout page-width"
        aria-label="OralSight workflow"
      >
        <ol className="process-list">
          {scanSteps.map((step, index) => (
            <li key={step.title}>
              <span className="process-list__number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h2>{step.title}</h2>
                <p>{step.summary}</p>
              </div>
            </li>
          ))}
        </ol>
        <RegionMap compact />
      </section>

      <section
        className="detail-band"
        id="start"
        aria-labelledby="capture-heading"
      >
        <div className="page-width detail-split">
          <div>
            <p className="section-label">Before capture</p>
            <h2 id="capture-heading">
              Start with permission and a steady frame.
            </h2>
          </div>
          <div className="long-copy">
            <p>
              Consent comes first. The app asks about symptoms only to organize
              the session and apply approved information rules. You can skip
              optional questions.
            </p>
            <p>
              During capture, motion feedback helps you steady the phone. After
              the shutter, OralSight checks blur, lighting, glare, obstruction,
              faces, and whether the selected mouth region is present. Rejected
              images are not saved or sent for analysis.
            </p>
          </div>
        </div>
      </section>

      <section
        className="page-width quality-sequence"
        aria-labelledby="quality-heading"
      >
        <div className="quality-sequence__heading">
          <p className="section-label">What happens to a capture</p>
          <h2 id="quality-heading">An image must earn its place.</h2>
        </div>
        <ol>
          <li>
            <span>1</span>
            <div>
              <h3>Private checks</h3>
              <p>
                Quality and face checks run before the image is stored or sent.
              </p>
            </div>
          </li>
          <li>
            <span>2</span>
            <div>
              <h3>Clean copy</h3>
              <p>
                Metadata is removed and a sanitized copy is prepared for
                analysis.
              </p>
            </div>
          </li>
          <li>
            <span>3</span>
            <div>
              <h3>Signed response</h3>
              <p>
                The app accepts only a valid response that matches the capture
                and schema.
              </p>
            </div>
          </li>
          <li>
            <span>4</span>
            <div>
              <h3>Clear feedback</h3>
              <p>
                If a capture cannot be analyzed, the app explains what happened
                and gives you the next useful action.
              </p>
            </div>
          </li>
        </ol>
      </section>

      <section
        className="detail-band detail-band--teal"
        aria-labelledby="results-heading"
      >
        <div className="page-width detail-split">
          <div>
            <p className="section-label">Observation review</p>
            <h2 id="results-heading">
              The result shows its limits beside the image.
            </h2>
          </div>
          <div className="long-copy">
            <p>
              A completed primary result can show a candidate outline,
              approximate image-normalized area, visible shape, color, and
              texture descriptors, confidence, and the capture details used to
              produce the result.
            </p>
            <p>
              Additional image-pattern analysis appears in a separate details
              panel when it is available. The deployed model card records which
              analysis tools are active and how they were evaluated.
            </p>
            <Link className="arrow-link arrow-link--light" href="/research">
              See how analysis works <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
      </section>

      <section className="page-width comparison-explainer" id="compare">
        <div className="comparison-explainer__copy">
          <p className="section-label">Over time</p>
          <h2>Suggested matches still need your confirmation.</h2>
          <p>
            The app can suggest that two observations may show the same area. It
            never silently links them. After confirmation, a geometric check
            decides whether a normalized change estimate is comparable.
          </p>
        </div>
        <div className="decision-path" aria-label="Comparison decision path">
          <div>
            <strong>Possible match</strong>
            <span>Suggested by the app</span>
          </div>
          <i aria-hidden="true">→</i>
          <div>
            <strong>User confirms</strong>
            <span>Required every time</span>
          </div>
          <i aria-hidden="true">→</i>
          <div>
            <strong>Geometry checked</strong>
            <span>Weak comparisons are suppressed</span>
          </div>
        </div>
      </section>
    </>
  );
}
