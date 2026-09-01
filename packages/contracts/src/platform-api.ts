import { z } from "zod";

/**
 * Exact camel-case wire contracts for the authenticated platform API.
 *
 * The older v2 schemas in index.ts describe persisted product records. These
 * schemas intentionally use a `platformApi` prefix so transport-only fields
 * (for example uploadStatus) are not stripped from public API responses.
 */

export const PLATFORM_API_CONTRACT_VERSION = "2.0.0" as const;
export const PLATFORM_API_DISCLAIMER =
  "This result is not a diagnosis." as const;

const idSchema = z.string().min(1).max(128);
const resourceIdSchema = z.string().min(1).max(64);
const dateSchema = z.string().datetime({ offset: true });
const sha256Schema = z.string().regex(/^[a-f0-9]{64}$/);
const encryptedPayloadSchema = z.string().min(16).max(1_000_000);

export const platformApiMouthRegionSchema = z.enum([
  "dorsal_tongue",
  "ventral_tongue",
  "left_buccal_mucosa",
  "right_buccal_mucosa",
  "upper_lip",
  "lower_lip",
  "upper_dental_arch",
  "lower_dental_arch",
]);

export const platformApiCaptureProtocolSchema = z.enum([
  "standard_eight_region",
  "detailed_multi_angle",
  "guided_video_sweep",
]);

export const platformApiCaptureAngleSchema = z.enum([
  "primary",
  "straight",
  "left_oblique",
  "right_oblique",
  "superior",
  "inferior",
]);

export const platformApiMediaKindSchema = z.enum([
  "image",
  "video",
  "video_frame",
]);
export const platformApiInputOriginSchema = z.enum([
  "live_capture",
  "bundled_demo",
]);
export const platformApiAnalysisOriginSchema = z.enum([
  "live_model",
  "cached_model_result",
  "manual_fixture",
  "unavailable",
]);
export const platformApiAnalysisStatusSchema = z.enum([
  "complete",
  "abstained",
  "unsupported",
  "failed",
]);
export const platformApiModelHeadSchema = z.enum([
  "segmentation",
  "anatomy",
  "appearance",
  "disease_research",
  "lesion_reidentification",
  "quality_control",
  "oral_tissue_segmentation",
  "out_of_distribution",
  "secondary_segmentation",
]);

export const platformApiAnatomicalSiteSchema = z.enum([
  "dorsal_tongue",
  "ventral_tongue",
  "left_lateral_tongue",
  "right_lateral_tongue",
  "floor_of_mouth",
  "hard_palate",
  "soft_palate",
  "oropharynx",
  "left_buccal_mucosa",
  "right_buccal_mucosa",
  "upper_labial_mucosa",
  "lower_labial_mucosa",
  "upper_gingiva",
  "lower_gingiva",
  "upper_teeth",
  "lower_teeth",
  "other_visible_oral_tissue",
]);

export const platformApiErrorSchema = z
  .object({
    error: z
      .object({
        code: z.string().min(1).max(128),
        message: z.string().min(1).max(1_000),
        requestId: z.string().min(1).max(128),
      })
      .strict(),
  })
  .strict();

export const platformApiMeResponseSchema = z
  .object({
    id: idSchema,
    role: z.enum([
      "patient",
      "share_viewer",
      "clinician_pending",
      "clinician",
      "admin",
    ]),
    status: z.enum(["active", "deletion_pending", "suspended"]),
    createdAt: dateSchema,
    deletionPending: z.boolean(),
    requiredOidcRole: z.enum(["clinician", "admin"]).nullable(),
    privilegedAccessReady: z.boolean(),
    clinicianApplicationEligible: z.boolean(),
  })
  .strict();

export const platformApiConsentDocumentResponseSchema = z
  .object({
    documentId: z.string().regex(/^[A-Za-z0-9._:-]{1,120}$/),
    documentVersion: z.string().regex(/^[A-Za-z0-9._:-]{1,64}$/),
    documentSha256: sha256Schema,
    title: z.string().min(1),
    body: z.string().min(1),
    withdrawalEffect: z.literal(
      "blocks_new_cloud_work_revokes_access_preserves_existing_data",
    ),
  })
  .strict();

