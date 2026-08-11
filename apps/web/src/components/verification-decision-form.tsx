"use client";

import { useActionState } from "react";

import {
  decideVerificationAction,
  type DecisionState,
} from "@/app/clinician/admin/actions";

const initialState: DecisionState = { status: "idle" };

export function VerificationDecisionForm({
  verificationId,
  operationKey,
}: {
  verificationId: string;
  operationKey: string;
}) {
  const [state, action, pending] = useActionState(
    decideVerificationAction,
    initialState,
  );
  return (
    <form className="verification-decision-form" action={action}>
      <input type="hidden" name="operationKey" value={operationKey} />
      <input type="hidden" name="verificationId" value={verificationId} />
      <div className="field-grid">
        <label>
          Evidence source
          <input name="source" required maxLength={160} />
        </label>
        <label>
          Evidence reference
          <input name="referenceId" required minLength={4} maxLength={160} />
        </label>
      </div>
      <label>
        Reviewer notes <span>Optional</span>
        <textarea name="reviewerNotes" maxLength={1000} />
      </label>
      <label>
        Rejection reason <span>Required only when rejecting</span>
        <textarea name="decisionReason" maxLength={500} />
      </label>
      <div className="review-action-form__buttons">
        <button
          className="button"
          name="status"
          value="verified"
          disabled={pending || !operationKey}
        >
          Verify clinician
        </button>
        <button
          className="text-button"
          name="status"
          value="rejected"
          disabled={pending || !operationKey}
        >
          Reject request
        </button>
      </div>
      {state.status !== "idle" ? (
        <p
          className="form-message"
          role="status"
          data-state={state.status === "error" ? "error" : "saved"}
        >
          {state.message}
        </p>
      ) : null}
    </form>
  );
}
