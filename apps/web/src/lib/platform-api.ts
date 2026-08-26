import {
  PLATFORM_CONTRACT_VERSION,
  captureSetSchema as contractCaptureSetSchema,
  platformApiClinicianVerificationQueueSchema as clinicianVerificationQueueSchema,
  platformApiClinicianVerificationResponseSchema as clinicianVerificationSchema,
  reportArtifactSchema,
} from "@oralsight/contracts";
import type { CaptureSet, ReportArtifact } from "@oralsight/contracts";
import { z } from "zod";

import { getAuth0Client } from "@/lib/auth0";

function removeCaptureUploadStatus(value: unknown): unknown {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return value;
  }
  const candidate = value as Record<string, unknown>;
  if (!Array.isArray(candidate.views)) return value;
  return {
    ...candidate,
    views: candidate.views.map((view) => {
      if (view === null || typeof view !== "object" || Array.isArray(view)) {
        return view;
      }
      const typedView = view as Record<string, unknown>;
      const asset = typedView.asset;
      if (asset === null || typeof asset !== "object" || Array.isArray(asset)) {
        return view;
      }
      const contractAsset = { ...(asset as Record<string, unknown>) };
      if (
        "uploadStatus" in contractAsset &&
        !["pending", "available", "deleted"].includes(
          String(contractAsset.uploadStatus),
        )
      ) {
        return view;
      }
      delete contractAsset.uploadStatus;
      return { ...typedView, asset: contractAsset };
    }),
  };
}

const captureSetSchema = z.preprocess(
  removeCaptureUploadStatus,
  contractCaptureSetSchema,
);

export const USER_ROLES = [
  "patient",
  "share_viewer",
  "clinician_pending",
  "clinician",
  "admin",
] as const;

export const userRoleSchema = z.enum(USER_ROLES);
export type UserRole = z.infer<typeof userRoleSchema>;

const meSchema = z
  .object({
    id: z.string().min(1).max(128),
    role: userRoleSchema,
    status: z.enum(["active", "deletion_pending", "suspended"]),
    createdAt: z.string().datetime(),
    deletionPending: z.boolean(),
    requiredOidcRole: z.enum(["clinician", "admin"]).nullable(),
    privilegedAccessReady: z.boolean(),
    clinicianApplicationEligible: z.boolean(),
  })
  .strict();

const scanSessionSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    scanSessionId: z.string().min(1).max(128),
    consentRecordId: z.string().min(1).max(128).nullable(),
    protocol: z.enum([
      "standard_eight_region",
      "detailed_multi_angle",
      "guided_video_sweep",
    ]),
    status: z.enum([
      "draft",
      "capturing",
      "complete",
      "processing",
      "ready",
      "failed",
      "deleted",
    ]),
    createdAt: z.string().datetime(),
    updatedAt: z.string().datetime(),
    completedAt: z.string().datetime().nullable(),
  })
  .strict();

const scanSessionListSchema = z
  .object({
    items: z.array(scanSessionSchema),
    nextCursor: z.string().datetime().nullable(),
  })
  .strict();

const captureSetListSchema = z
  .object({
    items: z.array(captureSetSchema),
    nextCursor: z.string().nullable(),
  })
  .strict();

const reportListSchema = z
  .object({
    items: z.array(reportArtifactSchema),
    nextCursor: z.string().datetime().nullable(),
  })
  .strict();

const jobSchema = z
  .object({
    jobId: z.string().min(1).max(128),
    ownerId: z.string().min(1).max(128),
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
    inputRefs: z.array(z.string().min(1).max(128)).max(128),
    outputRefs: z.array(z.string().min(1).max(128)).max(128),
    progress: z.number().min(0).max(1),
    attempt: z.number().int().nonnegative(),
    maxAttempts: z.number().int().positive().max(20),
    errorCode: z.string().nullable(),
    errorMessage: z.string().nullable(),
    createdAt: z.string().datetime(),
    startedAt: z.string().datetime().nullable(),
    completedAt: z.string().datetime().nullable(),
    expiresAt: z.string().datetime(),
    outcome: z
      .enum(["complete", "unavailable", "cancelled", "failed"])
      .nullable(),
    reasonCode: z.string().nullable(),
    result: z.record(z.string(), z.unknown()).nullable(),
    cancellationRequested: z.boolean(),
  })
  .strict();

