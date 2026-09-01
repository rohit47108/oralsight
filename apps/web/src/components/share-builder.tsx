"use client";

import { useActionState, useMemo, useRef, useState } from "react";
import QRCode from "react-qr-code";

import {
  createShareAction,
  type ShareActionState,
} from "@/app/app/share/actions";
import { readableDate } from "@/lib/presentation";

const initialState: ShareActionState = { status: "idle" };

export type ShareableRecordOption = {
  resourceType: "scan_session" | "report" | "lesion" | "analysis_run";
  resourceId: string;
  label: string;
};

export function ShareBuilder({
  recordOptions,
  operationKey,
}: {
  recordOptions: ShareableRecordOption[];
  operationKey: string;
}) {
  const [state, action, pending] = useActionState(
    createShareAction,
    initialState,
  );
  const shareUrl = useMemo(() => {
    if (state.status !== "created" || typeof window === "undefined") return "";
    const target = new URL("/shared", window.location.origin);
    target.searchParams.set("id", state.shareId);
    target.hash = new URLSearchParams({
      secret: state.fragmentSecret,
    }).toString();
    return target.toString();
  }, [state]);
  const linkRef = useRef<HTMLInputElement>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">(
    "idle",
  );

  async function copyLink() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopyState("copied");
    } catch {
      linkRef.current?.focus();
      linkRef.current?.select();
      setCopyState("error");
    }
  }

  return (
    <section className="share-builder" aria-labelledby="share-builder-title">
      <div className="share-builder__steps" aria-hidden="true">
        <span>Choose a record</span>
        <span>Set access</span>
        <span>Create secure link</span>
      </div>
      <form action={action}>
        <input type="hidden" name="operationKey" value={operationKey} />
        <fieldset disabled={pending}>
          <legend id="share-builder-title">New time-limited share</legend>
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
                Stoma3D record ID
                <input
                  name="manualResourceId"
                  required={!recordOptions.length}
                  maxLength={64}
                  autoComplete="off"
                />
              </label>
            </div>
          </details>
          <label>
            Link expires
            <select name="expiresInSeconds" defaultValue="86400">
              <option value="86400">24 hours</option>
              <option value="259200">3 days</option>
              <option value="604800">7 days</option>
            </select>
          </label>
          <label>
            Maximum openings
            <select name="maxExchanges" defaultValue="1">
              <option value="1">1 opening</option>
              <option value="3">3 openings</option>
              <option value="5">5 openings</option>
              <option value="10">10 openings</option>
            </select>
          </label>
          <button className="button" type="submit" disabled={!operationKey}>
            {pending ? "Creating secure link…" : "Create secure link"}
          </button>
        </fieldset>
      </form>
      {state.status === "error" ? (
        <p className="form-message" role="alert" data-state="error">
          {state.message}
        </p>
      ) : null}
      {state.status === "created" && shareUrl ? (
        <div className="share-result" aria-live="polite">
          <div className="share-result__qr">
            <QRCode value={shareUrl} size={168} level="M" />
          </div>
          <div>
            <p className="workspace-kicker">Link created</p>
            <h2>Show this code or copy the link.</h2>
            <p>
              Expires {readableDate(state.expiresAt)}. It can be opened at most{" "}
              {state.maxExchanges} {state.maxExchanges === 1 ? "time" : "times"}
              .
            </p>
            <label>
              Secure share link
              <span className="share-link-field">
                <input
                  ref={linkRef}
                  readOnly
                  value={shareUrl}
                  onFocus={(event) => event.currentTarget.select()}
                />
                <button
                  className="text-button"
                  type="button"
                  onClick={copyLink}
                >
                  {copyState === "copied" ? "Copied" : "Copy link"}
                </button>
              </span>
            </label>
            <span className="sr-only" aria-live="polite">
              {copyState === "copied"
                ? "Secure share link copied."
                : copyState === "error"
                  ? "Automatic copy was unavailable. The link is selected for manual copying."
                  : ""}
            </span>
            <p className="quiet-copy">
              The secret stays after the # in this link. Stoma3D never places it
              in server logs or access history.
            </p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
