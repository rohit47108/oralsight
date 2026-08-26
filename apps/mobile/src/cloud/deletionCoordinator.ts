import type { DeletionResponse } from "./contracts";
import {
  deletionReceiptFromResponse,
  type DeletionPollingReceipt,
  type DeletionReceiptReadResult,
} from "./deletionReceipt";

export type DeletionResumeOutcome =
  | { mode: "normal" }
  | {
      mode: "deletion_pending";
      receipt: DeletionPollingReceipt | null;
      error: string | null;
    }
  | {
      mode: "deletion_completed";
      receipt: DeletionPollingReceipt;
    };

export interface DeletionResumeDependencies {
  readReceipt(): Promise<DeletionReceiptReadResult>;
  pollStatus(requestId: string): Promise<DeletionResponse>;
  persistReceipt(receipt: DeletionPollingReceipt): Promise<void>;
  finalizeCompleted(receipt: DeletionPollingReceipt): Promise<void>;
}

export type DeletionProtectionOutcome =
  | { kind: "protected"; receipt: DeletionPollingReceipt }
  | { kind: "untrackable"; error: string };

export async function protectRequestedDeletion(options: {
  accountId: string;
  response: DeletionResponse;
  persistReceipt(receipt: DeletionPollingReceipt): Promise<void>;
  abandonUntrackableDeletion(): Promise<void>;
}): Promise<DeletionProtectionOutcome> {
  const receipt = deletionReceiptFromResponse(
    options.accountId,
    options.response,
  );
  try {
    await options.persistReceipt(receipt);
    return { kind: "protected", receipt };
  } catch {
    await options.abandonUntrackableDeletion();
    return {
      kind: "untrackable",
      error:
        "Cloud deletion was accepted, but this device could not protect its status receipt. The cloud session was removed to prevent automatic account recreation.",
    };
  }
}

export async function guardUnreceiptedServerDeletion(
  account: { id: string; deletionPending: boolean },
  abandonCloudSession: (accountId: string) => Promise<void>,
): Promise<{ kind: "normal" } | { kind: "blocked"; error: string }> {
  if (!account.deletionPending) return { kind: "normal" };
  await abandonCloudSession(account.id);
  return {
    kind: "blocked",
    error:
      "Cloud deletion is already pending, but this device has no protected status receipt. The cloud session was removed to prevent automatic account recreation.",
  };
}

function pending(
  receipt: DeletionPollingReceipt | null,
  error: string | null,
): DeletionResumeOutcome {
  return { mode: "deletion_pending", receipt, error };
}

async function finalize(
  receipt: DeletionPollingReceipt,
  finalizeCompleted: DeletionResumeDependencies["finalizeCompleted"],
): Promise<DeletionResumeOutcome> {
  try {
    await finalizeCompleted(receipt);
    return { mode: "deletion_completed", receipt };
  } catch {
    return pending(
      receipt,
      "Cloud data was deleted, but protected device cleanup is incomplete. Retry the status check.",
    );
  }
}

/**
 * Resolves a durable deletion receipt before callers are allowed to perform
 * any normal account bootstrap work. Every non-normal outcome is fail-closed.
 */
export async function resumePendingDeletion(
  dependencies: DeletionResumeDependencies,
): Promise<DeletionResumeOutcome> {
  let read: DeletionReceiptReadResult;
  try {
    read = await dependencies.readReceipt();
  } catch {
    return pending(
      null,
      "The protected cloud-deletion receipt could not be opened. Cloud features remain paused until you retry.",
    );
  }

  if (read.kind === "missing") return { mode: "normal" };
  if (read.kind === "invalid") {
    return pending(
      null,
      "The protected cloud-deletion receipt is unreadable. Cloud features remain paused to prevent account recreation.",
    );
  }

  const stored = read.receipt;
  if (stored.status === "completed") {
    return finalize(stored, dependencies.finalizeCompleted);
  }

  let response: DeletionResponse;
  try {
    response = await dependencies.pollStatus(stored.requestId);
  } catch {
    return pending(
      stored,
      "Cloud deletion status could not be checked. Cloud features remain paused; retry when the service is reachable.",
    );
  }

  if (
    response.requestId !== stored.requestId ||
    response.jobId !== stored.jobId ||
    response.requestedAt !== stored.requestedAt
  ) {
    return pending(
      stored,
      "The cloud returned a mismatched deletion receipt. Cloud features remain paused.",
    );
  }

  const refreshed = deletionReceiptFromResponse(stored.accountId, response);
  try {
    await dependencies.persistReceipt(refreshed);
  } catch {
    return pending(
      stored,
      "The refreshed deletion status could not be protected on this device. Cloud features remain paused.",
    );
  }

  if (refreshed.status === "completed") {
    return finalize(refreshed, dependencies.finalizeCompleted);
  }
  if (refreshed.status === "failed") {
    return pending(
      refreshed,
      "Cloud deletion reported a problem. Retry the status check; cloud features remain paused.",
    );
  }
  return pending(refreshed, null);
}