const jobListSchema = z
  .object({
    items: z.array(jobSchema),
    nextCursor: z.string().datetime().nullable(),
  })
  .strict();

const generatedArtifactSchema = z
  .object({
    artifactId: z.string().min(1).max(128),
    ownerId: z.string().min(1).max(128),
    jobId: z.string().min(1).max(128),
    purpose: z.enum(["reconstruction", "summary_video"]),
    filename: z.string().min(1).max(120),
    mediaType: z.enum(["model/gltf-binary", "video/mp4"]),
    sha256: z.string().regex(/^[a-f0-9]{64}$/),
    sizeBytes: z.number().int().positive().max(100_000_000),
    objectKey: z.string().min(1),
    manifest: z.record(z.string(), z.unknown()),
    createdAt: z.string().datetime(),
    retentionExpiresAt: z.string().datetime(),
  })
  .strict();

const generatedArtifactListSchema = z
  .object({
    items: z.array(generatedArtifactSchema),
    nextCursor: z.string().datetime().nullable(),
  })
  .strict();

const deletionRequestSchema = z
  .object({
    requestId: z.string().min(1).max(128),
    jobId: z.string().min(1).max(128),
    status: z.enum(["requested", "in_progress", "completed", "failed"]),
    requestedAt: z.string().datetime(),
    startedAt: z.string().datetime().nullable(),
    completedAt: z.string().datetime().nullable(),
    errorCode: z.string().nullable(),
  })
  .strict();

const analyticsConsentSchema = z
  .object({
    enabled: z.boolean(),
    policyVersion: z.string().min(1).nullable(),
    updatedAt: z.string().datetime().nullable(),
  })
  .strict();

