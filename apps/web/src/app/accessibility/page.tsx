import type { Metadata } from "next";

import { PageIntro } from "@/components/page-intro";

export const metadata: Metadata = {
  title: "Accessibility",
  description:
    "Stoma3D accessibility support for screen readers, larger text, contrast, reduced motion, capture guidance, and alternative controls.",
};

export default function AccessibilityPage() {
  return (
    <>
      <PageIntro
        label="Accessibility"
        title="The scan path should work without perfect sight, hearing, motion, or dexterity."
        description="Accessibility is part of the capture and review workflow, not a separate viewing mode."
      />

      <section
        className="accessibility-index page-width"
        aria-label="Accessibility support"
      >
        {[
          [
            "Screen readers",
            "Controls use clear names, roles, states, and reading order. The oral observation map always has a synchronized text list.",
          ],
          [
            "Larger text",
            "Important instructions reflow instead of clipping. Layouts adapt to system text size and avoid fixed-height text areas.",
          ],
          [
            "Contrast and color",
            "Text and controls meet contrast targets. Status uses words, icons, and shape so color is never the only signal.",
          ],
          [
            "Motion",
            "Reduced Motion removes positional effects. Capture stability and state changes remain understandable without animation.",
          ],
          [
            "Capture guidance",
            "Optional spoken instructions, haptics, large targets, and caregiver-assisted capture reduce reliance on one sense or grip.",
          ],
          [
            "Keyboard and switch input",
            "Web controls keep a visible focus order. Native alternatives exist for gestures such as image comparison and 3D map movement.",
          ],
        ].map(([title, description], index) => (
          <article key={title}>
            <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
            <h2>{title}</h2>
            <p>{description}</p>
          </article>
        ))}
      </section>

      <section className="detail-band" aria-labelledby="map-access-heading">
        <div className="page-width detail-split">
          <div>
            <p className="section-label">No visual-only dead ends</p>
            <h2 id="map-access-heading">
              The 3D map is never the only way in.
            </h2>
          </div>
          <div className="long-copy">
            <p>
              Every region and observation pin is also available through a named
              native list. Selecting either view keeps the other in sync. If 3D
              rendering fails, the list remains usable and offers a retry.
            </p>
            <p>
              Image comparison supports drag, tap, and screen-reader step
              controls. Important measurement and confidence text is available
              outside the graphic.
            </p>
          </div>
        </div>
      </section>

      <section
        className="page-width testing-matrix"
        aria-labelledby="testing-heading"
      >
        <div>
          <p className="section-label">Release testing</p>
          <h2 id="testing-heading">
            Test the difficult states, not only the happy path.
          </h2>
        </div>
        <ul>
          <li>VoiceOver and TalkBack</li>
          <li>Keyboard-only navigation</li>
          <li>Large text and zoom</li>
          <li>High contrast and color filters</li>
          <li>Reduced motion</li>
          <li>Denied camera permission</li>
          <li>Rotation and tablet layouts</li>
          <li>Offline and timeout recovery</li>
        </ul>
      </section>

      <section
        className="detail-band detail-band--amber"
        aria-labelledby="feedback-heading"
      >
        <div className="page-width detail-split">
          <div>
            <p className="section-label">Feedback</p>
            <h2 id="feedback-heading">
              Accessibility reports need a private route.
            </h2>
          </div>
          <div className="long-copy">
            <p>
              A production release must publish a monitored accessibility
              contact and response target. Do not include mouth images or
              private health details in a public issue.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
