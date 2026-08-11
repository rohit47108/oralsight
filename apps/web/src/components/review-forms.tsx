"use client";

import { useActionState } from "react";

import {
  createAnnotationAction,
  type ReviewActionState,
  updateReviewStatusAction,
} from "@/app/clinician/reviews/actions";
import type { ClinicianReview, ResourceRef } from "@/lib/platform-api";

const initialState: ReviewActionState = { status: "idle" };

function ActionMessage({ state }: { state: ReviewActionState }) {
  if (state.status === "idle") return null;
  return (
    <p
      className="form-message"
      role="status"
      data-state={state.status === "error" ? "error" : "saved"}
    >
      {state.message}
    </p>
  );
}

export function ReviewStatusForm({
  review,
  operationKey,
}: {
  review: ClinicianReview;
  operationKey: string;
}) {
  const [state, action, pending] = useActionState(
    updateReviewStatusAction,
    initialState,
  );
  const terminal =
    review.status === "completed" || review.status === "declined";
  return (
    <form className="review-action-form" action={action}>
      <input type="hidden" name="operationKey" value={operationKey} />
      <input type="hidden" name="reviewId" value={review.reviewId} />
      <label>
        Review summary <span>Optional until completion</span>
        <textarea
          name="summary"
          maxLength={4000}
          defaultValue={review.summary ?? ""}
        />
      </label>
      {!terminal ? (
        <div className="review-action-form__buttons">
          {review.status === "pending" ? (
            <button
              className="button"
              name="status"
              value="in_review"
              disabled={pending || !operationKey}
            >
              Start review
            </button>
          ) : (
            <button
              className="button"
              name="status"
              value="completed"
              disabled={pending || !operationKey}
            >
              Complete review
            </button>
          )}
          <button
            className="text-button"
            name="status"
            value="declined"
            disabled={pending || !operationKey}
          >
            Decline review
          </button>
        </div>
      ) : null}
      <ActionMessage state={state} />
    </form>
  );
}

export function AnnotationForm({
  reviewId,
  resource,
  operationKey,
}: {
  reviewId: string;
  resource: ResourceRef;
  operationKey: string;
}) {
  const [state, action, pending] = useActionState(
    createAnnotationAction,
    initialState,
  );
  return (
    <form className="annotation-form" action={action}>
      <input type="hidden" name="operationKey" value={operationKey} />
      <input type="hidden" name="reviewId" value={reviewId} />
      <input type="hidden" name="resourceType" value={resource.resourceType} />
      <input type="hidden" name="resourceId" value={resource.resourceId} />
      <div className="annotation-form__heading">
        <div>
          <p className="workspace-kicker">Clinician annotation</p>
          <h3>Add context to this record</h3>
        </div>
        <select name="kind" aria-label="Annotation type" defaultValue="note">
          <option value="note">Note</option>
          <option value="question">Question</option>
          <option value="follow_up">Follow-up</option>
          <option value="measurement_context">Measurement context</option>
          <option value="location_correction">Location correction</option>
          <option value="insufficient_scan">Insufficient scan</option>
          <option value="date_comparison">Date comparison</option>
        </select>
      </div>
      <textarea
        name="body"
        required
        maxLength={4000}
        placeholder="Write a concise observation for the patient-authorized record."
      />
      <p className="form-help">
        This adds context to the review. It does not change the saved analysis
        or retrain a model.
      </p>
      <button
        className="button"
        type="submit"
        disabled={pending || !operationKey}
      >
        {pending ? "Saving…" : "Save annotation"}
      </button>
      <ActionMessage state={state} />
    </form>
  );
}