export const platformApiConsentCreateSchema = z
  .object({
    documentId: z.string().regex(/^[A-Za-z0-9._:-]{1,120}$/),
    documentVersion: z.string().regex(/^[A-Za-z0-9._:-]{1,64}$/),
    documentSha256: sha256Schema,
    accepted: z.literal(true),
    deviceId: z.string().max(36).nullable().optional(),
  })
  .strict();

export const platformApiConsentResponseSchema = z
  .object({
    consentRecordId: idSchema,
    documentId: z.string().min(1),
    documentVersion: z.string().min(1),
    documentSha256: sha256Schema.nullable(),
    accepted: z.boolean(),
    acceptedAt: dateSchema,
    revokedAt: dateSchema.nullable(),
    active: z.boolean(),
  })
  .strict();

export const platformApiDeviceCreateSchema = z
  .object({
    installationId: z.string().min(16).max(128),
    platform: z.enum(["ios", "android", "web"]),
    displayName: z.string().min(1).max(120).nullable().optional(),
    publicKey: z.string().min(32).max(8192).nullable().optional(),
  })
  .strict();

export const platformApiDeviceResponseSchema = z
  .object({
    deviceId: idSchema,
    platform: z.enum(["ios", "android", "web"]),
    displayName: z.string().nullable(),
    createdAt: dateSchema,
    revokedAt: dateSchema.nullable(),
  })
  .strict();

export const platformApiScanSessionResponseSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_API_CONTRACT_VERSION),
    scanSessionId: idSchema,
    consentRecordId: idSchema.nullable(),
    protocol: platformApiCaptureProtocolSchema,
    status: z.enum([
      "draft",
      "capturing",
      "complete",
      "processing",
      "ready",
      "failed",
      "deleted",
    ]),
    createdAt: dateSchema,
    updatedAt: dateSchema,
    completedAt: dateSchema.nullable(),
  })
  .strict();

export const platformApiCaptureAssetInputSchema = z
  .object({
    mediaKind: platformApiMediaKindSchema,
    mimeType: z.string().min(3).max(128),
    byteSize: z.number().int().positive().max(2_147_483_647),
    sha256: sha256Schema,
    widthPx: z.number().int().positive().max(32_768),
    heightPx: z.number().int().positive().max(32_768),
    durationMs: z.number().int().positive().max(60_000).nullable(),
    inputOrigin: platformApiInputOriginSchema,
    encrypted: z.literal(true),
    retentionExpiresAt: dateSchema.nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if ((value.mediaKind === "video") !== (value.durationMs !== null)) {
      context.addIssue({
        code: "custom",
        path: ["durationMs"],
        message: "Exactly video assets require durationMs.",
      });
    }
  });

export const platformApiCaptureAssetResponseSchema =
  platformApiCaptureAssetInputSchema
    .extend({
      assetId: idSchema,
      createdAt: dateSchema,
      uploadStatus: z.enum(["pending", "available", "deleted"]),
    })
    .strict();

export const platformApiAssetTransferIntentResponseSchema = z
  .object({
    assetId: idSchema,
    method: z.enum(["PUT", "GET"]),
    url: z.string().min(1).max(8192),
    headers: z.record(z.string(), z.string()),
    expiresAt: dateSchema,
  })
  .strict();

export const platformApiCaptureViewResponseSchema = z
  .object({
    captureViewId: idSchema,
    captureSetId: idSchema,
    region: platformApiMouthRegionSchema,
    anatomicalSite: platformApiAnatomicalSiteSchema.nullable(),
    angle: platformApiCaptureAngleSchema,
    asset: platformApiCaptureAssetResponseSchema,
    sourceVideoAssetId: idSchema.nullable(),
    qualityAccepted: z.boolean(),
    qualityReasons: z.array(z.string()),
    ordinal: z.number().int().min(0).max(31),
    capturedAt: dateSchema,
  })
  .strict();

export const platformApiCaptureSetResponseSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_API_CONTRACT_VERSION),
    captureSetId: idSchema,
    scanSessionId: idSchema,
    region: platformApiMouthRegionSchema,
    protocol: platformApiCaptureProtocolSchema,
    primaryViewId: idSchema.nullable(),
    views: z.array(platformApiCaptureViewResponseSchema),
    complete: z.boolean(),
    createdAt: dateSchema,
    updatedAt: dateSchema,
  })
  .strict();

