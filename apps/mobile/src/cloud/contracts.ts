import {
  platformApiAnalysisRunResponseSchema,
  platformApiCandidateMaskSchema,
  platformApiCandidateObservationResponseSchema,
  platformApiGeneratedArtifactResponseSchema,
  platformApiReportResponseSchema,
} from "@oralsight/contracts";
import { z } from "zod";

export const PLATFORM_CONTRACT_VERSION = "2.0.0" as const;
export const mouthRegionSchema = z.enum([
  "dorsal_tongue",
  "ventral_tongue",
  "left_buccal_mucosa",
  "right_buccal_mucosa",
  "upper_lip",
  "lower_lip",
  "upper_dental_arch",
  "lower_dental_arch",
]);
export const captureProtocolSchema = z.enum([
  "standard_eight_region",
  "detailed_multi_angle",
  "guided_video_sweep",
]);
export const captureAngleSchema = z.enum([
  "primary",
  "straight",
  "left_oblique",
  "right_oblique",
  "superior",
  "inferior",
]);
export const mediaKindSchema = z.enum(["image", "video", "video_frame"]);
export const inputOriginSchema = z.enum(["live_capture", "bundled_demo"]);
export const syncEntityTypeSchema = z.enum([
  "scan_session",
  "capture_set",
  "capture_view",
  "analysis_run",
  "observation",
  "lesion",
  "match_decision",
  "report",
]);
export const jobTypeSchema = z.enum([
  "analysis",
  "comparison",
  "reconstruction",
  "report",
  "summary_video",
  "data_export",
]);
const idSchema = z.string().min(1).max(128);
const dateSchema = z.string().datetime({ offset: true });
export const sha256Schema = z.string().regex(/^[a-f0-9]{64}$/);
export const idempotencyKeySchema = z
  .string()
  .min(16)
  .max(128)
  .regex(/^[A-Za-z0-9._:-]+$/);

export const errorEnvelopeSchema = z
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

export const meResponseSchema = z
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
  })
  .strict();

export const deviceResponseSchema = z
  .object({
    deviceId: idSchema,
    platform: z.enum(["ios", "android", "web"]),
    displayName: z.string().nullable(),
    createdAt: dateSchema,
    revokedAt: dateSchema.nullable(),
  })
  .strict();

export const deviceCreateSchema = z
  .object({
    installationId: z.string().min(16).max(128),
    platform: z.enum(["ios", "android", "web"]),
    displayName: z.string().min(1).max(120).nullable().optional(),
    publicKey: z.string().min(32).max(8192).nullable().optional(),
  })
  .strict();

export const scanSessionResponseSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    scanSessionId: idSchema,
    consentRecordId: idSchema.nullable(),
    protocol: captureProtocolSchema,
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

export const consentDocumentSchema = z
  .object({
    documentId: z.string().regex(/^[A-Za-z0-9._:-]{1,120}$/),
    documentVersion: z.string().regex(/^[A-Za-z0-9._:-]{1,64}$/),
    documentSha256: sha256Schema,
    title: z.string().min(1).max(200),
    body: z.string().min(1).max(10_000),
    withdrawalEffect: z.literal(
      "blocks_new_cloud_work_revokes_access_preserves_existing_data",
    ),
  })
  .strict();
export const productConsentSchema = z
  .object({
    consentRecordId: idSchema,
    documentId: z.string(),
    documentVersion: z.string(),
    documentSha256: sha256Schema.nullable(),
    accepted: z.boolean(),
    acceptedAt: dateSchema,
    revokedAt: dateSchema.nullable(),
    active: z.boolean(),
  })
  .strict();
export const productConsentListSchema = z
  .object({
    items: z.array(productConsentSchema),
  })
  .strict();

