import type { Metadata } from "next";
import { cookies } from "next/headers";

import { AuthorizedResourceView } from "@/components/authorized-resource-view";
import { ShareExchange } from "@/components/share-exchange";
import { WorkspaceState } from "@/components/workspace-state";
import {
  getShareViewerResource,
  getShareViewerScope,
} from "@/lib/platform-api";
import { readableDate } from "@/lib/presentation";

export const metadata: Metadata = { title: "Shared OralSight record" };

const SHARE_COOKIE = "oralsight_share_token";

export default async function SharedRecordPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string; opened?: string }>;
}) {
  const query = await searchParams;
  if (query.id) {
    return (
      <div className="workspace-page shared-record-page">
        <ShareExchange shareId={query.id} />
      </div>
    );
  }
  const shareToken = (await cookies()).get(SHARE_COOKIE)?.value;
  if (!shareToken) {
    return (
      <div className="workspace-page shared-record-page">
        <WorkspaceState
          title="No shared record was opened."
          body="Use the complete link or QR code supplied by the record owner."
          headingLevel="h1"
        />
      </div>
    );
  }
  const scope = await getShareViewerScope(shareToken).then(
    (value) => ({ ok: true as const, value }),
    () => ({ ok: false as const }),
  );
  if (!scope.ok) {
    return (
      <div className="workspace-page shared-record-page">
        <WorkspaceState
          title="This shared record is no longer available."
          body="The link may have expired, been revoked, or reached its access limit."
          headingLevel="h1"
        />
      </div>
    );
  }
  const resources = await Promise.all(
    scope.value.resources.map((resource) =>
      getShareViewerResource(shareToken, resource).then(
        (value) => ({ ok: true as const, value }),
        () => ({ ok: false as const }),
      ),
    ),
  );
  const available = resources.flatMap((result) =>
    result.ok ? [result.value] : [],
  );
  return (
    <div className="workspace-page shared-record-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Patient-authorized access</p>
          <h1>Shared OralSight record</h1>
          <p>
            Access ends {readableDate(scope.value.shareExpiresAt)}. This page
            does not provide access to any other patient record.
          </p>
        </div>
        <span className="account-state" data-state="active">
          {scope.value.remainingUses} secure views left
        </span>
      </header>
      {available.length === 0 ? (
        <WorkspaceState
          title="The selected record could not be opened."
          body="Access remains limited to the records named by this share."
        />
      ) : (
        <div className="shared-resource-list">
          {available.map((resource) => (
            <AuthorizedResourceView
              key={`${resource.resourceType}:${resource.resourceId}`}
              resource={resource}
              reportContentHref={
                resource.resourceType === "report"
                  ? `/api/shared/reports/${encodeURIComponent(resource.resourceId)}/content`
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