const analyticsNameSchema = z.enum([
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

const analyticsSummarySchema = z
  .object({
    days: z.number().int().min(1).max(30),
    minimumGroupSize: z.literal(5),
    groups: z.array(
      z
        .object({
          name: analyticsNameSchema,
          platform: z.enum(["ios", "android", "web"]),
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
          count: z.number().int().min(5),
        })
        .strict(),
    ),
    generatedAt: z.string().datetime(),
  })
  .strict();

export const shareResourceTypeSchema = z.enum([
  "scan_session",
  "report",
  "lesion",
  "analysis_run",
]);

const resourceRefSchema = z
  .object({
    resourceType: shareResourceTypeSchema,
    resourceId: z.string().min(1).max(64),
  })
  .strict();

const shareLinkSchema = z
  .object({
    shareId: z.string().min(1),
    patientUserId: z.string().min(1),
    status: z.enum(["active", "revoked"]),
    resources: z.array(resourceRefSchema),
    expiresAt: z.string().datetime(),
    maxExchanges: z.number().int().positive(),
    exchangeCount: z.number().int().nonnegative(),
    revokedAt: z.string().datetime().nullable(),
    createdAt: z.string().datetime(),
    retentionExpiresAt: z.string().datetime(),
    active: z.boolean(),
  })
  .strict();

const accessGrantSchema = z
  .object({
    grantId: z.string().min(1),
    patientUserId: z.string().min(1),
    clinicianUserId: z.string().min(1),
    status: z.enum(["active", "revoked"]),
    label: z.string().nullable(),
    resources: z.array(resourceRefSchema),
    reviewId: z.string().min(1),
    expiresAt: z.string().datetime(),
    revokedAt: z.string().datetime().nullable(),
    createdAt: z.string().datetime(),
    updatedAt: z.string().datetime(),
    retentionExpiresAt: z.string().datetime(),
    active: z.boolean(),
  })
  .strict();

const accessGrantListSchema = z
  .object({ items: z.array(accessGrantSchema) })
  .strict();

const shareCreateResponseSchema = z
  .object({
    share: shareLinkSchema,
    fragmentSecret: z.string().min(40).max(128),
    fragmentParameter: z.literal("secret"),
  })
  .strict();

const shareListSchema = z.object({ items: z.array(shareLinkSchema) }).strict();

const reviewAnnotationSchema = z
  .object({
    annotationId: z.string().min(1),
    reviewId: z.string().min(1),
    clinicianUserId: z.string().min(1),
    resource: resourceRefSchema,
    kind: z.enum([
      "note",
      "question",
      "follow_up",
      "measurement_context",
      "outline_adjustment",
      "location_correction",
      "insufficient_scan",
      "date_comparison",
    ]),
    body: z.string().min(1),
    createdAt: z.string().datetime(),
    retentionExpiresAt: z.string().datetime(),
  })
  .strict();

const clinicianReviewSchema = z
  .object({
    reviewId: z.string().min(1),
    grantId: z.string().min(1),
    patientUserId: z.string().min(1),
    clinicianUserId: z.string().min(1),
    status: z.enum(["pending", "in_review", "completed", "declined"]),
    summary: z.string().nullable(),
    resources: z.array(resourceRefSchema),
    annotations: z.array(reviewAnnotationSchema),
    grantExpiresAt: z.string().datetime(),
    grantRevokedAt: z.string().datetime().nullable(),
    createdAt: z.string().datetime(),
    updatedAt: z.string().datetime(),
    startedAt: z.string().datetime().nullable(),
    completedAt: z.string().datetime().nullable(),
    retentionExpiresAt: z.string().datetime(),
    accessActive: z.boolean(),
  })
  .strict();

const clinicianReviewQueueSchema = z
  .object({
    items: z.array(clinicianReviewSchema),
    nextCursor: z.string().nullable(),
  })
  .strict();

const accessHistoryItemSchema = z
  .object({
    eventId: z.string().min(1),
    actorUserId: z.string().nullable(),
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
    resourceId: z.string().nullable(),
    grantId: z.string().nullable(),
    shareId: z.string().nullable(),
    reviewId: z.string().nullable(),
    details: z.record(z.string(), z.unknown()),
    createdAt: z.string().datetime(),
    retentionExpiresAt: z.string().datetime(),
  })
  .strict();

const accessHistorySchema = z
  .object({
    items: z.array(accessHistoryItemSchema),
    nextCursor: z.string().nullable(),
  })
  .strict();

const shareExchangeSchema = z
  .object({
    exchangeToken: z.string().min(40).max(128),
    authorizationScheme: z.literal("Share"),
    expiresAt: z.string().datetime(),
    maxUses: z.number().int().positive(),
  })
  .strict();

const shareViewerScopeSchema = z
  .object({
    shareId: z.string().min(1),
    resources: z.array(resourceRefSchema),
    shareExpiresAt: z.string().datetime(),
    tokenExpiresAt: z.string().datetime(),
    remainingUses: z.number().int().nonnegative(),
  })
  .strict();

const resourceViewSchema = z
  .object({
    resourceType: shareResourceTypeSchema,
    resourceId: z.string().min(1),
    data: z.record(z.string(), z.unknown()),
    disclaimer: z.literal("This result is not a diagnosis."),
  })
  .strict();

const apiErrorSchema = z
  .object({
    error: z.object({
      code: z.string().min(1),
      message: z.string().min(1),
      requestId: z.string().min(1),
    }),
  })
  .strict();

export type PlatformMe = z.infer<typeof meSchema>;
export type ScanSession = z.infer<typeof scanSessionSchema>;
export type PatientJob = z.infer<typeof jobSchema>;
export type GeneratedArtifact = z.infer<typeof generatedArtifactSchema>;
export type DeletionRequest = z.infer<typeof deletionRequestSchema>;
export type AnalyticsConsent = z.infer<typeof analyticsConsentSchema>;
export type AnalyticsSummary = z.infer<typeof analyticsSummarySchema>;
export type ShareResourceType = z.infer<typeof shareResourceTypeSchema>;
export type ResourceRef = z.infer<typeof resourceRefSchema>;
export type ClinicianVerification = z.infer<typeof clinicianVerificationSchema>;
export type ShareLink = z.infer<typeof shareLinkSchema>;
export type AccessGrant = z.infer<typeof accessGrantSchema>;
export type ShareCreateResponse = z.infer<typeof shareCreateResponseSchema>;
export type ClinicianReview = z.infer<typeof clinicianReviewSchema>;
export type ReviewAnnotation = z.infer<typeof reviewAnnotationSchema>;
export type AccessHistory = z.infer<typeof accessHistorySchema>;
export type ShareViewerScope = z.infer<typeof shareViewerScopeSchema>;
export type ResourceView = z.infer<typeof resourceViewSchema>;

export class PlatformApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "PlatformApiError";
  }
}

