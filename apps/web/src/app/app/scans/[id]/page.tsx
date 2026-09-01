import { MOUTH_REGIONS } from "@stoma3d/contracts";
import type { Metadata } from "next";
import Link from "next/link";

import { WorkspaceState } from "@/components/workspace-state";
import {
  PlatformApiError,
  getScanSession,
  listScanCaptureSets,
} from "@/lib/platform-api";
import { readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Scan record" };

export default async function ScanDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [scanResult, captureResult] = await Promise.all([
    getScanSession(id).then(
      (scan) => ({ ok: true as const, scan }),
      (error: unknown) => ({ ok: false as const, error }),
    ),
    listScanCaptureSets(id).then(
      (sets) => ({ ok: true as const, sets }),
      (error: unknown) => ({ ok: false as const, error }),
    ),
  ]);
  if (!scanResult.ok) {
    const { error } = scanResult;
    const message =
      error instanceof PlatformApiError && error.status === 404
        ? "This scan was not found in your account. Check the record ID in the mobile app."
        : error instanceof PlatformApiError
          ? error.message
          : "This scan could not be opened.";
    return (
      <div className="workspace-page">
        <WorkspaceState
          title="Scan unavailable"
          body={message}
          action={{ href: "/app/scans", label: "Back to scans" }}
        />
      </div>
    );
  }

  const scan = scanResult.scan;
  const captureSets = captureResult.ok ? captureResult.sets.items : [];
  const setByRegion = new Map(captureSets.map((set) => [set.region, set]));
  const acceptedRegions = new Set(
    captureSets.filter((set) => set.complete).map((set) => set.region),
  );

  return (
    <div className="workspace-page">
      <nav className="workspace-breadcrumb" aria-label="Breadcrumb">
        <Link href="/app/scans">Scans</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{scan.scanSessionId}</span>
      </nav>
      <header className="record-heading">
        <div>
          <p className="workspace-kicker">Synced scan record</p>
          <h1>{readableLabel(scan.protocol)}</h1>
          <p>
            {captureResult.ok
              ? `${acceptedRegions.size} of 8 regions have a complete accepted capture set.`
              : "The scan record opened, but its region details are temporarily unavailable."}
          </p>
        </div>
        <span className="record-status" data-state={scan.status}>
          {readableLabel(scan.status)}
        </span>
      </header>
      <dl className="record-ledger">
        <div>
          <dt>Record ID</dt>
          <dd>{scan.scanSessionId}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{readableDate(scan.createdAt)}</dd>
        </div>
        <div>
          <dt>Last updated</dt>
          <dd>{readableDate(scan.updatedAt)}</dd>
        </div>
        <div>
          <dt>Completed</dt>
          <dd>
            {scan.completedAt ? readableDate(scan.completedAt) : "Not complete"}
          </dd>
        </div>
      </dl>

      {!captureResult.ok ? (
        <WorkspaceState
          title="Region details could not be loaded."
          body={
            captureResult.error instanceof PlatformApiError
              ? captureResult.error.message
              : "The scan itself remains available. Try this page again."
          }
          action={{
            href: `/app/scans/${encodeURIComponent(scan.scanSessionId)}`,
            label: "Try again",
          }}
        />
      ) : (
        <section
          className="scan-coverage"
          aria-labelledby="scan-coverage-title"
        >
          <header>
            <div>
              <p className="workspace-kicker">Eight-region record</p>
              <h2 id="scan-coverage-title">Capture coverage</h2>
            </div>
            <span>{acceptedRegions.size}/8 complete</span>
          </header>
          <div
            className="coverage-progress"
            role="progressbar"
            aria-label="Accepted mouth regions"
            aria-valuemin={0}
            aria-valuemax={8}
            aria-valuenow={acceptedRegions.size}
          >
            <span style={{ width: `${(acceptedRegions.size / 8) * 100}%` }} />
          </div>
          <ol className="region-record-list">
            {MOUTH_REGIONS.map((region, index) => {
              const captureSet = setByRegion.get(region);
              const complete = captureSet?.complete ?? false;
              return (
                <li key={region} data-state={complete ? "complete" : "missing"}>
                  <span className="region-record-list__number">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <strong>{readableLabel(region)}</strong>
                    <span>
                      {captureSet
                        ? `${captureSet.views.length} accepted ${captureSet.views.length === 1 ? "view" : "views"}`
                        : "No synced capture set"}
                    </span>
                  </div>
                  <span className="region-record-list__state">
                    {complete ? "Complete" : "Needs capture"}
                  </span>
                  {captureSet ? (
                    <details>
                      <summary>View details</summary>
                      <dl>
                        <div>
                          <dt>Capture set</dt>
                          <dd>{captureSet.captureSetId}</dd>
                        </div>
                        <div>
                          <dt>Protocol</dt>
                          <dd>{readableLabel(captureSet.protocol)}</dd>
                        </div>
                      </dl>
                      {captureSet.views.length ? (
                        <ol className="capture-view-list">
                          {captureSet.views.map((view) => (
                            <li key={view.captureViewId}>
                              <strong>{readableLabel(view.angle)}</strong>
                              <span>
                                {view.asset.widthPx} × {view.asset.heightPx}px
                              </span>
                              <span>{readableDate(view.capturedAt)}</span>
                              <span>
                                {readableLabel(view.asset.inputOrigin)}
                              </span>
                            </li>
                          ))}
                        </ol>
                      ) : null}
                    </details>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </section>
      )}
      <p className="record-disclaimer">This result is not a diagnosis.</p>
    </div>
  );
}
