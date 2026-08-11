import { describe, expect, it } from "vitest";

import {
  analyticsEventSchema,
  jobResponseSchema,
  syncPullResponseSchema,
} from "../src/cloud/contracts";

describe("mobile cloud boundary contracts", () => {
  it("accepts only the identifier-free analytics shape", () => {
    const event = analyticsEventSchema.parse({
      name: "scan_completed",
      platform: "ios",
      appVersion: "0.1.0",
      surface: "scan",
      outcome: "completed",
    });
    expect(event.name).toBe("scan_completed");
    expect(
      analyticsEventSchema.safeParse({ ...event, captureId: "not-allowed" })
        .success,
    ).toBe(false);
  });

  it("validates the final durable-job result fields", () => {
    const parsed = jobResponseSchema.parse({
      jobId: "11111111-1111-4111-8111-111111111111",
      ownerId: "22222222-2222-4222-8222-222222222222",
      type: "report",
      status: "succeeded",
      inputRefs: ["33333333-3333-4333-8333-333333333333"],
      outputRefs: ["44444444-4444-4444-8444-444444444444"],
      progress: 1,
      attempt: 1,
      maxAttempts: 3,
      errorCode: null,
      errorMessage: null,
      createdAt: "2026-08-06T20:00:00.000Z",
      startedAt: "2026-08-06T20:00:01.000Z",
      completedAt: "2026-08-06T20:00:02.000Z",
      expiresAt: "2026-08-07T20:00:00.000Z",
      outcome: "complete",
      reasonCode: null,
      result: {
        report: { artifactId: "44444444-4444-4444-8444-444444444444" },
      },
      cancellationRequested: false,
    });
    expect(parsed.outcome).toBe("complete");
  });

  it("accepts server-sequenced operations returned by sync pull", () => {
    const parsed = syncPullResponseSchema.parse({
      operations: [
        {
          contractVersion: "2.0.0",
          operationId: "operation-1",
          idempotencyKey: "idempotency-key-0001",
          deviceId: "device-1",
          entityType: "observation",
          entityId: "observation-1",
          version: 1,
          sequence: 3,
          occurredAt: "2026-08-06T20:00:00.000Z",
          operation: "upsert",
          encryptedPayload: "encrypted-payload",
          tombstone: false,
          serverSequence: 9,
        },
      ],
      cursor: {
        contractVersion: "2.0.0",
        cursor: "cursor-value-0001",
        highWatermark: 9,
        issuedAt: "2026-08-06T20:00:00.000Z",
        expiresAt: "2026-08-07T20:00:00.000Z",
      },
      hasMore: false,
    });

    expect(parsed.operations[0]?.serverSequence).toBe(9);
  });
});
