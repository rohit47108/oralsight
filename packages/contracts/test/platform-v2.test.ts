import { describe, expect, it } from "vitest";

import {
  CONTRACT_VERSION,
  DISCLAIMER,
  MOUTH_REGIONS,
  PLATFORM_CONTRACT_VERSION,
  analysisRunSchema,
  calibrationResultSchema,
  captureSetSchema,
  jobSchema,
  matchDecisionSchema,
  matchProposalSchema,
  reportArtifactSchema,
  ruleReleaseSchema,
  shareGrantSchema,
  signedResultEnvelopeSchema,
  syncOperationSchema,
} from "../src/index";

const SHA256 = "0".repeat(64);
const SIGNATURE = "A".repeat(43);
const CREATED_AT = "2026-08-04T12:00:00.000Z";

function captureAsset(assetId: string, mediaKind = "image" as const) {
  return {
    assetId,
    mediaKind,
    mimeType: "image/jpeg",
    byteSize: 24_000,
    sha256: SHA256,
    widthPx: 1_200,
    heightPx: 900,
    durationMs: null,
    inputOrigin: "live_capture" as const,
    encrypted: true,
    createdAt: CREATED_AT,
    retentionExpiresAt: null,
  };
}

function captureView(
  captureViewId: string,
  angle: "straight" | "left_oblique" | "right_oblique",
) {
  return {
    captureViewId,
    captureSetId: "capture-set-1",
    region: "dorsal_tongue" as const,
    anatomicalSite: "dorsal_tongue" as const,
    angle,
    asset: captureAsset(`asset-${captureViewId}`),
    sourceVideoAssetId: null,
    qualityAccepted: true,
    qualityReasons: [],
    ordinal: 0,
    capturedAt: CREATED_AT,
  };
}

