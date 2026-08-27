"use client";

import { useEffect, useRef, useState } from "react";

type ExchangeState =
  { status: "opening" } | { status: "error"; message: string };

export function ShareExchange({ shareId }: { shareId: string }) {
  const [state, setState] = useState<ExchangeState>({ status: "opening" });
  const [attempt, setAttempt] = useState(0);
  const operationKey = useRef<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function openShare() {
      try {
        setState({ status: "opening" });
        await Promise.resolve();
        const fragment = new URLSearchParams(window.location.hash.slice(1));
        const secret = fragment.get("secret");
        if (!secret) throw new Error("This share link is incomplete.");
        operationKey.current ??= crypto.randomUUID();
        const response = await fetch("/api/shared/exchange", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            shareId,
            secret,
            operationKey: operationKey.current,
          }),
          cache: "no-store",
          signal: controller.signal,
        });
        const payload = (await response.json().catch(() => null)) as {
          message?: string;
        } | null;
        if (!response.ok) {
          throw new Error(
            payload?.message ?? "This shared record could not be opened.",
          );
        }
        window.location.replace("/shared?opened=1");
      } catch (error) {
        if (controller.signal.aborted) return;
        setState({
          status: "error",
          message:
            error instanceof Error
              ? error.message
              : "This shared record could not be opened.",
        });
      }
    }
    void openShare();
    return () => controller.abort();
  }, [attempt, shareId]);

  return (
    <div className="shared-exchange" aria-live="polite">
      {state.status === "opening" ? (
        <>
          <span className="workspace-spinner" aria-hidden="true" />
          <h1>Opening the shared record…</h1>
          <p>The link is being checked before any record is shown.</p>
        </>
      ) : (
        <>
          <span className="workspace-state__icon" aria-hidden="true">
            !
          </span>
          <h1>Shared record unavailable</h1>
          <p>{state.message}</p>
          <button
            className="button"
            type="button"
            onClick={() => setAttempt((value) => value + 1)}
          >
            Try again
          </button>
        </>
      )}
    </div>
  );
}