export const captureAssetInputSchema = z
  .object({
    mediaKind: mediaKindSchema,
    mimeType: z.string().min(3).max(128),
    byteSize: z.number().int().positive().max(2_147_483_647),
    sha256: sha256Schema,
    widthPx: z.number().int().positive().max(32_768),
    heightPx: z.number().int().positive().max(32_768),
    durationMs: z.number().int().positive().max(60_000).nullable(),
    inputOrigin: inputOriginSchema,
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

export const captureAssetResponseSchema = captureAssetInputSchema
  .extend({
    assetId: idSchema,
    createdAt: dateSchema,
    uploadStatus: z.enum(["pending", "available", "deleted"]),
  })
  .strict();

export const captureViewResponseSchema = z
  .object({
    captureViewId: idSchema,
    captureSetId: idSchema,
    region: mouthRegionSchema,
    anatomicalSite: z.string().nullable(),
    angle: captureAngleSchema,
    asset: captureAssetResponseSchema,
    sourceVideoAssetId: idSchema.nullable(),
    qualityAccepted: z.boolean(),
    qualityReasons: z.array(z.string()),
    ordinal: z.number().int().min(0).max(31),
    capturedAt: dateSchema,
  })
  .strict();

export const captureSetResponseSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    captureSetId: idSchema,
    scanSessionId: idSchema,
    region: mouthRegionSchema,
    protocol: captureProtocolSchema,
    primaryViewId: idSchema.nullable(),
    views: z.array(captureViewResponseSchema),
    complete: z.boolean(),
    createdAt: dateSchema,
    updatedAt: dateSchema,
  })
  .strict();

export const jobResponseSchema = z
  .object({
    jobId: idSchema,
    ownerId: idSchema,
    type: z.enum([
      "analysis",
      "comparison",
      "reconstruction",
      "report",
      "summary_video",
      "data_export",
      "account_deletion",
      "delete_all",
    ]),
    status: z.enum([
      "queued",
      "running",
      "succeeded",
      "failed",
      "cancelled",
      "expired",
    ]),
    inputRefs: z.array(idSchema),
    outputRefs: z.array(idSchema),
    progress: z.number().min(0).max(1),
    attempt: z.number().int().min(0),
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
    reasonCode: z.string().max(100).nullable(),
    result: z.record(z.string(), z.unknown()).nullable(),
    cancellationRequested: z.boolean(),
  })
  .strict();

export const jobListResponseSchema = z
  .object({
    items: z.array(jobResponseSchema),
    nextCursor: z.string().nullable().optional(),
  })
  .strict();

export const generatedArtifactSchema =
  platformApiGeneratedArtifactResponseSchema;

export const deletionResponseSchema = z
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

const syncOperationShape = {
  contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
  operationId: idSchema,
  idempotencyKey: z.string().min(16).max(256),
  deviceId: idSchema,
  entityType: syncEntityTypeSchema,
  entityId: idSchema,
  version: z.number().int().positive(),
  sequence: z.number().int().min(0),
  occurredAt: dateSchema,
  operation: z.enum(["upsert", "delete"]),
  encryptedPayload: z.string().min(16).max(1_000_000).nullable(),
  tombstone: z.boolean(),
} as const;

function validateSyncOperation(
  value: z.infer<z.ZodObject<typeof syncOperationShape>>,
  context: z.RefinementCtx,
) {
  if (
    value.operation === "upsert" &&
    (value.encryptedPayload === null || value.tombstone)
  ) {
    context.addIssue({ code: "custom", message: "Invalid upsert shape." });
  }
  if (
    value.operation === "delete" &&
    (value.encryptedPayload !== null || !value.tombstone)
  ) {
    context.addIssue({ code: "custom", message: "Invalid delete shape." });
  }
}

export const syncOperationInputSchema = z
  .object(syncOperationShape)
  .strict()
  .superRefine(validateSyncOperation);
export const syncOperationOutputSchema = z
  .object({
    ...syncOperationShape,
    serverSequence: z.number().int().positive(),
  })
  .strict()
  .superRefine(validateSyncOperation);
export const syncCursorSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    cursor: z.string().min(16).max(2048),
    highWatermark: z.number().int().min(0),
    issuedAt: dateSchema,
    expiresAt: dateSchema,
  })
  .strict();
export const syncPushResponseSchema = z
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
    cursor: syncCursorSchema,
  })
  .strict();
export const syncPullResponseSchema = z
  .object({
    operations: z.array(syncOperationOutputSchema),
    cursor: syncCursorSchema,
    hasMore: z.boolean(),
  })
  .strict();

