import { describe, expect, it } from "vitest";

import {
  PLATFORM_API_DISCLAIMER,
  platformApiAnalysisRunResponseSchema,
  platformApiCaptureSetResponseSchema,
  platformApiJobCreateSchema,
  platformApiJobResponseSchema,
  platformApiMatchDecisionResponseSchema,
  platformApiMatchProposalCreateSchema,
  platformApiReviewAnnotationResponseSchema,
  platformApiScanSessionResponseSchema,
  platformApiSyncOperationInputSchema,
  platformApiSyncPullResponseSchema,
} from "../src/index";

const CREATED_AT = "2026-08-08T12:00:00.000Z";
const SHA256 = "0".repeat(64);

describe("authenticated platform API wire contracts", () => {
  it("requires the consent record returned with every scan session", () => {
    const response = {
      contractVersion: "2.0.0",
      scanSessionId: "scan-1",
      consentRecordId: "consent-1",
      protocol: "standard_eight_region",
      status: "capturing",
      createdAt: CREATED_AT,
      updatedAt: CREATED_AT,
      completedAt: null,
    };

    expect(platformApiScanSessionResponseSchema.parse(response)).toEqual(
      response,
    );
    const { consentRecordId: _omitted, ...withoutConsent } = response;
    expect(
      platformApiScanSessionResponseSchema.safeParse(withoutConsent).success,
    ).toBe(false);
  });

  it("preserves the upload state on public capture assets", () => {
    const response = {
      contractVersion: "2.0.0",
      captureSetId: "capture-set-1",
      scanSessionId: "scan-1",
      region: "dorsal_tongue",
      protocol: "standard_eight_region",
      primaryViewId: "view-1",
      views: [
        {
          captureViewId: "view-1",
          captureSetId: "capture-set-1",
          region: "dorsal_tongue",
          anatomicalSite: "dorsal_tongue",
          angle: "straight",
          asset: {
            assetId: "asset-1",
            mediaKind: "image",
            mimeType: "image/jpeg",
            byteSize: 24_000,
            sha256: SHA256,
            widthPx: 1_200,
            heightPx: 900,
            durationMs: null,
            inputOrigin: "live_capture",
            encrypted: true,
            createdAt: CREATED_AT,
            retentionExpiresAt: null,
            uploadStatus: "available",
          },
          sourceVideoAssetId: null,
          qualityAccepted: true,
          qualityReasons: [],
          ordinal: 0,
          capturedAt: CREATED_AT,
        },
      ],
      complete: true,
      createdAt: CREATED_AT,
      updatedAt: CREATED_AT,
    };

    expect(
      platformApiCaptureSetResponseSchema.parse(response).views[0]?.asset
        .uploadStatus,
    ).toBe("available");
  });

  it("models durable job result and cancellation metadata", () => {
    const response = {
      jobId: "job-1",
      ownerId: "patient-1",
      type: "delete_all",
      status: "succeeded",
      inputRefs: [],
      outputRefs: [],
      progress: 1,
      attempt: 1,
      maxAttempts: 5,
      errorCode: null,
      errorMessage: null,
      createdAt: CREATED_AT,
      startedAt: CREATED_AT,
      completedAt: CREATED_AT,
      expiresAt: "2026-09-01T12:00:00.000Z",
      outcome: "complete",
      reasonCode: null,
      result: { deleted: true },
      cancellationRequested: false,
    };

    expect(platformApiJobResponseSchema.parse(response).type).toBe(
      "delete_all",
    );
    expect(
      platformApiJobCreateSchema.safeParse({ type: "delete_all" }).success,
    ).toBe(false);
  });

  it("keeps every automatic match as a proposal and every decision human", () => {
    const decision = {
      decisionId: "decision-1",
      proposalId: "proposal-1",
      decision: "confirmed",
      decidedBy: "patient",
      actorId: "patient-1",
      rationale: null,
      decidedAt: CREATED_AT,
      lesionId: "lesion-1",
    };

    expect(
      platformApiMatchDecisionResponseSchema.parse(decision).lesionId,
    ).toBe("lesion-1");
    expect(
      platformApiMatchDecisionResponseSchema.safeParse({
        ...decision,
        decidedBy: "automatic_model",
      }).success,
    ).toBe(false);

    expect(
      platformApiMatchProposalCreateSchema.parse({
        currentObservationId: "observation-current",
        candidatePriorObservationId: "observation-prior",
        candidateLesionId: null,
        proposalOrigin: "user_selected",
        score: null,
        rank: null,
        modelVersions: {},
        expiresAt: null,
      }).proposalOrigin,
    ).toBe("user_selected");
    expect(
      platformApiMatchProposalCreateSchema.safeParse({
        currentObservationId: "observation-current",
        candidatePriorObservationId: "observation-prior",
        candidateLesionId: null,
        proposalOrigin: "automatic_model",
        score: null,
        rank: null,
        modelVersions: {},
        expiresAt: null,
      }).success,
    ).toBe(false);
  });

  it("uses the complete clinician annotation taxonomy", () => {
    expect(
      platformApiReviewAnnotationResponseSchema.parse({
        annotationId: "annotation-1",
        reviewId: "review-1",
        clinicianUserId: "clinician-1",
        resource: { resourceType: "report", resourceId: "report-1" },
        kind: "outline_adjustment",
        body: "The outlined edge should stop before the glare region.",
        createdAt: CREATED_AT,
        retentionExpiresAt: "2033-08-08T12:00:00.000Z",
      }).kind,
    ).toBe("outline_adjustment");
  });

  it("does not invent an annotation entity in encrypted sync", () => {
    expect(
      platformApiSyncOperationInputSchema.safeParse({
        contractVersion: "2.0.0",
        operationId: "operation-1",
        idempotencyKey: "idempotency-key-1",
        deviceId: "device-1",
        entityType: "annotation",
        entityId: "annotation-1",
        version: 1,
        sequence: 0,
        occurredAt: CREATED_AT,
        operation: "delete",
        encryptedPayload: null,
        tombstone: true,
      }).success,
    ).toBe(false);

    expect(
      platformApiSyncPullResponseSchema.safeParse({
        operations: [
          {
            contractVersion: "2.0.0",
            operationId: "operation-1",
            idempotencyKey: "idempotency-key-1",
            deviceId: "device-1",
            entityType: "observation",
            entityId: "observation-1",
            version: 1,
            sequence: 0,
            occurredAt: CREATED_AT,
            operation: "delete",
            encryptedPayload: null,
            tombstone: true,
            serverSequence: 1,
          },
        ],
        cursor: {
          contractVersion: "2.0.0",
          cursor: "cursor-value-0001",
          highWatermark: 1,
          issuedAt: CREATED_AT,
          expiresAt: "2026-08-09T12:00:00.000Z",
        },
        hasMore: false,
      }).success,
    ).toBe(true);
  });

  it("requires the complete signed analysis response provenance", () => {
    const response = {
      contractVersion: "2.0.0",
      analysisRunId: "analysis-1",
      captureSetId: "capture-set-1",
      requestedHeads: ["segmentation", "anatomy"],
      status: "abstained",
      observations: [],
      inputOrigin: "live_capture",
      analysisOrigin: "live_model",
      sourceAssetSha256: [SHA256],
      modelVersions: { segmentation: "segmentation-1" },
      artifactHashes: { segmentationWeights: SHA256 },
      abstentionReasons: ["Image quality was insufficient."],
      startedAt: CREATED_AT,
      completedAt: CREATED_AT,
      persisted: true,
      signedEnvelopeId: "envelope-1",
      disclaimer: PLATFORM_API_DISCLAIMER,
    };

    expect(platformApiAnalysisRunResponseSchema.parse(response).persisted).toBe(
      true,
    );
  });
});