const pointSchema = z.tuple([
  z.number().min(0).max(1),
  z.number().min(0).max(1),
]);

export const platformApiCandidateMaskSchema = z
  .object({
    polygon: z.array(pointSchema).min(3).max(4096),
    boundingBox: z.tuple([
      z.number().min(0).max(1),
      z.number().min(0).max(1),
      z.number().positive().max(1),
      z.number().positive().max(1),
    ]),
    normalizedArea: z.number().min(0).max(1),
  })
  .strict()
  .superRefine((value, context) => {
    const [x, y, width, height] = value.boundingBox;
    if (x + width > 1 || y + height > 1) {
      context.addIssue({
        code: "custom",
        path: ["boundingBox"],
        message: "Bounding box must stay within normalized image bounds.",
      });
    }
  });

export const platformApiVisualDescriptorsSchema = z
  .object({
    normalizedArea: z.number().min(0).max(1),
    perimeter: z.number().nonnegative(),
    borderIrregularity: z.number().nonnegative(),
    meanRedness: z.number().min(0).max(1),
    meanBrightness: z.number().min(0).max(1),
    textureContrast: z.number().min(0).max(1),
    measurementLabel: z.literal("approximate"),
  })
  .strict();

export const platformApiUncertaintySchema = z
  .object({
    overallConfidence: z.number().min(0).max(1),
    imageQualityConfidence: z.number().min(0).max(1),
    datasetSimilarity: z.number().min(0).max(1).nullable(),
    modelAgreement: z.number().min(0).max(1).nullable(),
    limitations: z.array(z.string().min(1).max(512)).max(64),
  })
  .strict();

const classScoreSchema = z
  .object({
    label: z.string().min(1).max(128),
    probability: z.number().min(0).max(1),
  })
  .strict();

export const platformApiModelOutputSchema = z
  .object({
    enabled: z.boolean(),
    gatePassed: z.boolean(),
    topLabel: z.string().min(1).max(128).nullable(),
    confidence: z.number().min(0).max(1).nullable(),
    scores: z.array(classScoreSchema).max(128),
    limitation: z.string().min(1).max(1_000),
  })
  .strict();

export const platformApiCalibrationEvidenceSchema = z
  .object({
    status: z.enum(["not_attempted", "valid", "invalid"]),
    method: z.literal("versioned_reference_card"),
    cardVersion: z.string().min(1).max(64).nullable(),
    markerId: z.string().min(1).max(64).nullable(),
    referenceWidthMm: z.number().positive().max(1_000).nullable(),
    millimetersPerPixel: z.number().positive().max(100).nullable(),
    estimatedWidthMm: z.number().nonnegative().max(1_000).nullable(),
    estimatedHeightMm: z.number().nonnegative().max(1_000).nullable(),
    estimatedAreaMm2: z.number().nonnegative().max(1_000_000).nullable(),
    confidence: z.number().min(0).max(1).nullable(),
    gateReasons: z.array(z.string().min(1).max(256)).max(32),
    calibratedAt: dateSchema.nullable(),
    modelVersions: z.record(z.string(), z.string().min(1).max(128)),
    measurementLabel: z.literal("calibrated estimate"),
  })
  .strict();

export const platformApiCandidateObservationResponseSchema = z
  .object({
    captureViewId: idSchema,
    anatomicalSite: platformApiAnatomicalSiteSchema.nullable(),
    candidateMask: platformApiCandidateMaskSchema,
    descriptors: platformApiVisualDescriptorsSchema,
    calibration: platformApiCalibrationEvidenceSchema.nullable(),
    appearanceOutput: platformApiModelOutputSchema.nullable(),
    diseaseResearchOutput: platformApiModelOutputSchema.nullable(),
    uncertainty: platformApiUncertaintySchema,
    namedMesh: z.string().min(1).max(128).nullable(),
    uvCoordinates: pointSchema.nullable(),
    assetVersion: z.string().min(1).max(128).nullable(),
    limitations: z.array(z.string().min(1).max(512)).max(64),
    observationId: idSchema,
    analysisRunId: idSchema,
    region: platformApiMouthRegionSchema,
    createdAt: dateSchema,
  })
  .strict();

export const platformApiAnalysisRunResponseSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_API_CONTRACT_VERSION),
    analysisRunId: idSchema,
    captureSetId: idSchema,
    requestedHeads: z.array(platformApiModelHeadSchema),
    status: platformApiAnalysisStatusSchema,
    observations: z.array(platformApiCandidateObservationResponseSchema),
    inputOrigin: platformApiInputOriginSchema,
    analysisOrigin: platformApiAnalysisOriginSchema,
    sourceAssetSha256: z.array(sha256Schema),
    modelVersions: z.record(z.string(), z.string()),
    artifactHashes: z.record(z.string(), sha256Schema),
    abstentionReasons: z.array(z.string()),
    startedAt: dateSchema,
    completedAt: dateSchema.nullable(),
    persisted: z.literal(true),
    signedEnvelopeId: idSchema,
    disclaimer: z.literal(PLATFORM_API_DISCLAIMER),
  })
  .strict();

export const platformApiMatchProposalCreateSchema = z
  .object({
    currentObservationId: idSchema,
    candidatePriorObservationId: idSchema,
    candidateLesionId: idSchema.nullable().optional(),
    proposalOrigin: z.enum(["automatic_model", "user_selected"]),
    score: z.number().min(0).max(1).nullable(),
    rank: z.number().int().positive().max(100).nullable(),
    modelVersions: z.record(z.string(), z.string().min(1).max(128)),
    expiresAt: dateSchema.nullable().optional(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.currentObservationId === value.candidatePriorObservationId) {
      context.addIssue({
        code: "custom",
        path: ["candidatePriorObservationId"],
        message: "A proposal requires two distinct observations.",
      });
    }
    const invalidAutomatic =
      value.proposalOrigin === "automatic_model" &&
      (value.score === null ||
        value.rank === null ||
        Object.keys(value.modelVersions).length === 0);
    const invalidUserSelected =
      value.proposalOrigin === "user_selected" &&
      (value.score !== null ||
        value.rank !== null ||
        Object.keys(value.modelVersions).length > 0);
    if (invalidAutomatic || invalidUserSelected) {
      context.addIssue({
        code: "custom",
        path: ["proposalOrigin"],
        message:
          "Automatic proposals require a score, rank, and model versions; user-selected proposals require none.",
      });
    }
  });

export const platformApiMatchProposalResponseSchema = z
  .object({
    proposalId: idSchema,
    currentObservationId: idSchema,
    candidatePriorObservationId: idSchema,
    candidateLesionId: idSchema.nullable(),
    proposalOrigin: z.enum(["automatic_model", "user_selected"]),
    score: z.number().min(0).max(1).nullable(),
    rank: z.number().int().positive().max(100).nullable(),
    state: z.literal("proposed"),
    automaticallyConfirmed: z.literal(false),
    modelVersions: z.record(z.string(), z.string()),
    generatedAt: dateSchema,
    expiresAt: dateSchema.nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.currentObservationId === value.candidatePriorObservationId) {
      context.addIssue({
        code: "custom",
        path: ["candidatePriorObservationId"],
        message: "A proposal requires two distinct observations.",
      });
    }
    const invalidAutomatic =
      value.proposalOrigin === "automatic_model" &&
      (value.score === null ||
        value.rank === null ||
        Object.keys(value.modelVersions).length === 0);
    const invalidUserSelected =
      value.proposalOrigin === "user_selected" &&
      (value.score !== null ||
        value.rank !== null ||
        Object.keys(value.modelVersions).length > 0);
    if (invalidAutomatic || invalidUserSelected) {
      context.addIssue({
        code: "custom",
        path: ["proposalOrigin"],
        message:
          "Automatic proposals require a score, rank, and model versions; user-selected proposals require none.",
      });
    }
  });

export const platformApiMatchDecisionCreateSchema = z
  .object({
    decision: z.enum(["confirmed", "rejected", "deferred"]),
    rationale: z.string().min(1).max(1_000).nullable().optional(),
  })
  .strict();