function platformBaseUrl(): string {
  const raw = process.env.ORALSIGHT_PLATFORM_API_URL;
  if (!raw) {
    throw new PlatformApiError(
      "The OralSight service has not been connected.",
      "platform_not_configured",
      503,
    );
  }
  const url = new URL(raw);
  if (
    process.env.NODE_ENV === "production" &&
    url.protocol !== "https:" &&
    url.hostname !== "localhost"
  ) {
    throw new PlatformApiError(
      "The OralSight service must use HTTPS.",
      "platform_https_required",
      503,
    );
  }
  return url.toString().replace(/\/$/, "");
}

async function accessToken(): Promise<string> {
  const result = await getAuth0Client().getAccessToken();
  const token =
    typeof result === "string" ? result : (result as { token?: string }).token;
  if (!token) {
    throw new PlatformApiError(
      "Your secure session needs to be renewed.",
      "access_token_unavailable",
      401,
    );
  }
  return token;
}

async function platformRequest<T>(
  path: `/v2/${string}` | "/v2/me",
  schema: z.ZodType<T>,
  init: RequestInit = {},
  authentication: "session" | "none" | { shareToken: string } = "session",
): Promise<T> {
  const response = await platformFetch(path, init, authentication);
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw platformResponseError(response, payload);
  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new PlatformApiError(
      "The service returned data OralSight could not verify.",
      "invalid_platform_response",
      502,
    );
  }
  return parsed.data;
}

async function platformFetch(
  path: `/v2/${string}` | "/v2/me",
  init: RequestInit = {},
  authentication: "session" | "none" | { shareToken: string } = "session",
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.delete("Authorization");
  if (authentication === "session") {
    headers.set("Authorization", `Bearer ${await accessToken()}`);
  } else if (authentication !== "none") {
    headers.set("Authorization", `Share ${authentication.shareToken}`);
  }
  let response: Response;
  try {
    response = await fetch(`${platformBaseUrl()}${path}`, {
      ...init,
      cache: "no-store",
      headers,
      signal: AbortSignal.timeout(8_000),
    });
  } catch {
    throw new PlatformApiError(
      "The OralSight service could not be reached. Try again.",
      "platform_unreachable",
      503,
    );
  }
  return response;
}

function platformResponseError(response: Response, payload: unknown) {
  const parsed = apiErrorSchema.safeParse(payload);
  return new PlatformApiError(
    parsed.success
      ? parsed.data.error.message
      : "The OralSight service could not complete this request.",
    parsed.success ? parsed.data.error.code : "platform_request_failed",
    response.status,
    parsed.success ? parsed.data.error.requestId : undefined,
  );
}

