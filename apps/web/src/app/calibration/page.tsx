import type { Metadata } from "next";

import { ArucoMarker17 } from "@/components/aruco-marker";
import {
  CALIBRATION_QR_PAYLOAD,
  CalibrationQr,
} from "@/components/calibration-qr";
import { PrintButton } from "@/components/print-button";

export const metadata: Metadata = {
  title: "Print calibration card",
  description:
    "Print the versioned 20 mm OralSight reference used by supported calibrated captures.",
};

export default function CalibrationPage() {
  return (
    <div className="calibration-page">
      <section className="calibration-intro page-width">
        <p className="eyebrow">Physical scale reference</p>
        <h1>Print the OralSight calibration card.</h1>
        <p>
          Use this card only with a supported capture flow. Print it at 100%
          scale, check the ruler, and keep the marker flat in the same plane as
          the visible area being recorded.
        </p>
        <div className="calibration-actions">
          <a
            className="button"
            href="/calibration/oralsight-calibration-a4.pdf"
            download
          >
            Download A4 PDF
          </a>
          <a
            className="text-button"
            href="/calibration/oralsight-calibration-letter.pdf"
            download
          >
            Download US Letter PDF
          </a>
          <PrintButton />
        </div>
        <p className="print-button-note">
          Choose Actual size or 100%. Never choose Fit to page. The downloaded
          PDFs are the tested source files.
        </p>
      </section>

      <section className="calibration-sheet" aria-labelledby="card-title">
        <div className="calibration-card">
          <header className="calibration-card__header">
            <div>
              <span>OralSight physical reference</span>
              <h2 id="card-title">20 mm capture card</h2>
            </div>
            <strong>oralsight-calibration-v1</strong>
          </header>
          <div className="calibration-card__body">
            <div className="marker-block">
              <div className="physical-marker-frame">
                <ArucoMarker17 />
              </div>
              <span>DICT_4X4_50, marker 17: 20.0 mm</span>
            </div>
            <div className="neutral-reference">
              <p>Neutral orientation reference</p>
              <div
                className="neutral-swatches"
                aria-label="Four neutral reference patches"
              >
                <span data-tone="dark" aria-label="Gray value 35" />
                <span data-tone="lower-middle" aria-label="Gray value 100" />
                <span data-tone="upper-middle" aria-label="Gray value 170" />
                <span data-tone="light" aria-label="Gray value 235" />
              </div>
              <small>
                These patches help detect severe color shifts. They are not a
                laboratory color standard.
              </small>
            </div>
            <div className="calibration-card__qr-block">
              <CalibrationQr />
              <span>Marker metadata</span>
            </div>
          </div>
          <div className="scale-check">
            <span>Print check: this line must measure exactly 50 mm</span>
            <i aria-hidden="true" />
          </div>
          <footer>
            <span>Keep outside the mouth. Do not resize.</span>
            <span>Estimated size only. This result is not a diagnosis.</span>
          </footer>
        </div>
      </section>

      <section className="calibration-guidance page-width">
        <article>
          <h2>Print at actual size</h2>
          <p>
            A4 and US Letter are both supported. Use portrait orientation,
            normal margins, and 100% scale. Disable header and footer printing.
          </p>
        </article>
        <article>
          <h2>Check before use</h2>
          <p>
            Measure the 50 mm line with a physical ruler. If it is not exactly
            50 mm, correct the print settings and print again.
          </p>
        </article>
        <article>
          <h2>Use only after a valid check</h2>
          <p>
            A printed card alone does not validate a measurement. OralSight
            shows millimeter estimates only when the captured marker passes the
            platform’s scale, angle, visibility, and confidence checks.
          </p>
        </article>
      </section>

      <section
        className="calibration-metadata page-width"
        aria-labelledby="payload-title"
      >
        <div>
          <p className="eyebrow">Machine-readable metadata</p>
          <h2 id="payload-title">QR payload</h2>
          <p>
            This payload identifies the card version and expected geometry. It
            contains no account, scan, or health information.
          </p>
        </div>
        <code>{CALIBRATION_QR_PAYLOAD}</code>
      </section>
    </div>
  );
}