export const platformApiMatchDecisionResponseSchema = z
  .object({
    decisionId: idSchema,
    proposalId: idSchema,
    decision: z.enum(["confirmed", "rejected", "deferred"]),
    decidedBy: z.literal("patient"),
    actorId: idSchema,
    rationale: z.string().nullable(),
    decidedAt: dateSchema,
    lesionId: idSchema.nullable(),
  })
  .strict();

export const PLATFORM_API_JOB_TYPES = [
  "analysis",
  "comparison",
  "reconstruction",
  "report",
  "summary_video",
  "data_export",
  "account_deletion",
  "delete_all",
] as const;
export const platformApiJobTypeSchema = z.enum(PLATFORM_API_JOB_TYPES);
export const platformApiJobStatusSchema = z.enum([
  "queued",
  "running",
  "succeeded",
  "failed",
  "cancelled",
  "expired",
]);

export const platformApiJobCreateSchema = z
  .object({
    type: platformApiJobTypeSchema.exclude(["account_deletion", "delete_all"]),
    inputRefs: z.array(idSchema).max(128).optional(),
    payload: z.record(z.string(), z.unknown()).optional(),
    maxAttempts: z.number().int().positive().max(8).optional(),
  })
  .strict();

export const platformApiJobResponseSchema = z
  .object({
    jobId: idSchema,
    ownerId: idSchema,
    type: platformApiJobTypeSchema,
    status: platformApiJobStatusSchema,
    inputRefs: z.array(idSchema).max(128),
    outputRefs: z.array(idSchema).max(128),
    progress: z.number().min(0).max(1),
    attempt: z.number().int().nonnegative(),
    maxAttempts: z.number().int().positive().max(20),
    errorCode: z.string().nullable(),
    errorMessage: z.string().nullable(),
    createdAt: dateSchema,
    startedAt: dateSchema.nullable(),
    completedAt: dateSchema.nullable(),
    expiresAt: dateSchema,
    outcome: z
      .enum(["complete", "unavailable", "cancelled", "failed"])
      .nullable(),
    reasonCode: z.string().nullable(),
    result: z.record(z.string(), z.unknown()).nullable(),
    cancellationRequested: z.boolean(),
  })
  .strict()
  .superRefine((value, context) => {
    const terminal = new Set(["succeeded", "failed", "cancelled", "expired"]);
    if (terminal.has(value.status) !== (value.completedAt !== null)) {
      context.addIssue({
        code: "custom",
        path: ["completedAt"],
        message: "Exactly terminal jobs require a completion timestamp.",
      });
    }
    if (value.status === "succeeded" && value.progress !== 1) {
      context.addIssue({
        code: "custom",
        path: ["progress"],
        message: "Succeeded jobs must report complete progress.",
      });
    }
  });

export const platformApiReportResponseSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_API_CONTRACT_VERSION),
    reportArtifactId: idSchema,
    patientId: idSchema,
    scanSessionIds: z.array(idSchema).min(1).max(64),
    format: z.enum([
      "pdf",
      "html",
      "fhir_r4_bundle",
      "summary_video",
      "transcript",
    ]),
    assetId: idSchema,
    sha256: sha256Schema,
    byteSize: z.number().int().positive().max(2_147_483_647),
    locale: z.string().min(2).max(35),
    accessible: z.boolean(),
    inputOrigins: z.array(platformApiInputOriginSchema).min(1).max(8),
    analysisOrigins: z.array(platformApiAnalysisOriginSchema).min(1).max(8),
    modelVersions: z.record(z.string(), z.string()),
    signedEnvelopeId: idSchema,
    retentionExpiresAt: dateSchema.nullable(),
    createdAt: dateSchema,
    disclaimer: z.literal(PLATFORM_API_DISCLAIMER),
  })
  .strict();

export const platformApiGeneratedArtifactResponseSchema = z
  .object({
    artifactId: idSchema,
    ownerId: idSchema,
    jobId: idSchema,
    purpose: z.enum(["reconstruction", "summary_video"]),
    filename: z.string().min(1).max(120),
    mediaType: z.enum(["model/gltf-binary", "video/mp4"]),
    sha256: sha256Schema,
    sizeBytes: z.number().int().positive().max(100_000_000),
    objectKey: z.string().min(1),
    manifest: z.record(z.string(), z.unknown()),
    createdAt: dateSchema,
    retentionExpiresAt: dateSchema,
  })
  .strict();