export const shareResourceTypeSchema = z.enum([
  "scan_session",
  "report",
  "lesion",
  "analysis_run",
]);
export const resourceRefSchema = z
  .object({
    resourceType: shareResourceTypeSchema,
    resourceId: idSchema,
  })
  .strict();
export const shareLinkSchema = z
  .object({
    shareId: idSchema,
    patientUserId: idSchema,
    status: z.enum(["active", "revoked"]),
    resources: z.array(resourceRefSchema),
    expiresAt: dateSchema,
    maxExchanges: z.number().int().min(1).max(10),
    exchangeCount: z.number().int().nonnegative(),
    revokedAt: dateSchema.nullable(),
    createdAt: dateSchema,
    retentionExpiresAt: dateSchema,
    active: z.boolean(),
  })
  .strict();
export const shareCreateResponseSchema = z
  .object({
    share: shareLinkSchema,
    fragmentSecret: z.string().min(40).max(128),
    fragmentParameter: z.literal("secret"),
  })
  .strict();
export const shareListSchema = z
  .object({ items: z.array(shareLinkSchema) })
  .strict();

export const accessHistoryItemSchema = z
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
    resourceType: z.string().min(1).max(128),
    resourceId: idSchema.nullable(),
    grantId: idSchema.nullable(),
    shareId: idSchema.nullable(),
    reviewId: idSchema.nullable(),
    details: z.record(z.string(), z.unknown()),
    createdAt: dateSchema,
    retentionExpiresAt: dateSchema,
  })
  .strict();
export const accessHistoryResponseSchema = z
  .object({
    items: z.array(accessHistoryItemSchema),
    nextCursor: z.string().nullable(),
  })
  .strict();

export const assetUploadTicketSchema = z
  .object({
    assetId: idSchema,
    url: z.string().min(1).max(8192),
    method: z.enum(["PUT", "GET"]),
    headers: z.record(z.string(), z.string()),
    expiresAt: dateSchema,
  })
  .strict();
export const assetFinalizeResponseSchema = z
  .object({
    asset: captureAssetResponseSchema,
    checksumVerified: z.literal(true),
  })
  .strict();

export const cloudCandidateMaskSchema = platformApiCandidateMaskSchema;
export const cloudObservationSchema =
  platformApiCandidateObservationResponseSchema;
export const analysisRunSchema = platformApiAnalysisRunResponseSchema;

export const matchProposalSchema = z
  .object({
    proposalId: idSchema,
    currentObservationId: idSchema,
    candidatePriorObservationId: idSchema,
    candidateLesionId: idSchema.nullable(),
    proposalOrigin: z.enum(["automatic_model", "user_selected"]),
    score: z.number().min(0).max(1).nullable(),
    rank: z.number().int().min(1).max(100).nullable(),
    state: z.literal("proposed"),
    automaticallyConfirmed: z.literal(false),
    modelVersions: z.record(z.string(), z.string().min(1)),
    generatedAt: dateSchema,
    expiresAt: dateSchema.nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    const automatic = value.proposalOrigin === "automatic_model";
    if (
      automatic &&
      (value.score === null ||
        value.rank === null ||
        Object.keys(value.modelVersions).length === 0)
    ) {
      context.addIssue({
        code: "custom",
        message: "Automatic match proposals require model evidence.",
      });
    }
    if (
      !automatic &&
      (value.score !== null ||
        value.rank !== null ||
        Object.keys(value.modelVersions).length > 0)
    ) {
      context.addIssue({
        code: "custom",
        message: "User-selected pairs cannot claim model evidence.",
      });
    }
  });

export const matchDecisionSchema = z
  .object({
    decisionId: idSchema,
    proposalId: idSchema,
    decision: z.enum(["confirmed", "rejected", "deferred"]),
    decidedBy: z.literal("patient"),
    actorId: idSchema,
    rationale: z.string().max(1_000).nullable(),
    decidedAt: dateSchema,
    lesionId: idSchema.nullable(),
  })
  .strict();

export const lesionSchema = z
  .object({
    lesionId: idSchema,
    region: mouthRegionSchema,
    anatomicalSite: z.string().nullable(),
    label: z.string().nullable(),
    status: z.enum(["tracking", "archived"]),
    confirmedObservationIds: z.array(idSchema).min(1),
    matchDecisionIds: z.array(idSchema),
    version: z.number().int().positive(),
    createdAt: dateSchema,
    updatedAt: dateSchema,
  })
  .strict();

