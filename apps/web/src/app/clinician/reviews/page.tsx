import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { AnnotationForm, ReviewStatusForm } from "@/components/review-forms";
import { AuthorizedResourceView } from "@/components/authorized-resource-view";
import { OutlineAdjustmentEditor } from "@/components/outline-adjustment-editor";
import { parseOutlineAdjustment } from "@/components/outline-adjustment";
import { WorkspaceState } from "@/components/workspace-state";
import { getProductContext, productHomeForAccount } from "@/lib/product-auth";
import {
  getClinicianReview,
  getClinicianReviewResource,
  listClinicianReviews,
  type ClinicianReview,
  type ResourceRef,
} from "@/lib/platform-api";
import { readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Clinical review" };

type Result<T> = { ok: true; value: T } | { ok: false };

function load<T>(operation: Promise<T>): Promise<Result<T>> {
  return operation.then(
    (value) => ({ ok: true as const, value }),
    () => ({ ok: false as const }),
  );
}

export default async function ClinicianReviewsPage({
  searchParams,
}: {
  searchParams: Promise<{
    status?: string;
    review?: string;
    resourceType?: string;
    resourceId?: string;
  }>;
}) {
  const context = await getProductContext();
  if (context.state !== "ready") return null;
  if (context.account.role === "clinician_pending")
    redirect("/clinician/pending");
  if (!context.account.privilegedAccessReady)
    redirect(productHomeForAccount(context.account));
  const query = await searchParams;
  const allowedStatus = new Set([
    "pending",
    "in_review",
    "completed",
    "declined",
  ]);
  const status = allowedStatus.has(query.status ?? "")
    ? (query.status as ClinicianReview["status"])
    : undefined;
  const queue = await load(listClinicianReviews(status));
  const selected = query.review
    ? await load(getClinicianReview(query.review))
    : null;
  const selectedResource: ResourceRef | null =
    query.resourceType &&
    query.resourceId &&
    ["scan_session", "report", "lesion", "analysis_run"].includes(
      query.resourceType,
    )
      ? {
          resourceType: query.resourceType as ResourceRef["resourceType"],
          resourceId: query.resourceId,
        }
      : null;
  const resource =
    selected?.ok && selectedResource
      ? await load(
          getClinicianReviewResource(selected.value.reviewId, selectedResource),
        )
      : null;
  return (
    <div className="workspace-page clinician-workspace">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Clinical review</p>
          <h1>Patient-authorized records.</h1>
          <p>
            Only active grants appear here. Stoma3D has no patient directory and
            does not allow open-ended record search.
          </p>
        </div>
      </header>
      <nav className="review-filters" aria-label="Review status">
        <Link
          href="/clinician/reviews"
          aria-current={!status ? "page" : undefined}
        >
          All
        </Link>
        {(["pending", "in_review", "completed", "declined"] as const).map(
          (value) => (
            <Link
              key={value}
              href={`/clinician/reviews?status=${value}`}
              aria-current={status === value ? "page" : undefined}
            >
              {readableLabel(value)}
            </Link>
          ),
        )}
      </nav>
      <div className="review-grid">
        <section className="review-queue" aria-labelledby="queue-title">
          <header>
            <h2 id="queue-title">Review queue</h2>
            <span>{queue.ok ? queue.value.items.length : 0} loaded</span>
          </header>
          {!queue.ok ? (
            <WorkspaceState
              title="The review queue could not be loaded."
              body="No patient information is shown when authorization cannot be checked."
            />
          ) : queue.value.items.length === 0 ? (
            <WorkspaceState
              title="No patient-authorized reviews."
              body="A review appears only after a patient grants this account access to specific records."
            />
          ) : (
            <ol className="review-queue-list">
              {queue.value.items.map((review) => (
                <li key={review.reviewId}>
                  <Link
                    href={`/clinician/reviews?review=${review.reviewId}${status ? `&status=${status}` : ""}`}
                    aria-current={
                      selected?.ok &&
                      selected.value.reviewId === review.reviewId
                        ? "page"
                        : undefined
                    }
                  >
                    <span>{readableLabel(review.status)}</span>
                    <strong>Patient {review.patientUserId.slice(-8)}</strong>
                    <small>
                      {review.resources.length} shared records. Expires{" "}
                      {readableDate(review.grantExpiresAt)}
                    </small>
                  </Link>
                </li>
              ))}
            </ol>
          )}
        </section>
        <aside className="review-detail" aria-labelledby="review-detail-title">
          {!selected ? (
            <WorkspaceState
              title="Choose a review"
              body="Capture information, limitations, provenance, and clinician notes stay together."
            />
          ) : !selected.ok ? (
            <WorkspaceState
              title="This review is unavailable."
              body="The patient grant may have expired or been revoked."
            />
          ) : (
            <>
              <header className="review-detail__heading">
                <div>
                  <p className="workspace-kicker">Selected review</p>
                  <h2 id="review-detail-title">
                    Patient {selected.value.patientUserId.slice(-8)}
                  </h2>
                </div>
                <span>{readableLabel(selected.value.status)}</span>
              </header>
              <dl className="review-detail__ledger">
                <div>
                  <dt>Granted until</dt>
                  <dd>{readableDate(selected.value.grantExpiresAt)}</dd>
                </div>
                <div>
                  <dt>Records</dt>
                  <dd>{selected.value.resources.length}</dd>
                </div>
                <div>
                  <dt>Annotations</dt>
                  <dd>{selected.value.annotations.length}</dd>
                </div>
              </dl>
              <nav className="review-resource-tabs" aria-label="Shared records">
                {selected.value.resources.map((item) => (
                  <Link
                    key={`${item.resourceType}:${item.resourceId}`}
                    href={`/clinician/reviews?review=${selected.value.reviewId}&resourceType=${item.resourceType}&resourceId=${encodeURIComponent(item.resourceId)}`}
                    aria-current={
                      selectedResource?.resourceType === item.resourceType &&
                      selectedResource.resourceId === item.resourceId
                        ? "page"
                        : undefined
                    }
                  >
                    {readableLabel(item.resourceType)}
                  </Link>
                ))}
              </nav>
              {resource?.ok ? (
                <AuthorizedResourceView
                  resource={resource.value}
                  headingLevel="h3"
                  reportContentHref={
                    selectedResource?.resourceType === "report"
                      ? `/api/clinician/reviews/${encodeURIComponent(selected.value.reviewId)}/reports/${encodeURIComponent(selectedResource.resourceId)}/content`
                      : undefined
                  }
                />
              ) : selectedResource ? (
                <WorkspaceState
                  title="This shared record could not be opened."
                  body="Access was not expanded beyond the patient grant."
                />
              ) : null}
              {resource?.ok && selectedResource ? (
                <>
                  <OutlineAdjustmentEditor
                    reviewId={selected.value.reviewId}
                    resource={selectedResource}
                    resourceView={resource.value}
                    annotations={selected.value.annotations}
                    operationKey={crypto.randomUUID()}
                  />
                  <AnnotationForm
                    reviewId={selected.value.reviewId}
                    resource={selectedResource}
                    operationKey={crypto.randomUUID()}
                  />
                </>
              ) : null}
              {selected.value.annotations.length ? (
                <section
                  className="annotation-list"
                  aria-labelledby="annotations-title"
                >
                  <h3 id="annotations-title">Recorded annotations</h3>
                  <ol>
                    {selected.value.annotations.map((annotation) => {
                      const outline =
                        annotation.kind === "outline_adjustment"
                          ? parseOutlineAdjustment(annotation.body)
                          : null;
                      return (
                        <li key={annotation.annotationId}>
                          <span>{readableLabel(annotation.kind)}</span>
                          <p>
                            {outline
                              ? `${readableLabel(outline.region)} outline · ${outline.polygon.length} clinician-set points`
                              : annotation.body}
                          </p>
                          {outline?.note ? (
                            <p className="annotation-list__note">
                              {outline.note}
                            </p>
                          ) : null}
                          <small>{readableDate(annotation.createdAt)}</small>
                        </li>
                      );
                    })}
                  </ol>
                </section>
              ) : null}
              <ReviewStatusForm
                review={selected.value}
                operationKey={crypto.randomUUID()}
              />
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