export const platformApiDataExportArtifactResponseSchema = z
  .object({
    artifactId: idSchema,
    exportRequestId: idSchema,
    jobId: idSchema,
    mediaType: z.literal("application/vnd.stoma3d.export"),
    sha256: sha256Schema,
    byteSize: z.number().int().positive().max(2_147_483_647),
    includedFiles: z.boolean(),
    encryption: z
      .object({
        scheme: z.literal("x25519-hkdf-sha256-aes-256-gcm"),
        ephemeralPublicKeyB64: z.string(),
        saltB64: z.string(),
        nonceB64: z.string(),
      })
      .strict(),
    createdAt: dateSchema,
    retentionExpiresAt: dateSchema,
  })
  .strict();

export const platformApiDeletionRequestResponseSchema = z
  .object({
    requestId: idSchema,
    jobId: idSchema,
    status: z.enum(["requested", "in_progress", "completed", "failed"]),
    requestedAt: dateSchema,
    startedAt: dateSchema.nullable(),
    completedAt: dateSchema.nullable(),
    errorCode: z.string().nullable(),
  })
  .strict();

export const platformApiSyncEntityTypeSchema = z.enum([
  "scan_session",
  "capture_set",
  "capture_view",
  "analysis_run",
  "observation",
  "lesion",
  "match_decision",
  "report",
]);

const syncOperationCommon = {
  contractVersion: z.literal(PLATFORM_API_CONTRACT_VERSION),
  operationId: idSchema,
  idempotencyKey: z.string().min(16).max(256),
  deviceId: idSchema,
  entityType: platformApiSyncEntityTypeSchema,
  entityId: idSchema,
  version: z.number().int().positive(),
  sequence: z.number().int().nonnegative(),
  occurredAt: dateSchema,
};

export const platformApiSyncOperationInputSchema = z.discriminatedUnion(
  "operation",
  [
    z
      .object({
        ...syncOperationCommon,
        operation: z.literal("upsert"),
        encryptedPayload: encryptedPayloadSchema,
        tombstone: z.literal(false),
      })
      .strict(),
    z
      .object({
        ...syncOperationCommon,
        operation: z.literal("delete"),
        encryptedPayload: z.null(),
        tombstone: z.literal(true),
      })
      .strict(),
  ],
);

export const platformApiSyncCursorResponseSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_API_CONTRACT_VERSION),
    cursor: z.string().min(16).max(2_048),
    highWatermark: z.number().int().nonnegative(),
    issuedAt: dateSchema,
    expiresAt: dateSchema,
  })
  .strict();

export const platformApiSyncOperationOutputSchema = z.discriminatedUnion(
  "operation",
  [
    z
      .object({
        ...syncOperationCommon,
        operation: z.literal("upsert"),
        encryptedPayload: encryptedPayloadSchema,
        tombstone: z.literal(false),
        serverSequence: z.number().int().positive(),
      })
      .strict(),
    z
      .object({
        ...syncOperationCommon,
        operation: z.literal("delete"),
        encryptedPayload: z.null(),
        tombstone: z.literal(true),
        serverSequence: z.number().int().positive(),
      })
      .strict(),
  ],
);

export const platformApiSyncPushResponseSchema = z
  .object({
    results: z.array(
      z
        .object({
          operationId: idSchema,
          status: z.enum([
            "applied",
            "stale_ignored",
            "tombstone_wins",
            "duplicate",
          ]),
          serverSequence: z.number().int().positive().nullable(),
        })
        .strict(),
    ),
    cursor: platformApiSyncCursorResponseSchema,
  })
  .strict();

export const platformApiSyncPullResponseSchema = z
  .object({
    operations: z.array(platformApiSyncOperationOutputSchema),
    cursor: platformApiSyncCursorResponseSchema,
    hasMore: z.boolean(),
  })
  .strict();

export const platformApiShareResourceTypeSchema = z.enum([
  "scan_session",
  "report",
  "lesion",
  "analysis_run",
]);

