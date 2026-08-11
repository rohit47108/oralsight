"use client";

import { useActionState, useState } from "react";

import {
  saveAnalyticsConsent,
  type AnalyticsConsentState,
} from "@/app/app/settings/actions";
import { readableDate } from "@/lib/presentation";

const initialActionState: AnalyticsConsentState = {
  status: "idle",
  message: "",
};

type AnalyticsConsentFormProps = {
  initialEnabled: boolean;
  initialUpdatedAt: string | null;
};

export function AnalyticsConsentForm({
  initialEnabled,
  initialUpdatedAt,
}: AnalyticsConsentFormProps) {
  const [state, action, pending] = useActionState(
    saveAnalyticsConsent,
    initialActionState,
  );
  const [enabled, setEnabled] = useState(initialEnabled);

  const updatedAt = state.updatedAt ?? initialUpdatedAt;
  return (
    <form className="analytics-consent" action={action}>
      <div className="analytics-consent__choice">
        <div>
          <label htmlFor="analytics-enabled">
            Share private product analytics
          </label>
          <p>
            OralSight can record which feature was used and whether an action
            finished, failed, or was cancelled. Images, record IDs, report
            content, symptoms, model outputs, and free text are never included.
          </p>
        </div>
        <input
          id="analytics-enabled"
          name="analyticsEnabled"
          type="checkbox"
          role="switch"
          checked={enabled}
          onChange={(event) => setEnabled(event.currentTarget.checked)}
          disabled={pending}
        />
      </div>
      <div className="analytics-consent__footer">
        <p>
          This starts off. Accepted events expire after 30 days, and groups
          smaller than five are not shown in summaries.
          {updatedAt ? ` Last changed ${readableDate(updatedAt)}.` : ""}
        </p>
        <button
          className="button button--compact"
          type="submit"
          disabled={pending}
        >
          {pending ? "Saving..." : "Save privacy setting"}
        </button>
      </div>
      {state.status !== "idle" ? (
        <p
          className="form-message"
          data-state={state.status}
          role={state.status === "error" ? "alert" : "status"}
        >
          {state.message}
        </p>
      ) : null}
    </form>
  );
}
