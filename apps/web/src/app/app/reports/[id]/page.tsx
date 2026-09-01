import type { Metadata } from "next";
import Link from "next/link";

import { ReportFileViewer } from "@/components/report-file-viewer";
import { WorkspaceState } from "@/components/workspace-state";
import { getReport, PlatformApiError } from "@/lib/platform-api";
import { compactHash, readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Report record" };

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await getReport(id).then(
    (report) => ({ ok: true as const, report }),
    (error: unknown) => ({ ok: false as const, error }),
  );
  if (!result.ok) {
    const { error } = result;
    const message =
      error instanceof PlatformApiError && error.status === 404
        ? "This report was not found in your account. Check the report ID in Stoma3D."
        : error instanceof PlatformApiError
          ? error.message
          : "This report could not be opened.";
    return (
      <div className="workspace-page">
        <WorkspaceState
          title="Report unavailable"
          body={message}
          action={{ href: "/app/reports", label: "Back to reports" }}
        />
      </div>
    );
  }
  const { report } = result;
  return (
    <div className="workspace-page">
      <nav className="workspace-breadcrumb" aria-label="Breadcrumb">
        <Link href="/app/reports">Reports and media</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{report.reportArtifactId}</span>
      </nav>
      <header className="record-heading">
        <div>
          <p className="workspace-kicker">Verified report record</p>
          <h1>{readableLabel(report.format)}</h1>
          <p>Prepared {readableDate(report.createdAt)}</p>
        </div>
        <span className="record-status">
          {report.accessible ? "Accessible output" : "Standard output"}
        </span>
      </header>
      <dl className="record-ledger">
        <div>
          <dt>Report ID</dt>
          <dd>{report.reportArtifactId}</dd>
        </div>
        <div>
          <dt>Source sessions</dt>
          <dd>{report.scanSessionIds.length}</dd>
        </div>
        <div>
          <dt>File size</dt>
          <dd>{(report.byteSize / 1024).toFixed(1)} KB</dd>
        </div>
        <div>
          <dt>Locale</dt>
          <dd>{report.locale}</dd>
        </div>
        <div>
          <dt>Input source</dt>
          <dd>{report.inputOrigins.map(readableLabel).join(", ")}</dd>
        </div>
        <div>
          <dt>Analysis source</dt>
          <dd>{report.analysisOrigins.map(readableLabel).join(", ")}</dd>
        </div>
        <div>
          <dt>Content hash</dt>
          <dd title={report.sha256}>{compactHash(report.sha256)}</dd>
        </div>
        <div>
          <dt>Signed record</dt>
          <dd>{report.signedEnvelopeId}</dd>
        </div>
      </dl>

      <ReportFileViewer
        reportId={report.reportArtifactId}
        format={report.format}
      />

      <section
        className="report-source-scans"
        aria-labelledby="source-scans-title"
      >
        <div>
          <p className="workspace-kicker">Source record</p>
          <h2 id="source-scans-title">Scans included in this report</h2>
        </div>
        <ol>
          {report.scanSessionIds.map((scanId) => (
            <li key={scanId}>
              <Link href={`/app/scans/${encodeURIComponent(scanId)}`}>
                <span>{scanId}</span>
                <span aria-hidden="true">Open →</span>
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <section className="report-provenance" aria-labelledby="provenance-title">
        <div>
          <p className="workspace-kicker">Provenance</p>
          <h2 id="provenance-title">Models named by this report</h2>
        </div>
        <dl>
          {Object.entries(report.modelVersions).map(([name, version]) => (
            <div key={name}>
              <dt>{readableLabel(name)}</dt>
              <dd>{version}</dd>
            </div>
          ))}
        </dl>
      </section>
      <p className="record-disclaimer">{report.disclaimer}</p>
    </div>
  );
}
