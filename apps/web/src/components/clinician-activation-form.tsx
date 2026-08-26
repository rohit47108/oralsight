"use client";

import { useActionState } from "react";

import {
  activateClinicianAction,
  type ActivationState,
} from "@/app/clinician/pending/actions";

const initialState: ActivationState = { status: "idle" };

export function ClinicianActivationForm() {
  const [state, action, pending] = useActionState(
    activateClinicianAction,
    initialState,
  );
  return (
    <form action={action} aria-busy={pending}>
      <button className="button" type="submit" disabled={pending}>
        {pending ? "Checking access..." : "Check secure access"}
      </button>
      {state.status === "error" ? (
        <p className="form-message" role="alert" data-state="error">
          {state.message}
        </p>
      ) : null}
    </form>
  );
}