async function platformContentRequest(
  path: `/v2/${string}`,
  authentication: "session" | { shareToken: string } = "session",
): Promise<Response> {
  const response = await platformFetch(path, {}, authentication);
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw platformResponseError(response, payload);
  }
  return response;
}

function resourceId(value: string): string {
  const trimmed = value.trim();
  if (!/^[A-Za-z0-9._:-]{1,128}$/.test(trimmed)) {
    throw new PlatformApiError(
      "Enter a valid OralSight record ID.",
      "invalid_resource_id",
      400,
    );
  }
  return encodeURIComponent(trimmed);
}

export function getMe(): Promise<PlatformMe> {
  return platformRequest("/v2/me", meSchema);
}

export function getScanSession(id: string): Promise<ScanSession> {
  return platformRequest(
    `/v2/scan-sessions/${resourceId(id)}`,
    scanSessionSchema,
  );
}

export function listScanSessions(
  before?: string,
  limit = 25,
): Promise<{ items: ScanSession[]; nextCursor: string | null }> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (before) query.set("before", before);
  return platformRequest(
    `/v2/scan-sessions?${query.toString()}`,
    scanSessionListSchema,
  );
}

export function listScanCaptureSets(
  scanSessionId: string,
): Promise<{ items: CaptureSet[]; nextCursor: string | null }> {
  return platformRequest(
    `/v2/scan-sessions/${resourceId(scanSessionId)}/capture-sets`,
    captureSetListSchema,
  );
}

export function getCaptureSet(id: string): Promise<CaptureSet> {
  return platformRequest(
    `/v2/capture-sets/${resourceId(id)}`,
    captureSetSchema,
  );
}

export function getReport(id: string): Promise<ReportArtifact> {
  return platformRequest(`/v2/reports/${resourceId(id)}`, reportArtifactSchema);
}

export function getReportContent(id: string): Promise<Response> {
  return platformContentRequest(`/v2/reports/${resourceId(id)}/content`);
}

export function getClinicianReviewReportContent(
  reviewId: string,
  reportId: string,
): Promise<Response> {
  return platformContentRequest(
    `/v2/clinician/reviews/${resourceId(reviewId)}/resources/report/${resourceId(reportId)}/content`,
  );
}

export function getClinicianCaptureViewContent(
  reviewId: string,
  captureViewId: string,
): Promise<Response> {
  return platformContentRequest(
    `/v2/clinician/reviews/${resourceId(reviewId)}/capture-views/${resourceId(captureViewId)}/content`,
  );
}

export function getShareViewerReportContent(
  shareToken: string,
  reportId: string,
): Promise<Response> {
  return platformContentRequest(
    `/v2/share-viewer/resources/report/${resourceId(reportId)}/content`,
    { shareToken },
  );
}

export function listReports(
  before?: string,
  limit = 25,
): Promise<{ items: ReportArtifact[]; nextCursor: string | null }> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (before) query.set("before", before);
  return platformRequest(`/v2/reports?${query.toString()}`, reportListSchema);
}

export function listJobs(
  before?: string,
  limit = 50,
): Promise<{ items: PatientJob[]; nextCursor: string | null }> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (before) query.set("before", before);
  return platformRequest(`/v2/jobs?${query.toString()}`, jobListSchema);
}

export function getGeneratedArtifact(id: string): Promise<GeneratedArtifact> {
  return platformRequest(
    `/v2/generated-artifacts/${resourceId(id)}`,
    generatedArtifactSchema,
  );
}

export function listGeneratedArtifacts(
  before?: string,
  limit = 25,
): Promise<{ items: GeneratedArtifact[]; nextCursor: string | null }> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (before) query.set("before", before);
  return platformRequest(
    `/v2/generated-artifacts?${query.toString()}`,
    generatedArtifactListSchema,
  );
}

export function getGeneratedArtifactContent(id: string): Promise<Response> {
  return platformContentRequest(
    `/v2/generated-artifacts/${resourceId(id)}/content`,
  );
}

