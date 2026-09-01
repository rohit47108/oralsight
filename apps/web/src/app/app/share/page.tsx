import type { Metadata } from "next";

import { ClinicianGrantForm } from "@/components/clinician-grant-form";
import { RevokeAccessButton } from "@/components/revoke-access-button";
import {
  ShareBuilder,
  type ShareableRecordOption,
} from "@/components/share-builder";
import { WorkspaceState } from "@/components/workspace-state";
import {
  getAccessHistory,
  listAccessGrants,
  listReports,
  listScanSessions,
  listShareGrants,
  type AccessGrant,
  type AccessHistory,
  type ShareLink,
} from "@/lib/platform-api";
import { readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Sharing" };

type Loaded<T> = { ok: true; value: T } | { ok: false };

async function load<T>(operation: Promise<T>): Promise<Loaded<T>> {
  return operation.then(
    (value) => ({ ok: true as const, value }),
    () => ({ ok: false as const }),
  );
}

export default async function SharingPage() {
  const [shares, grants, history, reports, scans] = await Promise.all([
    load<{ items: ShareLink[] }>(listShareGrants()),
    load<{ items: AccessGrant[] }>(listAccessGrants()),
    load<AccessHistory>(getAccessHistory()),
    load(listReports(undefined, 50)),
    load(listScanSessions(undefined, 50)),
  ]);
  const recordOptions: ShareableRecordOption[] = [
    ...(reports.ok
      ? reports.value.items.map((report) => ({
          resourceType: "report" as const,
          resourceId: report.reportArtifactId,
          label: `${readableLabel(report.format)} - ${readableDate(report.createdAt)}`,
        }))
      : []),
    ...(scans.ok
      ? scans.value.items.map((scan) => ({
          resourceType: "scan_session" as const,
          resourceId: scan.scanSessionId,
          label: `${readableLabel(scan.protocol)} - ${readableDate(scan.createdAt)}`,
        }))
      : []),
  ];
  return (
    <div className="workspace-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Controlled sharing</p>
          <h1>Share a record without sharing your account.</h1>
          <p>
            Each link has an expiry and opening limit, can be revoked, and
            records when protected information is accessed.
          </p>
        </div>
      </header>
      <ShareBuilder
        recordOptions={recordOptions}
        operationKey={crypto.randomUUID()}
      />
      <section
        className="share-register"
        aria-labelledby="share-register-title"
      >
        <header>
          <div>
            <p className="workspace-kicker">Issued links</p>
            <h2 id="share-register-title">Active and past shares</h2>
          </div>
          <span>{shares.ok ? shares.value.items.length : 0} records</span>
        </header>
        {!shares.ok ? (
          <WorkspaceState
            title="Shares could not be loaded."
            body="Your records remain protected. Refresh when the service is available."
          />
        ) : shares.value.items.length === 0 ? (
          <WorkspaceState
            title="No links have been issued."
            body="Create a link above when you are ready to share a specific Stoma3D record."
          />
        ) : (
          <ul className="share-list">
            {shares.value.items.map((share) => (
              <li key={share.shareId}>
                <div>
                  <strong>
                    {share.active ? "Active link" : readableLabel(share.status)}
                  </strong>
                  <span>
                    {share.resources
                      .map((item) => readableLabel(item.resourceType))
                      .join(", ")}
                  </span>
                </div>
                <dl>
                  <div>
                    <dt>Expires</dt>
                    <dd>{readableDate(share.expiresAt)}</dd>
                  </div>
                  <div>
                    <dt>Openings</dt>
                    <dd>
                      {share.exchangeCount} of {share.maxExchanges}
                    </dd>
                  </div>
                </dl>
                {share.active ? (
                  <RevokeAccessButton
                    kind="share"
                    id={share.shareId}
                    operationKey={crypto.randomUUID()}
                  />
                ) : (
                  <span className="share-list__ended">Access ended</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section
        className="professional-sharing"
        aria-labelledby="professional-sharing-title"
      >
        <header>
          <div>
            <p className="workspace-kicker">Professional review</p>
            <h2 id="professional-sharing-title">
              Send a record to a verified clinician
            </h2>
          </div>
        </header>
        <ClinicianGrantForm
          recordOptions={recordOptions}
          operationKey={crypto.randomUUID()}
        />
        {!grants.ok ? (
          <WorkspaceState
            title="Professional access could not be loaded."
            body="No review access is implied when the service cannot confirm it."
          />
        ) : grants.value.items.length ? (
          <ul className="grant-list">
            {grants.value.items.map((grant) => (
              <li key={grant.grantId}>
                <div>
                  <strong>
                    {grant.label ??
                      `Clinician ${grant.clinicianUserId.slice(-8)}`}
                  </strong>
                  <span>
                    {grant.resources
                      .map((item) => readableLabel(item.resourceType))
                      .join(", ")}
                  </span>
                </div>
                <span>
                  {grant.active
                    ? `Expires ${readableDate(grant.expiresAt)}`
                    : "Access ended"}
                </span>
                {grant.active ? (
                  <RevokeAccessButton
                    kind="grant"
                    id={grant.grantId}
                    operationKey={crypto.randomUUID()}
                  />
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
      <section
        className="access-history"
        aria-labelledby="access-history-title"
      >
        <header>
          <div>
            <p className="workspace-kicker">Access history</p>
            <h2 id="access-history-title">Who opened or changed access</h2>
          </div>
        </header>
        {!history.ok ? (
          <WorkspaceState
            title="Access history could not be loaded."
            body="Try again before relying on this view for a sharing decision."
          />
        ) : history.value.items.length === 0 ? (
          <WorkspaceState
            title="No sharing activity yet."
            body="Views, exchanges, annotations, and access changes will appear here."
          />
        ) : (
          <ol className="access-event-list">
            {history.value.items.map((event) => (
              <li key={event.eventId}>
                <span className="access-event-list__mark" aria-hidden="true" />
                <div>
                  <strong>{readableLabel(event.eventType)}</strong>
                  <span>
                    {readableLabel(event.actorType)},{" "}
                    {readableDate(event.createdAt)}
                  </span>
                </div>
                <span>{readableLabel(event.resourceType)}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