describe("Stoma3D platform contract v2", () => {
  it("is additive and leaves the canonical v1 region contract unchanged", () => {
    expect(CONTRACT_VERSION).toBe("1.1.0");
    expect(PLATFORM_CONTRACT_VERSION).toBe("2.0.0");
    expect(MOUTH_REGIONS).toEqual([
      "dorsal_tongue",
      "ventral_tongue",
      "left_buccal_mucosa",
      "right_buccal_mucosa",
      "upper_lip",
      "lower_lip",
      "upper_dental_arch",
      "lower_dental_arch",
    ]);
  });

  it("requires all three accepted angles before a detailed capture is complete", () => {
    const views = [
      captureView("view-straight", "straight"),
      captureView("view-left", "left_oblique"),
      captureView("view-right", "right_oblique"),
    ];
    const valid = {
      contractVersion: PLATFORM_CONTRACT_VERSION,
      captureSetId: "capture-set-1",
      scanSessionId: "scan-1",
      region: "dorsal_tongue" as const,
      protocol: "detailed_multi_angle" as const,
      primaryViewId: "view-straight",
      views,
      complete: true,
      createdAt: CREATED_AT,
      updatedAt: CREATED_AT,
    };

    expect(captureSetSchema.parse(valid).views).toHaveLength(3);
    expect(() =>
      captureSetSchema.parse({ ...valid, views: views.slice(0, 2) }),
    ).toThrow(/straight, left, and right/i);
  });

  it("keeps every millimeter estimate null unless calibration is valid", () => {
    const invalid = {
      calibrationId: "calibration-1",
      captureViewId: "view-1",
      status: "invalid" as const,
      method: "versioned_reference_card" as const,
      cardVersion: "1",
      markerId: "marker-1",
      referenceWidthMm: null,
      millimetersPerPixel: null,
      estimatedWidthMm: null,
      estimatedHeightMm: null,
      estimatedAreaMm2: null,
      confidence: 0.2,
      gateReasons: ["Marker and tissue were not in a comparable plane."],
      calibratedAt: CREATED_AT,
      modelVersions: { calibration: "1.0.0" },
      measurementLabel: "calibrated estimate" as const,
    };

    expect(calibrationResultSchema.parse(invalid).estimatedWidthMm).toBeNull();
    expect(() =>
      calibrationResultSchema.parse({ ...invalid, estimatedWidthMm: 4.2 }),
    ).toThrow(/millimeter values/i);

    expect(
      calibrationResultSchema.parse({
        ...invalid,
        status: "valid",
        referenceWidthMm: 20,
        millimetersPerPixel: 0.04,
        estimatedWidthMm: 4.2,
        estimatedHeightMm: 3.5,
        estimatedAreaMm2: 11.4,
        confidence: 0.94,
        gateReasons: [],
      }).estimatedWidthMm,
    ).toBe(4.2);
  });

  it("represents automatic matching only as a proposal requiring a human decision", () => {
    const proposal = {
      proposalId: "proposal-1",
      currentObservationId: "observation-current",
      candidatePriorObservationId: "observation-prior",
      candidateLesionId: "lesion-1",
      proposalOrigin: "automatic_model" as const,
      score: 0.96,
      rank: 1,
      state: "proposed" as const,
      automaticallyConfirmed: false as const,
      modelVersions: { reidentification: "2.0.0" },
      generatedAt: CREATED_AT,
      expiresAt: null,
    };

    expect(matchProposalSchema.parse(proposal).state).toBe("proposed");
    expect(() =>
      matchProposalSchema.parse({ ...proposal, automaticallyConfirmed: true }),
    ).toThrow();
    expect(() =>
      matchDecisionSchema.parse({
        decisionId: "decision-1",
        proposalId: "proposal-1",
        decision: "confirmed",
        decidedBy: "automatic_model",
        actorId: "model-1",
        rationale: null,
        decidedAt: CREATED_AT,
        lesionId: null,
      }),
    ).toThrow();

    expect(
      matchProposalSchema.parse({
        ...proposal,
        proposalOrigin: "user_selected",
        score: null,
        rank: null,
        modelVersions: {},
      }).proposalOrigin,
    ).toBe("user_selected");
    expect(() =>
      matchProposalSchema.parse({
        ...proposal,
        proposalOrigin: "user_selected",
      }),
    ).toThrow(/require none/i);
  });

  it("caps every share grant at seven days", () => {
    const grant = {
      shareGrantId: "share-1",
      patientId: "patient-1",
      secretHash: SHA256,
      scopes: ["scan:view" as const],
      resourceIds: ["scan-1"],
      allowDownloads: false,
      maxDownloads: null,
      downloadCount: 0,
      createdAt: CREATED_AT,
      expiresAt: "2026-08-11T12:00:00.000Z",
      revokedAt: null,
    };

    expect(shareGrantSchema.parse(grant).expiresAt).toBe(grant.expiresAt);
    expect(() =>
      shareGrantSchema.parse({
        ...grant,
        expiresAt: "2026-08-11T12:00:00.001Z",
      }),
    ).toThrow(/seven days/i);
  });

  it("rejects urgency until the rule file is enabled, signed, and clinician approved", () => {
    const release = {
      contractVersion: PLATFORM_CONTRACT_VERSION,
      ruleReleaseId: "rules-1",
      version: "2026.08",
      status: "enabled" as const,
      urgencyEnabled: true,
      rulesSha256: SHA256,
      intendedUse: "Deterministic review-priority guidance.",
      limitations: ["This result is not a diagnosis."],
      clinicianApproval: null,
      signedAt: null,
      signingKeyId: null,
      signatureAlgorithm: null,
      signature: null,
      createdAt: CREATED_AT,
    };

    expect(() => ruleReleaseSchema.parse(release)).toThrow(/urgency guidance/i);
    expect(
      ruleReleaseSchema.parse({
        ...release,
        clinicianApproval: {
          clinicianId: "clinician-1",
          reviewedAt: CREATED_AT,
          scope: "Symptoms, duration, progression, quality, and uncertainty.",
          configurationSha256: SHA256,
        },
        signedAt: CREATED_AT,
        signingKeyId: "rules-key-1",
        signatureAlgorithm: "Ed25519",
        signature: SIGNATURE,
      }).urgencyEnabled,
    ).toBe(true);
  });

  it("requires signed provenance before an analysis is persisted", () => {
    const run = {
      contractVersion: PLATFORM_CONTRACT_VERSION,
      analysisRunId: "analysis-run-1",
      captureSetId: "capture-set-1",
      requestedHeads: ["segmentation" as const],
      status: "complete" as const,
      observations: [],
      inputOrigin: "live_capture" as const,
      analysisOrigin: "live_model" as const,
      sourceAssetSha256: [SHA256],
      modelVersions: { segmentation: "2.0.0" },
      artifactHashes: { segmentation_weights: SHA256 },
      abstentionReasons: [],
      startedAt: CREATED_AT,
      completedAt: CREATED_AT,
      persisted: true,
      signedEnvelopeId: null,
      disclaimer: DISCLAIMER,
    };

    expect(() => analysisRunSchema.parse(run)).toThrow(/signed provenance/i);
    expect(
      analysisRunSchema.parse({ ...run, signedEnvelopeId: "envelope-1" })
        .persisted,
    ).toBe(true);
  });

  it("requires complete origin, model, artifact, and signing provenance", () => {
    const envelope = {
      contractVersion: PLATFORM_CONTRACT_VERSION,
      envelopeId: "envelope-1",
      resultType: "analysis" as const,
      subjectId: "analysis-run-1",
      schemaId: "https://stoma3d.example/schemas/analysis-run-v2.json",
      payload: { analysisRunId: "analysis-run-1" },
      payloadSha256: SHA256,
      sourceAssetSha256: [SHA256],
      inputOrigin: "live_capture" as const,
      analysisOrigin: "live_model" as const,
      modelVersions: { segmentation: "2.0.0" },
      artifactHashes: { segmentation_weights: SHA256 },
      createdAt: CREATED_AT,
      signingKeyId: "results-key-1",
      signatureAlgorithm: "Ed25519" as const,
      signature: SIGNATURE,
    };

    expect(signedResultEnvelopeSchema.parse(envelope).envelopeId).toBe(
      "envelope-1",
    );
    expect(() =>
      signedResultEnvelopeSchema.parse({ ...envelope, modelVersions: {} }),
    ).toThrow(/model-version provenance/i);
    expect(() =>
      signedResultEnvelopeSchema.parse({
        ...envelope,
        analysisOrigin: "manual_fixture",
      }),
    ).toThrow(/bundled input/i);
  });

  it("models deletion sync as an explicit tombstone", () => {
    const common = {
      contractVersion: PLATFORM_CONTRACT_VERSION,
      operationId: "operation-1",
      idempotencyKey: "idempotency-key-1",
      deviceId: "device-1",
      entityType: "observation" as const,
      entityId: "observation-1",
      version: 2,
      sequence: 12,
      occurredAt: CREATED_AT,
    };

    expect(
      syncOperationSchema.parse({
        ...common,
        operation: "delete",
        encryptedPayload: null,
        tombstone: true,
      }).tombstone,
    ).toBe(true);
    expect(() =>
      syncOperationSchema.parse({
        ...common,
        operation: "delete",
        encryptedPayload: "encrypted medical data",
        tombstone: true,
      }),
    ).toThrow();
  });

  it("keeps jobs and report artifacts strict and provenance labelled", () => {
    expect(
      jobSchema.parse({
        jobId: "job-1",
        ownerId: "patient-1",
        type: "report",
        status: "succeeded",
        inputRefs: ["scan-1"],
        outputRefs: ["report-1"],
        progress: 1,
        attempt: 1,
        maxAttempts: 3,
        errorCode: null,
        errorMessage: null,
        createdAt: CREATED_AT,
        startedAt: CREATED_AT,
        completedAt: CREATED_AT,
        expiresAt: "2026-09-03T12:00:00.000Z",
        outcome: "complete",
        reasonCode: null,
        result: { report: { reportArtifactId: "report-1" } },
        cancellationRequested: false,
      }).status,
    ).toBe("succeeded");

    const report = {
      contractVersion: PLATFORM_CONTRACT_VERSION,
      reportArtifactId: "report-1",
      patientId: "patient-1",
      scanSessionIds: ["scan-1"],
      format: "pdf" as const,
      assetId: "asset-report-1",
      sha256: SHA256,
      byteSize: 120_000,
      locale: "en-US",
      accessible: true,
      inputOrigins: ["live_capture" as const],
      analysisOrigins: ["live_model" as const],
      modelVersions: { segmentation: "2.0.0" },
      signedEnvelopeId: "envelope-report-1",
      createdAt: CREATED_AT,
      retentionExpiresAt: null,
      disclaimer: DISCLAIMER,
    };
    expect(reportArtifactSchema.parse(report).format).toBe("pdf");
    expect(() =>
      reportArtifactSchema.parse({ ...report, extra: true }),
    ).toThrow();
  });
});