export const platformApiResourceRefSchema = z
  .object({
    resourceType: platformApiShareResourceTypeSchema,
    resourceId: resourceIdSchema,
  })
  .strict();

export const platformApiShareLinkResponseSchema = z
  .object({
    shareId: idSchema,
    patientUserId: idSchema,
    status: z.enum(["active", "revoked"]),
    resources: z.array(platformApiResourceRefSchema),
    expiresAt: dateSchema,
    maxExchanges: z.number().int().positive(),
    exchangeCount: z.number().int().nonnegative(),
    revokedAt: dateSchema.nullable(),
    createdAt: dateSchema,
    retentionExpiresAt: dateSchema,
    active: z.boolean(),
  })
  .strict();

export const platformApiAccessGrantResponseSchema = z
  .object({
    grantId: idSchema,
    patientUserId: idSchema,
    clinicianUserId: idSchema,
    status: z.enum(["active", "revoked"]),
    label: z.string().nullable(),
    resources: z.array(platformApiResourceRefSchema),
    reviewId: idSchema,
    expiresAt: dateSchema,
    revokedAt: dateSchema.nullable(),
    createdAt: dateSchema,
    updatedAt: dateSchema,
    retentionExpiresAt: dateSchema,
    active: z.boolean(),
  })
  .strict();

export const platformApiClinicianIdentityRoleResponseSchema = z
  .object({
    requiredClaim: z.string().min(1).max(160),
    requiredValue: z.literal("clinician"),
    observationStatus: z.enum([
      "not_applicable",
      "awaiting_token_observation",
      "observed",
    ]),
    oidcRoleObservedAt: dateSchema
      .nullable()
      .describe("Timestamp of the first validated clinician role observation."),
    privilegedAccessReady: z.boolean(),
  })
  .strict();

const platformApiClinicianReviewerEvidenceSchema = z
  .object({
    source: z.string().min(1).max(160),
    referenceId: z.string().min(4).max(160),
    checkedAt: dateSchema,
    reviewerNotes: z.string().min(1).max(1_000).nullable(),
  })
  .strict();

export const platformApiClinicianVerificationResponseSchema = z
  .object({
    verificationId: idSchema,
    applicantUserId: idSchema,
    status: z.enum(["pending", "verified", "rejected"]),
    profession: z.string().min(1).max(80),
    licenseJurisdiction: z.string().min(1).max(80),
    licenseNumberSuffix: z.string().min(1).max(80),
    organization: z.string().min(1).max(160).nullable(),
    applicantEvidenceRef: z.string().min(1).max(160),
    submittedAt: dateSchema,
    reviewerUserId: idSchema.nullable(),
    reviewerEvidence: platformApiClinicianReviewerEvidenceSchema.nullable(),
    decisionReason: z.string().min(1).max(500).nullable(),
    reviewedAt: dateSchema.nullable(),
    retentionExpiresAt: dateSchema,
    identityRole: platformApiClinicianIdentityRoleResponseSchema,
  })
  .strict();

export const platformApiClinicianVerificationQueueSchema = z
  .object({
    items: z.array(platformApiClinicianVerificationResponseSchema),
    nextCursor: idSchema.nullable(),
  })
  .strict();

export const PLATFORM_API_REVIEW_ANNOTATION_KINDS = [
  "note",
  "question",
  "follow_up",
  "measurement_context",
  "outline_adjustment",
  "location_correction",
  "insufficient_scan",
  "date_comparison",
] as const;
export const platformApiReviewAnnotationKindSchema = z.enum(
  PLATFORM_API_REVIEW_ANNOTATION_KINDS,
);

export const platformApiReviewAnnotationResponseSchema = z
  .object({
    annotationId: idSchema,
    reviewId: idSchema,
    clinicianUserId: idSchema,
    resource: platformApiResourceRefSchema,
    kind: platformApiReviewAnnotationKindSchema,
    body: z.string().min(1).max(4_000),
    createdAt: dateSchema,
    retentionExpiresAt: dateSchema,
  })
  .strict();

