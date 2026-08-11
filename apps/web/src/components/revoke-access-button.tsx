"use client";

import { useActionState } from "react";

import {
  revokeGrantAction,
  revokeShareAction,
  type RevokeActionState,
} from "@/app/app/share/actions";

const initialState: RevokeActionState = { status: "idle" };

export function RevokeAccessButton({
  kind,
  id,
  operationKey,
}: {
  kind: "share" | "grant";
  id: string;
  operationKey: string;
}) {
  const [state, action, pending] = useActionState(
    kind === "share" ? revokeShareAction : revokeGrantAction,
    initialState,
  );
  return (
    <form action={action} className="revoke-access-form">
      <input type="hidden" name="operationKey" value={operationKey} />
      <input
        type="hidden"
        name={kind === "share" ? "shareId" : "grantId"}
        value={id}
      />
      <button
        className="text-button"
        type="submit"
        disabled={pending || !operationKey || state.status === "revoked"}
      >
        {pending
          ? "Ending access…"
          : state.status === "revoked"
            ? "Access ended"
            : kind === "share"
              ? "Revoke link"
              : "End access"}
      </button>
      {state.status === "error" ? (
        <span className="revoke-access-form__error" role="alert">
          {state.message}
        </span>
      ) : null}
    </form>
  );
}
