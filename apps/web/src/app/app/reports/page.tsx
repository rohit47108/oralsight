import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { WorkspaceState } from "@/components/workspace-state";
import {
  listGeneratedArtifacts,
  listReports,
  PlatformApiError,
} from "@/lib/platform-api";
import { compactHash, readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Reports and media" };

export default async function ReportsPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string; before?: string }>;
}) {
  const query = await searchParams;
  const value = query.id?.trim();
  if (value && /^[A-Za-z0-9._:-]{1,128}$/.test(value)) {
    redirect(`/app/reports/${encodeURIComponent(value)}`);
  }
  const invalid = Boolean(value);
  const before =
    query.before && !Number.isNaN(Date.parse(query.before))
      ? query.before
      : undefined;
  const [reports, artifacts] = await Promise.all([
    listReports(before).then(
      (records) => ({ ok: true as const, records }),
      (error: unknown) => ({ ok: false as const, error }),
    ),
    listGeneratedArtifacts(undefined, 8).then(
      (records) => ({ ok: true as const, records }),
      () => ({ ok: false as const }),
    ),
  ]);

  return (
    <div className="workspace-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Prepared records</p>
          <h1>Reports and generated media.</h1>
          <p>
            Open the clinician-ready report, a captioned scan summary, or the
            observation surface generated for your own account.
          </p>
        </div>
      </header>

      <form
        className="record-lookup"
        method="get"
        aria-label="Open report by ID"
      >
        <label htmlFor="report-id">Open a specific report</label>
        <div>
          <input
            id="report-id"
            name="id"
            autoComplete="off"
            spellCheck="false"
            aria-invalid={invalid}
            aria-describedby={invalid ? "report-id-error" : "report-id-help"}
            placeholder="Report record ID"
            required
          />
          <button className="button" type="submit">
            Open report
          </button>
        </div>
        <small id={invalid ? "report-id-error" : "report-id-help"}>
          {invalid
            ? "Enter the report ID exactly as OralSight shows it."
            : "Reports from another account are never returned."}
        </small>
      </form>

      {!reports.ok ? (
        <WorkspaceState
          title="Your reports could not be loaded."
          body={
            reports.error instanceof PlatformApiError
              ? reports.error.message
              : "Try again when your connection is available."
          }
          action={{ href: "/app/reports", label: "Try again" }}
        />
      ) : reports.records.items.length === 0 ? (
        <WorkspaceState
          title={before ? "No older reports." : "No reports prepared yet."}
          body={
            before
              ? "You have reached the beginning of this account’s report history."
              : "A report appears here after OralSight prepares it from an accepted scan."
          }
          action={
            before
              ? { href: "/app/reports", label: "Back to newest" }
              : undefined
          }
        />
      ) : (
        <section className="archive-ledger" aria-labelledby="report-list-title">
          <header>
            <div>
              <p className="workspace-kicker">Clinician-ready files</p>
              <h2 id="report-list-title">
                {before ? "Earlier reports" : "Most recent"}
              </h2>
            </div>
            <span>{reports.records.items.length} loaded</span>
          </header>
          <ol className="archive-list archive-list--reports">
            {reports.records.items.map((report) => (
              <li key={report.reportArtifactId}>
                <Link
                  href={`/app/reports/${encodeURIComponent(report.reportArtifactId)}`}
                >
                  <div className="archive-list__date">
                    <strong>{readableLabel(report.format)}</strong>
                    <span>{readableDate(report.createdAt)}</span>
                  </div>
                  <div>
                    <span>Source scans</span>
                    <strong>{report.scanSessionIds.length}</strong>
                  </div>
                  <div>
                    <span>Verified file</span>
                    <strong title={report.sha256}>
                      {compactHash(report.sha256)}
                    </strong>
                  </div>
                  <span className="archive-list__arrow" aria-hidden="true">
                    →
                  </span>
                </Link>
              </li>
            ))}
          </ol>
          <nav className="archive-pagination" aria-label="Report archive pages">
            {before ? (
              <Link href="/app/reports">Newest reports</Link>
            ) : (
              <span />
            )}
            {reports.records.nextCursor ? (
              <Link
                href={`/app/reports?before=${encodeURIComponent(reports.records.nextCursor)}`}
              >
                Older reports
              </Link>
            ) : null}
          </nav>
        </section>
      )}

      <section className="generated-ledger" aria-labelledby="generated-title">
        <header>
          <div>
            <p className="workspace-kicker">Generated outputs</p>
            <h2 id="generated-title">Videos and observation surfaces</h2>
          </div>
          <span>
            {artifacts.ok ? artifacts.records.items.length : 0} available
          </span>
        </header>
        {!artifacts.ok ? (
          <WorkspaceState
            title="Generated media could not be loaded."
            body="Your reports are still available above."
          />
        ) : artifacts.records.items.length === 0 ? (
          <WorkspaceState
            title="No generated media yet."
            body="Completed summary-video and observation-surface jobs appear here without any sample files."
          />
        ) : (
          <ol className="generated-list">
            {artifacts.records.items.map((artifact) => (
              <li key={artifact.artifactId}>
                <Link
                  href={`/app/artifacts/${encodeURIComponent(artifact.artifactId)}`}
                >
                  <span className="generated-list__type" aria-hidden="true">
                    {artifact.purpose === "summary_video" ? "▶" : "3D"}
                  </span>
                  <div>
                    <strong>{readableLabel(artifact.purpose)}</strong>
                    <span>{artifact.filename}</span>
                  </div>
                  <span>{readableDate(artifact.createdAt)}</span>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
