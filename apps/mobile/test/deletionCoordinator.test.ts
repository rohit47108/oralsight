import { describe, expect, it, vi } from "vitest";

import {
  DeletionReceiptRepository,
  type DeletionPollingReceipt,
} from "../src/cloud/deletionReceipt";
import {
  guardUnreceiptedServerDeletion,
  protectRequestedDeletion,
  resumePendingDeletion,
} from "../src/cloud/deletionCoordinator";

const requestedReceipt: DeletionPollingReceipt = {
  accountId: "account-1",
  requestId: "request-1",
  jobId: "job-1",
  status: "requested",
  requestedAt: "2026-08-13T12:00:00.000Z",
  startedAt: null,
  completedAt: null,
  errorCode: null,
};

function response(
  status: DeletionPollingReceipt["status"],
): Omit<DeletionPollingReceipt, "accountId"> {
  return {
    requestId: requestedReceipt.requestId,
    jobId: requestedReceipt.jobId,
    status,
    requestedAt: requestedReceipt.requestedAt,
    startedAt: status === "requested" ? null : "2026-08-13T12:00:01.000Z",
    completedAt:
      status === "completed" || status === "failed"
        ? "2026-08-13T12:00:02.000Z"
        : null,
    errorCode: status === "failed" ? "object_cleanup_failed" : null,
  };
}

describe("protectRequestedDeletion", () => {
  it("saves the restart receipt before allowing destructive local cleanup", async () => {
    const calls: string[] = [];

    const outcome = await protectRequestedDeletion({
      accountId: "account-1",
      response: response("requested"),
      persistReceipt: async () => {
        calls.push("persist");
      },
      abandonUntrackableDeletion: async () => {
        calls.push("abandon");
      },
    });

    expect(calls).toEqual(["persist"]);
    expect(outcome).toEqual({
      kind: "protected",
      receipt: requestedReceipt,
    });
  });

  it("abandons the cloud session when a server-accepted deletion cannot survive restart", async () => {
    const calls: string[] = [];
    let opaqueTokenPresent = true;

    const outcome = await protectRequestedDeletion({
      accountId: "account-1",
      response: response("requested"),
      persistReceipt: async () => {
        calls.push("persist-failed");
        throw new Error("secure storage unavailable");
      },
      abandonUntrackableDeletion: async () => {
        calls.push("clear-token");
        opaqueTokenPresent = false;
      },
    });

    expect(calls).toEqual(["persist-failed", "clear-token"]);
    expect(opaqueTokenPresent).toBe(false);
    expect(outcome).toEqual({
      kind: "untrackable",
      error:
        "Cloud deletion was accepted, but this device could not protect its status receipt. The cloud session was removed to prevent automatic account recreation.",
    });
  });
});

describe("guardUnreceiptedServerDeletion", () => {
  it("allows normal bootstrap for an active account", async () => {
    const abandonCloudSession = vi.fn();
    await expect(
      guardUnreceiptedServerDeletion(
        { id: "account-1", deletionPending: false },
        abandonCloudSession,
      ),
    ).resolves.toEqual({ kind: "normal" });
    expect(abandonCloudSession).not.toHaveBeenCalled();
  });

  it("clears the retained session before any other bootstrap work for an unreceipted pending account", async () => {
    const calls: string[] = ["account"];
    let opaqueTokenPresent = true;

    const outcome = await guardUnreceiptedServerDeletion(
      { id: "account-1", deletionPending: true },
      async (accountId) => {
        calls.push(`clear:${accountId}`);
        opaqueTokenPresent = false;
      },
    );

    expect(calls).toEqual(["account", "clear:account-1"]);
    expect(opaqueTokenPresent).toBe(false);
    expect(outcome).toEqual({
      kind: "blocked",
      error:
        "Cloud deletion is already pending, but this device has no protected status receipt. The cloud session was removed to prevent automatic account recreation.",
    });
  });
});

describe("DeletionReceiptRepository", () => {
  it("persists only the bounded deletion polling receipt", async () => {
    let stored: string | null = null;
    const repository = new DeletionReceiptRepository({
      getItem: async () => stored,
      setItem: async (_key, value) => {
        stored = value;
      },
      deleteItem: async () => {
        stored = null;
      },
    });

    await repository.write(requestedReceipt);

    expect(JSON.parse(stored!)).toEqual(requestedReceipt);
    expect(stored).not.toContain("accessToken");
    await expect(repository.read()).resolves.toEqual({
      kind: "present",
      receipt: requestedReceipt,
    });
  });

  it("fails closed on a malformed receipt without deleting evidence", async () => {
    let stored: string | null = '{"status":"requested"}';
    const deleteItem = vi.fn(async () => {
      stored = null;
    });
    const repository = new DeletionReceiptRepository({
      getItem: async () => stored,
      setItem: async (_key, value) => {
        stored = value;
      },
      deleteItem,
    });

    await expect(repository.read()).resolves.toEqual({ kind: "invalid" });
    expect(deleteItem).not.toHaveBeenCalled();
    expect(stored).not.toBeNull();
  });
});

