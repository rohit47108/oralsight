import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { WorkspaceState } from "@/components/workspace-state";
import { listScanSessions, PlatformApiError } from "@/lib/platform-api";
import { readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Scans" };

export default async function ScansPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string; before?: string }>;
}) {
  const query = await searchParams;
  const value = query.id?.trim();
  if (value && /^[A-Za-z0-9._:-]{1,128}$/.test(value)) {
    redirect(`/app/scans/${encodeURIComponent(value)}`);
  }
  const invalid = Boolean(value);
  const before =
    query.before && !Number.isNaN(Date.parse(query.before))
      ? query.before
      : undefined;
  const result = await listScanSessions(before).then(
    (records) => ({ ok: true as const, records }),
    (error: unknown) => ({ ok: false as const, error }),
  );

  return (
    <div className="workspace-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Scan archive</p>
          <h1>Your synced mouth scans.</h1>
          <p>
            Each row is returned from your account. Open a scan to review its
            eight named regions, accepted views, and preparation status.
          </p>
        </div>
      </header>

      <form className="record-lookup" method="get" aria-label="Open scan by ID">
        <label htmlFor="scan-id">Open a specific scan</label>
        <div>
          <input
            id="scan-id"
            name="id"
            autoComplete="off"
            spellCheck="false"
            aria-invalid={invalid}
            aria-describedby={invalid ? "scan-id-error" : "scan-id-help"}
            placeholder="Scan record ID"
            required
          />
          <button className="button" type="submit">
            Open scan
          </button>
        </div>
        <small id={invalid ? "scan-id-error" : "scan-id-help"}>
          {invalid
            ? "Use the letters, numbers, dots, colons, or dashes from the record ID."
            : "A direct lookup still checks that the scan belongs to your account."}
        </small>
      </form>

      {!result.ok ? (
        <WorkspaceState
          title="Your scan archive could not be loaded."
          body={
            result.error instanceof PlatformApiError
              ? result.error.message
              : "Try again when your connection is available."
          }
          action={{ href: "/app/scans", label: "Try again" }}
        />
      ) : result.records.items.length === 0 ? (
        <WorkspaceState
          title={before ? "No older scans." : "No synced scans yet."}
          body={
            before
              ? "You have reached the beginning of this account’s scan history."
              : "Complete or save a mouth scan on your phone, then turn on account sync."
          }
          action={
            before ? { href: "/app/scans", label: "Back to newest" } : undefined
          }
        />
      ) : (
        <section className="archive-ledger" aria-labelledby="scan-list-title">
          <header>
            <div>
              <p className="workspace-kicker">Account records</p>
              <h2 id="scan-list-title">
                {before ? "Earlier scans" : "Most recent"}
              </h2>
            </div>
            <span>{result.records.items.length} loaded</span>
          </header>
          <ol className="archive-list">
            {result.records.items.map((scan) => (
              <li key={scan.scanSessionId}>
                <Link
                  href={`/app/scans/${encodeURIComponent(scan.scanSessionId)}`}
                >
                  <div className="archive-list__date">
                    <strong>{readableDate(scan.createdAt)}</strong>
                    <span>{scan.scanSessionId}</span>
                  </div>
                  <div>
                    <span>Capture protocol</span>
                    <strong>{readableLabel(scan.protocol)}</strong>
                  </div>
                  <span
                    className="record-list__status"
                    data-state={scan.status}
                  >
                    {readableLabel(scan.status)}
                  </span>
                  <span className="archive-list__arrow" aria-hidden="true">
                    →
                  </span>
                </Link>
              </li>
            ))}
          </ol>
          <nav className="archive-pagination" aria-label="Scan archive pages">
            {before ? <Link href="/app/scans">Newest scans</Link> : <span />}
            {result.records.nextCursor ? (
              <Link
                href={`/app/scans?before=${encodeURIComponent(result.records.nextCursor)}`}
              >
                Older scans
              </Link>
            ) : null}
          </nav>
        </section>
      )}
    </div>
  );
}
