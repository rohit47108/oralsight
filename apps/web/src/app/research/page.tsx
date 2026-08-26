import type { Metadata } from "next";

import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = {
  title: "Analysis & evidence",
  description:
    "See how OralSight checks captures, highlights candidate areas, records confidence, and publishes model performance.",
};

const releaseGates = [
  {
    output: "Candidate outline",
    evidence: "Patient-disjoint segmentation evaluation",
    gate: "Dice ≥ 0.70 and boundary F1 ≥ 0.60",
  },
  {
    output: "Anatomy match",
    evidence: "Eight-region held-out evaluation",
    gate: "Macro F1 ≥ 0.80 and every region recall ≥ 0.70",
  },
  {
    output: "Appearance words",
    evidence: "At least 50 held-out patients per class",
    gate: "Macro F1 ≥ 0.75, class recall ≥ 0.70, calibration error ≤ 0.08",
  },
  {
    output: "Disease-category research panel",
    evidence:
      "Independent set with at least 100 patients per class and signed clinical review",
    gate: "Sensitivity and specificity ≥ 0.80 per class, macro F1 ≥ 0.80, calibration error ≤ 0.05",
  },
  {
    output: "Suggested re-identification",
    evidence:
      "At least 200 matches and 200 hard negatives from 50 held-out patients",
    gate: "Precision ≥ 0.95 and lower 95% confidence bound ≥ 0.90",
  },
] as const;

export default function ResearchPage() {
  return (
    <>
      <PageIntro
        label="Analysis & evidence"
        title="Every result carries its own record."
        description="OralSight keeps capture quality, model versions, confidence, and limitations beside the image so a result can be understood and checked."
      />

      <section
        className="page-width research-status"
        aria-labelledby="status-heading"
      >
        <div>
          <p className="section-label">Current deployment</p>
          <h2 id="status-heading">
            The deployed model card is the source of truth.
          </h2>
        </div>
        <p>
          OralSight reads a versioned model card at runtime. It lists the active
          analysis tools, exact model versions and hashes, evaluation metrics,
          known limits, and release status for the service you are using.
        </p>
      </section>

      <section
        className="gate-section page-width"
        aria-labelledby="gate-heading"
      >
        <div className="gate-section__heading">
          <p className="section-label">Performance requirements</p>
          <h2 id="gate-heading">
            Each analysis tool earns release separately.
          </h2>
        </div>
        <div
          className="gate-table"
          role="table"
          aria-label="Analysis release requirements"
        >
          <div className="gate-table__header" role="row">
            <span role="columnheader">Output</span>
            <span role="columnheader">Required evidence</span>
            <span role="columnheader">Release threshold</span>
          </div>
          {releaseGates.map((item) => (
            <div className="gate-table__row" role="row" key={item.output}>
              <strong role="rowheader">{item.output}</strong>
              <span role="cell">{item.evidence}</span>
              <span role="cell">{item.gate}</span>
            </div>
          ))}
        </div>
      </section>

      <section
        className="detail-band detail-band--dark"
        aria-labelledby="primary-heading"
      >
        <div className="page-width research-output-split">
          <div>
            <p className="section-label">Primary observation</p>
            <h2 id="primary-heading">
              Start with what is visible in the image.
            </h2>
            <ul>
              <li>Candidate mask or outline</li>
              <li>Approximate normalized area</li>
              <li>Shape, color, and texture descriptors</li>
              <li>Uncertainty and limitations</li>
              <li>A clear reason and next step when analysis stops</li>
            </ul>
          </div>
          <div>
            <p className="section-label">Additional pattern analysis</p>
            <h2>Extra context stays separate from the primary result.</h2>
            <p>
              Additional categories appear only when the deployed model card
              marks that tool as released. They stay in an expandable panel with
              their confidence and model version, leaving the visual observation
              easy to read first.
            </p>
          </div>
        </div>
      </section>

      <section
        className="page-width limitation-ledger"
        aria-labelledby="limits-heading"
      >
        <div className="limitation-ledger__heading">
          <p className="section-label">Reading a result well</p>
          <h2 id="limits-heading">
            Important context stays beside the result.
          </h2>
        </div>
        <dl>
          <div>
            <dt>Diagnosis</dt>
            <dd>
              A result organizes visible image findings for follow-up; diagnosis
              requires an appropriate professional evaluation.
            </dd>
          </div>
          <div>
            <dt>Harmlessness</dt>
            <dd>
              A quiet-looking image is still only one view at one point in time.
            </dd>
          </div>
          <div>
            <dt>Physical size</dt>
            <dd>
              Millimeter estimates require a visible calibration marker,
              accepted geometry, and repeatability checks. Otherwise only
              approximate normalized values appear.
            </dd>
          </div>
          <div>
            <dt>Comparable change</dt>
            <dd>
              A user-confirmed match may still fail registration and show
              “insufficient comparable data.”
            </dd>
          </div>
          <div>
            <dt>Complete coverage of people or devices</dt>
            <dd>
              Performance can vary with anatomy, skin tone, device camera,
              lighting, motion, and conditions not represented in the evaluation
              set.
            </dd>
          </div>
          <div>
            <dt>Clinical validity</dt>
            <dd>
              Engineering performance is recorded separately from any future
              clinical or regulatory evaluation.
            </dd>
          </div>
        </dl>
      </section>

      <section
        className="detail-band detail-band--amber"
        aria-labelledby="guidance-heading"
      >
        <div className="page-width detail-split">
          <div>
            <p className="section-label">Next-step information</p>
            <h2 id="guidance-heading">
              Symptoms and image analysis remain separate.
            </h2>
          </div>
          <div className="long-copy">
            <p>
              OralSight can organize symptom answers, duration, progression,
              image quality, and uncertainty using a signed, versioned guidance
              file. The app records the exact guidance version used and always
              keeps model categories out of that decision.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