export const platformApiClinicianReviewResponseSchema = z
  .object({
    reviewId: idSchema,
    grantId: idSchema,
    patientUserId: idSchema,
    clinicianUserId: idSchema,
    status: z.enum(["pending", "in_review", "completed", "declined"]),
    summary: z.string().nullable(),
    resources: z.array(platformApiResourceRefSchema),
    annotations: z.array(platformApiReviewAnnotationResponseSchema),
    grantExpiresAt: dateSchema,
    grantRevokedAt: dateSchema.nullable(),
    createdAt: dateSchema,
    updatedAt: dateSchema,
    startedAt: dateSchema.nullable(),
    completedAt: dateSchema.nullable(),
    retentionExpiresAt: dateSchema,
    accessActive: z.boolean(),
  })
  .strict();

export const platformApiAccessHistoryItemSchema = z
  .object({
    eventId: idSchema,
    actorUserId: idSchema.nullable(),
    actorType: z.enum([
      "patient",
      "clinician",
      "share_viewer",
      "admin",
      "system",
    ]),
    eventType: z.enum([
      "grant_created",
      "grant_revoked",
      "share_created",
      "share_revoked",
      "share_exchanged",
      "resource_viewed",
      "review_status_changed",
      "annotation_created",
    ]),
    resourceType: z.string().min(1),
    resourceId: idSchema.nullable(),
    grantId: idSchema.nullable(),
    shareId: idSchema.nullable(),
    reviewId: idSchema.nullable(),
    details: z.record(z.string(), z.unknown()),
    createdAt: dateSchema,
    retentionExpiresAt: dateSchema,
  })
  .strict();

export const PLATFORM_API_ANALYTICS_NAMES = [
  "app_opened",
  "onboarding_completed",
  "scan_started",
  "scan_completed",
  "capture_retake_requested",
  "analysis_completed",
  "analysis_unavailable",
  "comparison_viewed",
  "observation_map_viewed",
  "report_generated",
  "report_downloaded",
  "summary_video_generated",
  "share_created",
  "share_revoked",
  "clinician_review_requested",
  "learning_section_viewed",
  "notification_permission_changed",
] as const;
export const platformApiAnalyticsNameSchema = z.enum(
  PLATFORM_API_ANALYTICS_NAMES,
);

export const platformApiAnalyticsConsentResponseSchema = z
  .object({
    enabled: z.boolean(),
    policyVersion: z.string().nullable(),
    updatedAt: dateSchema.nullable(),
  })
  .strict();

export const platformApiAnalyticsEventInputSchema = z
  .object({
    name: platformApiAnalyticsNameSchema,
    platform: z.enum(["ios", "android", "web"]),
    appVersion: z.string().regex(/^[A-Za-z0-9._+-]{1,32}$/),
    surface: z.enum([
      "app",
      "onboarding",
      "scan",
      "result",
      "comparison",
      "map",
      "report",
      "sharing",
      "clinician",
      "learn",
      "settings",
    ]),
    outcome: z.enum([
      "started",
      "completed",
      "abstained",
      "cancelled",
      "failed",
      "viewed",
      "generated",
      "shared",
      "revoked",
      "enabled",
      "disabled",
    ]),
  })
  .strict();

export type PlatformApiScanSessionResponse = z.infer<
  typeof platformApiScanSessionResponseSchema
>;
export type PlatformApiCaptureSetResponse = z.infer<
  typeof platformApiCaptureSetResponseSchema
>;
export type PlatformApiAnalysisRunResponse = z.infer<
  typeof platformApiAnalysisRunResponseSchema
>;
export type PlatformApiJobResponse = z.infer<
  typeof platformApiJobResponseSchema
>;
export type PlatformApiMatchDecisionResponse = z.infer<
  typeof platformApiMatchDecisionResponseSchema
>;
export type PlatformApiReportResponse = z.infer<
  typeof platformApiReportResponseSchema
>;
export type PlatformApiClinicianIdentityRoleResponse = z.infer<
  typeof platformApiClinicianIdentityRoleResponseSchema
>;
export type PlatformApiClinicianVerificationResponse = z.infer<
  typeof platformApiClinicianVerificationResponseSchema
>;
export type PlatformApiClinicianVerificationQueue = z.infer<
  typeof platformApiClinicianVerificationQueueSchema
>;