export function getCaptureAssetContent(id: string): Promise<Response> {
  return platformContentRequest(`/v2/capture-assets/${resourceId(id)}/content`);
}

export function requestAccountDeletion(
  idempotencyKey: string,
): Promise<DeletionRequest> {
  return platformRequest("/v2/me/deletion-requests", deletionRequestSchema, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify({ confirmation: "DELETE" }),
  });
}

export function getAccountDeletionRequest(
  id: string,
): Promise<DeletionRequest> {
  return platformRequest(
    `/v2/me/deletion-requests/${resourceId(id)}`,
    deletionRequestSchema,
  );
}

export function getAnalyticsConsent(): Promise<AnalyticsConsent> {
  return platformRequest("/v2/me/analytics-consent", analyticsConsentSchema);
}

export function updateAnalyticsConsent(
  enabled: boolean,
): Promise<AnalyticsConsent> {
  return platformRequest("/v2/me/analytics-consent", analyticsConsentSchema, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled, policyVersion: "analytics-v1" }),
  });
}

export function getAdminAnalyticsSummary(days = 30): Promise<AnalyticsSummary> {
  if (!Number.isInteger(days) || days < 1 || days > 30) {
    throw new PlatformApiError(
      "The analytics date range is invalid.",
      "invalid_analytics_range",
      400,
    );
  }
  return platformRequest(
    `/v2/admin/analytics/summary?days=${days}`,
    analyticsSummarySchema,
  );
}

export function submitClinicianVerification(
  body: {
    profession: string;
    licenseJurisdiction: string;
    licenseNumber: string;
    organization: string | null;
    applicantEvidenceRef: string;
  },
  idempotencyKey: string,
): Promise<ClinicianVerification> {
  return platformRequest(
    "/v2/clinician-verifications",
    clinicianVerificationSchema,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    },
  );
}

export function getCurrentClinicianVerification(): Promise<ClinicianVerification> {
  return platformRequest(
    "/v2/clinician-verifications/current",
    clinicianVerificationSchema,
  );
}

export function activateCurrentClinicianVerification(): Promise<ClinicianVerification> {
  return platformRequest(
    "/v2/clinician-verifications/current/activate",
    clinicianVerificationSchema,
    { method: "POST" },
  );
}

export function listClinicianVerifications(
  status: ClinicianVerification["status"] = "pending",
): Promise<{ items: ClinicianVerification[]; nextCursor: string | null }> {
  return platformRequest(
    `/v2/admin/clinician-verifications?status=${status}`,
    clinicianVerificationQueueSchema,
  );
}

export function decideClinicianVerification(
  verificationId: string,
  body: {
    status: "verified" | "rejected";
    decisionReason: string | null;
    evidence: {
      source: string;
      referenceId: string;
      checkedAt: string;
      reviewerNotes: string | null;
    };
  },
  idempotencyKey: string,
): Promise<ClinicianVerification> {
  return platformRequest(
    `/v2/admin/clinician-verifications/${resourceId(verificationId)}/decision`,
    clinicianVerificationSchema,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    },
  );
}

export function listClinicianReviews(
  status?: ClinicianReview["status"],
): Promise<{ items: ClinicianReview[]; nextCursor: string | null }> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return platformRequest(
    `/v2/clinician/reviews${query}`,
    clinicianReviewQueueSchema,
  );
}

export function getClinicianReview(id: string): Promise<ClinicianReview> {
  return platformRequest(
    `/v2/clinician/reviews/${resourceId(id)}`,
    clinicianReviewSchema,
  );
}

export function getClinicianReviewResource(
  reviewId: string,
  resource: ResourceRef,
): Promise<ResourceView> {
  return platformRequest(
    `/v2/clinician/reviews/${resourceId(reviewId)}/resources/${resource.resourceType}/${resourceId(resource.resourceId)}`,
    resourceViewSchema,
  );
}

