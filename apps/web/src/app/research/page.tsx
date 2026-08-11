import type { Metadata } from "next";

import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = {
  title: "Research & limitations",
  description:
    "Read OralSight model release gates, measurement limits, abstention behavior, dataset limits, and forbidden conclusions.",
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
        label="Research & limitations"
        title="No evidence, no output."
        description="A model can exist in the codebase and still remain hidden in the product. Each output has its own data, performance, calibration, and review gate."
      />

      <section
        className="page-width research-status"
        aria-labelledby="status-heading"
      >
        <div>
          <p className="section-label">Release status</p>
          <h2 id="status-heading">
            The deployed model card is the source of truth.
          </h2>
        </div>
        <p>
          OralSight reads a versioned model card at runtime. It names model
          files, hashes, enabled heads, metrics, limitations, and gate status. A
          public page never substitutes a marketing claim for that record.
        </p>
      </section>

      <section
        className="gate-section page-width"
        aria-labelledby="gate-heading"
      >
        <div className="gate-section__heading">
          <p className="section-label">Required evidence</p>
          <h2 id="gate-heading">Five outputs. Five separate gates.</h2>
        </div>
        <div
          className="gate-table"
          role="table"
          aria-label="Research output release gates"
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
              Describe the image before naming a category.
            </h2>
            <ul>
              <li>Candidate mask or outline</li>
              <li>Approximate normalized area</li>
              <li>Shape, color, and texture descriptors</li>
              <li>Uncertainty and limitations</li>
              <li>Reasons for abstention</li>
            </ul>
          </div>
          <div>
            <p className="section-label">Experimental research output</p>
            <h2>Separate, collapsed, and never a care rule.</h2>
            <p>
              A disease-category head may appear only after its stricter gate
              and signed review pass. It remains expandable, plainly labeled,
              and cannot set urgency or care guidance.
            </p>
          </div>
        </div>
      </section>

      <section
        className="page-width limitation-ledger"
        aria-labelledby="limits-heading"
      >
        <div className="limitation-ledger__heading">
          <p className="section-label">Known limits</p>
          <h2 id="limits-heading">What the product cannot establish.</h2>
        </div>
        <dl>
          <div>
            <dt>Diagnosis</dt>
            <dd>
              A photograph and research model do not establish a diagnosis.
            </dd>
          </div>
          <div>
            <dt>Harmlessness</dt>
            <dd>No result proves that an observed change is harmless.</dd>
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
              Passing a competition release gate does not establish clinical
              validity or regulatory clearance.
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
            <p className="section-label">Care information</p>
            <h2 id="guidance-heading">
              Models do not decide what you should do next.
            </h2>
          </div>
          <div className="long-copy">
            <p>
              Review priority can come only from a signed, versioned,
              clinician-approved rule file using symptoms, duration,
              progression, image quality, and uncertainty. If that file is
              absent or invalid, urgency levels stay off and the app gives
              neutral seek-care information.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