describe("resumePendingDeletion", () => {
  it("allows normal account bootstrap only when no deletion receipt exists", async () => {
    const pollStatus = vi.fn();
    const persistReceipt = vi.fn();
    const finalizeCompleted = vi.fn();

    await expect(
      resumePendingDeletion({
        readReceipt: async () => ({ kind: "missing" }),
        pollStatus,
        persistReceipt,
        finalizeCompleted,
      }),
    ).resolves.toEqual({ mode: "normal" });
    expect(pollStatus).not.toHaveBeenCalled();
    expect(persistReceipt).not.toHaveBeenCalled();
    expect(finalizeCompleted).not.toHaveBeenCalled();
  });

  it("restores pending mode and performs only the status poll on restart", async () => {
    const calls: string[] = [];
    const refreshed = response("in_progress");

    const outcome = await resumePendingDeletion({
      readReceipt: async () => {
        calls.push("read");
        return { kind: "present", receipt: requestedReceipt };
      },
      pollStatus: async (requestId) => {
        calls.push(`poll:${requestId}`);
        return refreshed;
      },
      persistReceipt: async () => {
        calls.push("persist");
      },
      finalizeCompleted: async () => {
        calls.push("finalize");
      },
    });

    expect(calls).toEqual(["read", "poll:request-1", "persist"]);
    expect(outcome).toEqual({
      mode: "deletion_pending",
      receipt: { ...refreshed, accountId: "account-1" },
      error: null,
    });
  });

  it("persists completion before clearing credentials and local cloud state", async () => {
    const calls: string[] = [];
    const refreshed = response("completed");

    const outcome = await resumePendingDeletion({
      readReceipt: async () => {
        calls.push("read");
        return { kind: "present", receipt: requestedReceipt };
      },
      pollStatus: async () => {
        calls.push("poll");
        return refreshed;
      },
      persistReceipt: async () => {
        calls.push("persist");
      },
      finalizeCompleted: async () => {
        calls.push("finalize");
      },
    });

    expect(calls).toEqual(["read", "poll", "persist", "finalize"]);
    expect(outcome).toEqual({
      mode: "deletion_completed",
      receipt: { ...refreshed, accountId: "account-1" },
    });
  });

  it("finishes an already-completed receipt after a cleanup-interrupted restart without polling", async () => {
    const completed = {
      ...requestedReceipt,
      ...response("completed"),
    };
    const pollStatus = vi.fn();
    const persistReceipt = vi.fn();
    const finalizeCompleted = vi.fn(async () => undefined);

    await expect(
      resumePendingDeletion({
        readReceipt: async () => ({ kind: "present", receipt: completed }),
        pollStatus,
        persistReceipt,
        finalizeCompleted,
      }),
    ).resolves.toEqual({
      mode: "deletion_completed",
      receipt: completed,
    });
    expect(pollStatus).not.toHaveBeenCalled();
    expect(persistReceipt).not.toHaveBeenCalled();
    expect(finalizeCompleted).toHaveBeenCalledOnce();
  });

  it("keeps a terminal server failure in safe deletion mode for explicit retry", async () => {
    const failed = response("failed");
    const finalizeCompleted = vi.fn();

    const outcome = await resumePendingDeletion({
      readReceipt: async () => ({
        kind: "present",
        receipt: requestedReceipt,
      }),
      pollStatus: async () => failed,
      persistReceipt: async () => undefined,
      finalizeCompleted,
    });

    expect(outcome).toEqual({
      mode: "deletion_pending",
      receipt: { ...failed, accountId: "account-1" },
      error:
        "Cloud deletion reported a problem. Retry the status check; cloud features remain paused.",
    });
    expect(finalizeCompleted).not.toHaveBeenCalled();
  });

  it("fails closed when receipt storage is malformed or unavailable", async () => {
    const pollStatus = vi.fn();
    const finalizeCompleted = vi.fn();

    await expect(
      resumePendingDeletion({
        readReceipt: async () => ({ kind: "invalid" }),
        pollStatus,
        persistReceipt: vi.fn(),
        finalizeCompleted,
      }),
    ).resolves.toEqual({
      mode: "deletion_pending",
      receipt: null,
      error:
        "The protected cloud-deletion receipt is unreadable. Cloud features remain paused to prevent account recreation.",
    });

    await expect(
      resumePendingDeletion({
        readReceipt: async () => {
          throw new Error("keychain unavailable");
        },
        pollStatus,
        persistReceipt: vi.fn(),
        finalizeCompleted,
      }),
    ).resolves.toEqual({
      mode: "deletion_pending",
      receipt: null,
      error:
        "The protected cloud-deletion receipt could not be opened. Cloud features remain paused until you retry.",
    });
    expect(pollStatus).not.toHaveBeenCalled();
    expect(finalizeCompleted).not.toHaveBeenCalled();
  });

  it("rejects a mismatched status response and preserves the original receipt", async () => {
    const persistReceipt = vi.fn();
    const finalizeCompleted = vi.fn();

    const outcome = await resumePendingDeletion({
      readReceipt: async () => ({
        kind: "present",
        receipt: requestedReceipt,
      }),
      pollStatus: async () => ({
        ...response("completed"),
        requestId: "different-request",
      }),
      persistReceipt,
      finalizeCompleted,
    });

    expect(outcome).toEqual({
      mode: "deletion_pending",
      receipt: requestedReceipt,
      error:
        "The cloud returned a mismatched deletion receipt. Cloud features remain paused.",
    });
    expect(persistReceipt).not.toHaveBeenCalled();
    expect(finalizeCompleted).not.toHaveBeenCalled();
  });

  it("retains the completed receipt when local cleanup fails so restart can retry", async () => {
    const completed = response("completed");

    const outcome = await resumePendingDeletion({
      readReceipt: async () => ({
        kind: "present",
        receipt: requestedReceipt,
      }),
      pollStatus: async () => completed,
      persistReceipt: async () => undefined,
      finalizeCompleted: async () => {
        throw new Error("secure key deletion failed");
      },
    });

    expect(outcome).toEqual({
      mode: "deletion_pending",
      receipt: { ...completed, accountId: "account-1" },
      error:
        "Cloud data was deleted, but protected device cleanup is incomplete. Retry the status check.",
    });
  });
});