export function updateClinicianReviewStatus(
  reviewId: string,
  body: {
    status: "in_review" | "completed" | "declined";
    summary: string | null;
  },
  idempotencyKey: string,
): Promise<ClinicianReview> {
  return platformRequest(
    `/v2/clinician/reviews/${resourceId(reviewId)}/status`,
    clinicianReviewSchema,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    },
  );
}

export function createReviewAnnotation(
  reviewId: string,
  body: {
    resource: ResourceRef;
    kind: ReviewAnnotation["kind"];
    body: string;
  },
  idempotencyKey: string,
): Promise<ReviewAnnotation> {
  return platformRequest(
    `/v2/clinician/reviews/${resourceId(reviewId)}/annotations`,
    reviewAnnotationSchema,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    },
  );
}

export function createShare(
  body: {
    resources: ResourceRef[];
    expiresInSeconds: number;
    maxExchanges: number;
  },
  idempotencyKey: string,
): Promise<ShareCreateResponse> {
  return platformRequest("/v2/shares", shareCreateResponseSchema, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(body),
  });
}

export function createAccessGrant(
  body: {
    clinicianUserId: string;
    resources: ResourceRef[];
    label: string | null;
    expiresAt: string | null;
  },
  idempotencyKey: string,
): Promise<AccessGrant> {
  return platformRequest("/v2/access-grants", accessGrantSchema, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(body),
  });
}

export function listAccessGrants(): Promise<{ items: AccessGrant[] }> {
  return platformRequest("/v2/access-grants", accessGrantListSchema);
}

export function revokeAccessGrant(
  grantId: string,
  idempotencyKey: string,
): Promise<AccessGrant> {
  return platformRequest(
    `/v2/access-grants/${resourceId(grantId)}/revoke`,
    accessGrantSchema,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
    },
  );
}

export function listShareGrants(): Promise<{ items: ShareLink[] }> {
  return platformRequest("/v2/shares", shareListSchema);
}

export function revokeShare(
  shareId: string,
  idempotencyKey: string,
): Promise<ShareLink> {
  return platformRequest(
    `/v2/shares/${resourceId(shareId)}/revoke`,
    shareLinkSchema,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
    },
  );
}

export function getAccessHistory(): Promise<AccessHistory> {
  return platformRequest("/v2/access-history", accessHistorySchema);
}

export function exchangeShareSecret(
  body: { shareId: string; secret: string },
  idempotencyKey: string,
) {
  return platformRequest(
    "/v2/share-exchanges",
    shareExchangeSchema,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    },
    "none",
  );
}

export function getShareViewerScope(
  shareToken: string,
): Promise<ShareViewerScope> {
  return platformRequest(
    "/v2/share-viewer/resources",
    shareViewerScopeSchema,
    {},
    { shareToken },
  );
}

export function getShareViewerResource(
  shareToken: string,
  resource: ResourceRef,
): Promise<ResourceView> {
  return platformRequest(
    `/v2/share-viewer/resources/${resource.resourceType}/${resourceId(resource.resourceId)}`,
    resourceViewSchema,
    {},
    { shareToken },
  );
}

export const platformSchemasForTesting = {
  me: meSchema,
  scanSession: scanSessionSchema,
  scanSessionList: scanSessionListSchema,
  captureSet: captureSetSchema,
  reportList: reportListSchema,
  job: jobSchema,
  generatedArtifact: generatedArtifactSchema,
  generatedArtifactList: generatedArtifactListSchema,
  deletionRequest: deletionRequestSchema,
  analyticsConsent: analyticsConsentSchema,
  analyticsSummary: analyticsSummarySchema,
  clinicianVerification: clinicianVerificationSchema,
  clinicianReview: clinicianReviewSchema,
  shareLink: shareLinkSchema,
  accessGrant: accessGrantSchema,
  accessHistory: accessHistorySchema,
  resourceView: resourceViewSchema,
};
