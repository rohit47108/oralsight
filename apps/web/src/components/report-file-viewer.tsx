"use client";

type ReportFileViewerProps = {
  reportId?: string;
  contentHref?: string;
  format: "pdf" | "html" | "fhir_r4_bundle" | "summary_video" | "transcript";
  headingLevel?: "h2" | "h3" | "h4";
  showDisclaimer?: boolean;
};

export function ReportFileViewer({
  reportId,
  contentHref: suppliedContentHref,
  format,
  headingLevel = "h2",
  showDisclaimer = true,
}: ReportFileViewerProps) {
  const contentHref =
    suppliedContentHref ??
    (reportId ? `/api/reports/${encodeURIComponent(reportId)}/content` : "");
  const Heading = headingLevel;
  const downloadLabel =
    format === "pdf"
      ? "Download PDF"
      : format === "summary_video"
        ? "Download video"
        : "Download file";
  return (
    <section className="report-file" aria-label="Protected report file">
      <header>
        <div>
          <p className="workspace-kicker">Protected file</p>
          <Heading>
            {format === "pdf"
              ? "Clinician-ready report"
              : format === "summary_video"
                ? "Scan summary video"
                : "Prepared report file"}
          </Heading>
        </div>
        <a className="button button--compact" href={contentHref} download>
          {downloadLabel}
        </a>
      </header>
      {format === "pdf" ? (
        <iframe
          className="report-file__frame"
          src={contentHref}
          title="Stoma3D clinician-ready PDF report"
        />
      ) : format === "summary_video" ? (
        <video
          className="report-file__video"
          controls
          playsInline
          preload="metadata"
        >
          <source src={contentHref} type="video/mp4" />
          Your browser cannot play this video. Use the download link above.
        </video>
      ) : format === "html" ? (
        <iframe
          className="report-file__frame"
          src={contentHref}
          title="Stoma3D HTML report"
          sandbox=""
        />
      ) : (
        <div className="report-file__download-state">
          <strong>The file is ready.</strong>
          <p>
            {format === "fhir_r4_bundle"
              ? "Download the FHIR R4 bundle to use it with compatible clinical software."
              : "Download the text transcript in its original prepared format."}
          </p>
        </div>
      )}
      {showDisclaimer ? (
        <p className="record-disclaimer">This result is not a diagnosis.</p>
      ) : null}
    </section>
  );
}
