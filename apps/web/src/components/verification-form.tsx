"use client";

import { useActionState } from "react";

import {
  submitVerificationAction,
  type VerificationActionState,
} from "@/app/clinician/verification/actions";

const initialState: VerificationActionState = { status: "idle" };

export function VerificationForm({ operationKey }: { operationKey: string }) {
  const [state, action, pending] = useActionState(
    submitVerificationAction,
    initialState,
  );
  if (state.status === "submitted") {
    return (
      <div className="form-success" role="status">
        <span aria-hidden="true">✓</span>
        <div>
          <h2>Credential review requested</h2>
          <p>
            Professional access stays locked until an administrator records a
            decision.
          </p>
        </div>
      </div>
    );
  }
  return (
    <form className="verification-form" action={action}>
      <input type="hidden" name="operationKey" value={operationKey} />
      <fieldset disabled={pending}>
        <legend>Professional credentials</legend>
        <div className="field-grid">
          <label>
            Profession
            <input name="profession" required minLength={2} maxLength={80} />
          </label>
          <label>
            License jurisdiction
            <input
              name="licenseJurisdiction"
              required
              minLength={2}
              maxLength={80}
            />
          </label>
          <label>
            License number
            <input
              name="licenseNumber"
              required
              minLength={4}
              maxLength={80}
              autoComplete="off"
            />
          </label>
          <label>
            Organization <span>Optional</span>
            <input name="organization" maxLength={160} />
          </label>
        </div>
        <label>
          Credential evidence reference
          <input
            name="applicantEvidenceRef"
            required
            minLength={4}
            maxLength={160}
            aria-describedby="evidence-help"
          />
        </label>
        <p id="evidence-help" className="field-help">
          Enter the secure reference supplied by the verification administrator.
          Do not paste a password or access token.
        </p>
        <button className="button" type="submit" disabled={!operationKey}>
          {pending ? "Submitting…" : "Submit for review"}
        </button>
      </fieldset>
      {state.status === "error" ? (
        <p className="form-message" role="alert" data-state="error">
          {state.message}
        </p>
      ) : null}
    </form>
  );
}
