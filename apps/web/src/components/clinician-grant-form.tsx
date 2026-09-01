"use client";

import { useActionState } from "react";

import {
  createGrantAction,
  type GrantActionState,
} from "@/app/app/share/actions";
import type { ShareableRecordOption } from "@/components/share-builder";

const initialState: GrantActionState = { status: "idle" };

export function ClinicianGrantForm({
  recordOptions,
  operationKey,
}: {
  recordOptions: ShareableRecordOption[];
  operationKey: string;
}) {
  const [state, action, pending] = useActionState(
    createGrantAction,
    initialState,
  );
  return (
    <form className="clinician-grant-form" action={action}>
      <input type="hidden" name="operationKey" value={operationKey} />
      <fieldset disabled={pending}>
        <legend>Send to a verified Stoma3D clinician</legend>
        <div className="field-grid">
          <label>
            Clinician account ID
            <input
              name="clinicianUserId"
              required
              maxLength={64}
              autoComplete="off"
            />
          </label>
          {recordOptions.length ? (
            <label>
              Record
              <select
                name="resourceChoice"
                defaultValue={JSON.stringify({
                  resourceType: recordOptions[0].resourceType,
                  resourceId: recordOptions[0].resourceId,
                })}
              >
                {recordOptions.map((option) => (
                  <option
                    key={`${option.resourceType}:${option.resourceId}`}
                    value={JSON.stringify({
                      resourceType: option.resourceType,
                      resourceId: option.resourceId,
                    })}
                  >
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label>
            Label <span>Optional</span>
            <input
              name="label"
              maxLength={120}
              placeholder="Example: September follow-up"
            />
          </label>
        </div>
        <details className="manual-resource" open={!recordOptions.length}>
          <summary>
            {recordOptions.length
              ? "Use a different record ID"
              : "Enter a record ID"}
          </summary>
          <div>
            <label>
              Record type
              <select name="manualResourceType" defaultValue="report">
                <option value="report">Report</option>
                <option value="scan_session">Scan session</option>
                <option value="lesion">Confirmed observation timeline</option>
                <option value="analysis_run">Analysis record</option>
              </select>
            </label>
            <label>
              Record ID
              <input
                name="manualResourceId"
                required={!recordOptions.length}
                maxLength={64}
                autoComplete="off"
              />
            </label>
          </div>
        </details>
        <p className="field-help">
          The platform verifies the clinician account before creating the
          review. Default access expires automatically.
        </p>
        <button className="button" type="submit" disabled={!operationKey}>
          {pending ? "Granting access…" : "Grant review access"}
        </button>
      </fieldset>
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
