"use client";

import { useActionState, useEffect, useState } from "react";

import {
  requestDeleteAll,
  type DeleteAccountState,
} from "@/app/app/settings/actions";

const initialState: DeleteAccountState = { status: "idle", message: "" };

export function DeleteAccountForm({ operationKey }: { operationKey: string }) {
  const [state, action, pending] = useActionState(
    requestDeleteAll,
    initialState,
  );
  const [jobStatus, setJobStatus] = useState<
    "requested" | "in_progress" | "completed" | "failed" | null
  >(null);

  useEffect(() => {
    if (state.status !== "accepted" || !state.requestId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function check() {
      try {
        const response = await fetch(
          `/api/account/deletion/${encodeURIComponent(state.requestId!)}`,
          { cache: "no-store" },
        );
        const payload = (await response.json()) as {
          status?: typeof jobStatus;
        };
        if (stopped) return;
        if (!response.ok || !payload.status) {
          timer = setTimeout(check, 6_000);
          return;
        }
        setJobStatus(payload.status);
        if (payload.status !== "completed" && payload.status !== "failed") {
          timer = setTimeout(check, 3_000);
        }
      } catch {
        if (!stopped) timer = setTimeout(check, 6_000);
      }
    }
    void check();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [state]);
  return (
    <form className="delete-account-form" action={action}>
      <input type="hidden" name="operationKey" value={operationKey} />
      <label htmlFor="delete-confirmation">
        Type <strong>DELETE</strong> to continue
      </label>
      <div>
        <input
          id="delete-confirmation"
          name="confirmation"
          autoComplete="off"
          spellCheck="false"
          disabled={pending || !operationKey || state.status === "accepted"}
          required
        />
        <button
          className="danger-button"
          type="submit"
          disabled={pending || !operationKey || state.status === "accepted"}
        >
          {pending ? "Requesting…" : "Delete all account data"}
        </button>
      </div>
      {state.status !== "idle" ? (
        <p
          className="form-message"
          data-state={state.status}
          role={state.status === "error" ? "alert" : "status"}
        >
          {state.message}
          {state.requestId ? (
            <small> Request ID: {state.requestId}</small>
          ) : null}
        </p>
      ) : null}
      {state.status === "accepted" ? (
        <div className="deletion-progress" aria-live="polite">
          <span aria-hidden="true" data-state={jobStatus ?? "requested"} />
          <div>
            <strong>
              {jobStatus === "completed"
                ? "Deletion complete"
                : jobStatus === "failed"
                  ? "Deletion needs attention"
                  : jobStatus === "in_progress"
                    ? "Removing account data"
                    : "Deletion queued"}
            </strong>
            <p>
              {jobStatus === "completed"
                ? "OralSight finished the cloud cleanup. Sign out on this device."
                : jobStatus === "failed"
                  ? "The cleanup did not finish. Keep the request ID above for support."
                  : "You can leave this page. The protected cleanup job continues on the service."}
            </p>
            {jobStatus === "completed" ? (
              <a className="text-link" href="/auth/logout">
                Sign out
              </a>
            ) : null}
          </div>
        </div>
      ) : null}
    </form>
  );
}