export const reportArtifactSchema = platformApiReportResponseSchema;

export const dataExportArtifactSchema = z
  .object({
    artifactId: idSchema,
    exportRequestId: idSchema,
    jobId: idSchema,
    mediaType: z.literal("application/vnd.oralsight.export"),
    sha256: sha256Schema,
    byteSize: z.number().int().positive(),
    includedFiles: z.boolean(),
    encryption: z
      .object({
        scheme: z.literal("x25519-hkdf-sha256-aes-256-gcm"),
        ephemeralPublicKeyB64: z.string().min(40).max(64),
        saltB64: z.string().min(20).max(32),
        nonceB64: z.string().min(16).max(24),
      })
      .strict(),
    createdAt: dateSchema,
    retentionExpiresAt: dateSchema,
  })
  .strict();

export const ANALYTICS_POLICY_VERSION = "analytics-v1" as const;
export const analyticsNameSchema = z.enum([
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
]);
export const analyticsSurfaceSchema = z.enum([
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
]);
export const analyticsOutcomeSchema = z.enum([
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
]);
export const analyticsEventSchema = z
  .object({
    name: analyticsNameSchema,
    platform: z.enum(["ios", "android", "web"]),
    appVersion: z.string().regex(/^[A-Za-z0-9._+-]{1,32}$/),
    surface: analyticsSurfaceSchema,
    outcome: analyticsOutcomeSchema,
  })
  .strict();
export const analyticsConsentSchema = z
  .object({
    enabled: z.boolean(),
    policyVersion: z.string().nullable(),
    updatedAt: dateSchema.nullable(),
  })
  .strict();
export const analyticsAcceptedSchema = z
  .object({
    accepted: z.number().int().min(1).max(20),
    retentionDays: z.literal(30),
  })
  .strict();

export type CaptureAssetInput = z.infer<typeof captureAssetInputSchema>;
export type CaptureViewResponse = z.infer<typeof captureViewResponseSchema>;
export type DeviceResponse = z.infer<typeof deviceResponseSchema>;
export type ScanSessionResponse = z.infer<typeof scanSessionResponseSchema>;
export type CaptureSetResponse = z.infer<typeof captureSetResponseSchema>;
export type JobResponse = z.infer<typeof jobResponseSchema>;
export type DeletionResponse = z.infer<typeof deletionResponseSchema>;
export type SyncOperationInput = z.infer<typeof syncOperationInputSchema>;
export type SyncPushResponse = z.infer<typeof syncPushResponseSchema>;
export type SyncPullResponse = z.infer<typeof syncPullResponseSchema>;
export type MeResponse = z.infer<typeof meResponseSchema>;
export type JobListResponse = z.infer<typeof jobListResponseSchema>;
export type GeneratedArtifact = z.infer<typeof generatedArtifactSchema>;
export type ResourceRef = z.infer<typeof resourceRefSchema>;
export type ShareLink = z.infer<typeof shareLinkSchema>;
export type ShareCreateResponse = z.infer<typeof shareCreateResponseSchema>;
export type AccessHistoryItem = z.infer<typeof accessHistoryItemSchema>;
export type AccessHistoryResponse = z.infer<typeof accessHistoryResponseSchema>;
export type AssetUploadTicket = z.infer<typeof assetUploadTicketSchema>;
export type AnalysisRun = z.infer<typeof analysisRunSchema>;
export type MatchProposal = z.infer<typeof matchProposalSchema>;
export type MatchDecision = z.infer<typeof matchDecisionSchema>;
export type Lesion = z.infer<typeof lesionSchema>;
export type CloudObservation = z.infer<typeof cloudObservationSchema>;
export type ReportArtifact = z.infer<typeof reportArtifactSchema>;
export type DataExportArtifact = z.infer<typeof dataExportArtifactSchema>;
export type ConsentDocument = z.infer<typeof consentDocumentSchema>;
export type ProductConsent = z.infer<typeof productConsentSchema>;
export type AnalyticsConsent = z.infer<typeof analyticsConsentSchema>;
export type AnalyticsEvent = z.infer<typeof analyticsEventSchema>;
