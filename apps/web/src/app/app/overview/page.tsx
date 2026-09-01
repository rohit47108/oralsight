import type { Metadata } from "next";
import Link from "next/link";

import { WorkspaceState } from "@/components/workspace-state";
import { getProductContext } from "@/lib/product-auth";
import {
  listJobs,
  listReports,
  listScanSessions,
  type PatientJob,
  type ScanSession,
} from "@/lib/platform-api";
import { readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "My Stoma3D" };

type Loaded<T> = { ok: true; value: T } | { ok: false };

function load<T>(operation: Promise<T>): Promise<Loaded<T>> {
  return operation.then(
    (value) => ({ ok: true as const, value }),
    () => ({ ok: false as const }),
  );
}

function ScanRow({ scan }: { scan: ScanSession }) {
  return (
    <li>
      <Link href={`/app/scans/${encodeURIComponent(scan.scanSessionId)}`}>
        <div>
          <strong>{readableLabel(scan.protocol)}</strong>
          <span>{readableDate(scan.createdAt)}</span>
        </div>
        <span className="record-list__status" data-state={scan.status}>
          {readableLabel(scan.status)}
        </span>
      </Link>
    </li>
  );
}

function JobRow({ job }: { job: PatientJob }) {
  const active = job.status === "queued" || job.status === "running";
  return (
    <li>
      <div className="job-row">
        <div>
          <strong>{readableLabel(job.type)}</strong>
          <span>{readableDate(job.createdAt)}</span>
        </div>
        <span className="record-list__status" data-state={job.status}>
          {active
            ? `${Math.round(job.progress * 100)}% ${readableLabel(job.status).toLowerCase()}`
            : readableLabel(job.outcome ?? job.status)}
        </span>
      </div>
    </li>
  );
}

export default async function PatientOverviewPage() {
  const context = await getProductContext();
  if (context.state !== "ready") return null;

  const [scans, reports, jobs] = await Promise.all([
    load(listScanSessions(undefined, 4)),
    load(listReports(undefined, 4)),
    load(listJobs(undefined, 4)),
  ]);
  const unavailable = !scans.ok && !reports.ok && !jobs.ok;

  return (
    <div className="workspace-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">My Stoma3D</p>
          <h1>Keep each record easy to find.</h1>
          <p>
            Capture on your phone. Your synced scans, prepared reports, and
            generated outputs stay together here.
          </p>
        </div>
        <span className="account-state" data-state={context.account.status}>
          {context.account.deletionPending
            ? "Deletion pending"
            : "Account active"}
        </span>
      </header>

      <section className="workspace-actions" aria-label="Open a record">
        <Link href="/app/scans">
          <span>Scan record</span>
          <strong>Open a scan</strong>
          <small>Coverage, protocol, and capture status</small>
        </Link>
        <Link href="/app/reports">
          <span>Prepared artifact</span>
          <strong>Open a report</strong>
          <small>Dates, provenance, and format details</small>
        </Link>
        <Link href="/app/share">
          <span>Controlled access</span>
          <strong>Manage sharing</strong>
          <small>Time limits, downloads, and revocation</small>
        </Link>
      </section>

      {unavailable ? (
        <WorkspaceState
          title="Your recent records could not be loaded."
          body="No account data is guessed when the service cannot confirm it. Refresh when your connection is available."
          action={{ href: "/app/overview", label: "Try again" }}
        />
      ) : (
        <div className="overview-ledgers">
          <section
            className="recent-ledger"
            aria-labelledby="recent-scans-title"
          >
            <header>
              <div>
                <p className="workspace-kicker">Recent captures</p>
                <h2 id="recent-scans-title">Scans</h2>
              </div>
              <Link href="/app/scans">View all</Link>
            </header>
            {!scans.ok ? (
              <WorkspaceState
                title="Scans could not be loaded."
                body="Reports and other records remain available."
              />
            ) : scans.value.items.length ? (
              <ol className="record-list">
                {scans.value.items.map((scan) => (
                  <ScanRow key={scan.scanSessionId} scan={scan} />
                ))}
              </ol>
            ) : (
              <WorkspaceState
                title="No synced scans yet."
                body="Complete or save a scan in the mobile app, then turn on sync for this account."
              />
            )}
          </section>

          <section
            className="recent-ledger"
            aria-labelledby="recent-reports-title"
          >
            <header>
              <div>
                <p className="workspace-kicker">Prepared files</p>
                <h2 id="recent-reports-title">Reports</h2>
              </div>
              <Link href="/app/reports">View all</Link>
            </header>
            {!reports.ok ? (
              <WorkspaceState
                title="Reports could not be loaded."
                body="Your scan records are not affected."
              />
            ) : reports.value.items.length ? (
              <ol className="record-list">
                {reports.value.items.map((report) => (
                  <li key={report.reportArtifactId}>
                    <Link
                      href={`/app/reports/${encodeURIComponent(report.reportArtifactId)}`}
                    >
                      <div>
                        <strong>{readableLabel(report.format)}</strong>
                        <span>{readableDate(report.createdAt)}</span>
                      </div>
                      <span>
                        {report.scanSessionIds.length} source scan
                        {report.scanSessionIds.length === 1 ? "" : "s"}
                      </span>
                    </Link>
                  </li>
                ))}
              </ol>
            ) : (
              <WorkspaceState
                title="No reports prepared yet."
                body="Create a report after an accepted scan is ready for review."
              />
            )}
          </section>

          {jobs.ok && jobs.value.items.length ? (
            <section
              className="recent-ledger recent-ledger--wide"
              aria-labelledby="recent-jobs-title"
            >
              <header>
                <div>
                  <p className="workspace-kicker">Background work</p>
                  <h2 id="recent-jobs-title">Generation status</h2>
                </div>
              </header>
              <ol className="record-list record-list--jobs">
                {jobs.value.items.map((job) => (
                  <JobRow key={job.jobId} job={job} />
                ))}
              </ol>
            </section>
          ) : null}
        </div>
      )}

      <section
        className="account-ledger"
        aria-labelledby="account-ledger-title"
      >
        <div>
          <p className="workspace-kicker">Account record</p>
          <h2 id="account-ledger-title">What the service confirmed</h2>
        </div>
        <dl>
          <div>
            <dt>Account ID</dt>
            <dd>{context.account.id}</dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd>{readableDate(context.account.createdAt)}</dd>
          </div>
          <div>
            <dt>Access</dt>
            <dd>Patient workspace</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
