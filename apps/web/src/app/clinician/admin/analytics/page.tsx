import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { WorkspaceState } from "@/components/workspace-state";
import { getProductContext, productHomeForRole } from "@/lib/product-auth";
import { getAdminAnalyticsSummary } from "@/lib/platform-api";
import { readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Product use" };

export default async function AdminAnalyticsPage() {
  const context = await getProductContext();
  if (context.state !== "ready") return null;
  if (context.account.role !== "admin") {
    redirect(productHomeForRole(context.account.role));
  }
  const summary = await getAdminAnalyticsSummary(30).then(
    (value) => ({ ok: true as const, value }),
    () => ({ ok: false as const }),
  );

  return (
    <div className="workspace-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Administrator</p>
          <h1>Opt-in product use.</h1>
          <p>
            This summary contains allowlisted use events from people who opted
            in. It contains no images, health records, symptoms, report text, or
            model output.
          </p>
        </div>
        <span className="account-state" data-state="active">
          Aggregate only
        </span>
      </header>

      {!summary.ok ? (
        <WorkspaceState
          title="Product-use totals could not be loaded."
          body="No estimate or cached total is shown while the analytics service is unavailable."
        />
      ) : (
        <>
          <dl className="analytics-summary-ledger">
            <div>
              <dt>Summary window</dt>
              <dd>Last {summary.value.days} days</dd>
            </div>
            <div>
              <dt>Privacy threshold</dt>
              <dd>
                At least {summary.value.minimumGroupSize} events per group
              </dd>
            </div>
            <div>
              <dt>Event retention</dt>
              <dd>30 days</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{readableDate(summary.value.generatedAt)}</dd>
            </div>
          </dl>

          {summary.value.groups.length === 0 ? (
            <WorkspaceState
              title="No groups meet the privacy threshold."
              body="A group appears only after at least five matching opt-in events are recorded within this window."
            />
          ) : (
            <section aria-labelledby="analytics-groups-title">
              <div className="workspace-section-heading">
                <div>
                  <p className="workspace-kicker">Allowlisted totals</p>
                  <h2 id="analytics-groups-title">
                    Events by platform and outcome
                  </h2>
                </div>
                <span>{summary.value.groups.length} groups</span>
              </div>
              <div
                className="analytics-table-wrap"
                role="region"
                aria-label="Product-use event totals"
                tabIndex={0}
              >
                <table className="analytics-table">
                  <thead>
                    <tr>
                      <th scope="col">Event</th>
                      <th scope="col">Platform</th>
                      <th scope="col">Outcome</th>
                      <th scope="col">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.value.groups.map((group) => (
                      <tr
                        key={`${group.name}:${group.platform}:${group.outcome}`}
                      >
                        <th scope="row">{readableLabel(group.name)}</th>
                        <td>{readableLabel(group.platform)}</td>
                        <td>{readableLabel(group.outcome)}</td>
                        <td className="analytics-table__count">
                          {group.count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
