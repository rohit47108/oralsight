import * as Network from "expo-network";
import { z, type ZodType } from "zod";

import {
  accessHistoryResponseSchema,
  ANALYTICS_POLICY_VERSION,
  analyticsAcceptedSchema,
  analyticsConsentSchema,
  analysisRunSchema,
  assetFinalizeResponseSchema,
  assetUploadTicketSchema,
  captureSetResponseSchema,
  consentDocumentSchema,
  productConsentListSchema,
  productConsentSchema,
  deletionResponseSchema,
  deviceResponseSchema,
  generatedArtifactSchema,
  reportArtifactSchema,
  dataExportArtifactSchema,
  jobListResponseSchema,
  jobResponseSchema,
  matchDecisionSchema,
  matchProposalSchema,
  lesionSchema,
  meResponseSchema,
  scanSessionResponseSchema,
  shareCreateResponseSchema,
  shareLinkSchema,
  shareListSchema,
  syncPullResponseSchema,
  syncPushResponseSchema,
  type AccessHistoryResponse,
  type AnalyticsConsent,
  type AnalyticsEvent,
  type AnalysisRun,
  type AssetUploadTicket,
  type CaptureAssetInput,
  type CaptureSetResponse,
  type ConsentDocument,
  type ProductConsent,
  type DeletionResponse,
  type DeviceResponse,
  type GeneratedArtifact,
  type ReportArtifact,
  type DataExportArtifact,
  type JobListResponse,
  type JobResponse,
  type MatchDecision,
  type MatchProposal,
  type Lesion,
  type MeResponse,
  type ResourceRef,
  type ScanSessionResponse,
  type ShareCreateResponse,
  type ShareLink,
  type SyncOperationInput,
  type SyncPullResponse,
  type SyncPushResponse,
} from "./contracts";
import { readCloudConfig } from "./config";
import { CloudError, cloudErrorFromStatus } from "./errors";
import { cloudAccessToken } from "./session";

type JsonValue =
  null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export interface PlatformClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  tokenProvider?: () => Promise<string>;
  online?: () => Promise<boolean>;
  timeoutMs?: number;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: JsonValue | Record<string, unknown>;
  idempotencyKey?: string;
  signal?: AbortSignal;
  token?: string;
}

const errorResponseSchema = z
  .object({
    error: z
      .object({
        code: z.string().optional(),
        message: z.string().optional(),
        requestId: z.string().optional(),
      })
      .passthrough(),
  })
  .passthrough();

export function newIdempotencyKey(scope: string): string {
  const safeScope = scope.replace(/[^A-Za-z0-9._:-]/g, "_").slice(0, 40);
  const random =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${safeScope}:${random}`.slice(0, 128);
}

function mergeSignals(
  external: AbortSignal | undefined,
  timeoutMs: number,
): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("timeout"), timeoutMs);
  const relay = () => controller.abort(external?.reason ?? "cancelled");
  external?.addEventListener("abort", relay, { once: true });
  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timeout);
      external?.removeEventListener("abort", relay);
    },
  };
}

async function defaultOnline(): Promise<boolean> {
  const state = await Network.getNetworkStateAsync().catch(() => null);
  return state?.isConnected !== false && state?.isInternetReachable !== false;
}

export class PlatformClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly tokenProvider: () => Promise<string>;
  private readonly online: () => Promise<boolean>;
  private readonly timeoutMs: number;

  constructor(options: PlatformClientOptions = {}) {
    const config = readCloudConfig();
    const rawBaseUrl = options.baseUrl ?? config?.platformBaseUrl;
    if (!rawBaseUrl) {
      throw new CloudError({
        code: "upload_unavailable",
        message: "Account services are not configured in this build.",
      });
    }
    this.baseUrl = rawBaseUrl.replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.tokenProvider = options.tokenProvider ?? cloudAccessToken;
    this.online = options.online ?? defaultOnline;
    this.timeoutMs = options.timeoutMs ?? config?.requestTimeoutMs ?? 20_000;
  }

  async request<T>(
    path: string,
    schema: ZodType<T>,
    options: RequestOptions = {},
  ): Promise<T> {
    if (!(await this.online())) {
      throw new CloudError({
        code: "offline",
        message:
          "You are offline. This change is saved on this device and can retry later.",
        retryable: true,
      });
    }
    const token = options.token ?? (await this.tokenProvider());
    const { signal, cleanup } = mergeSignals(options.signal, this.timeoutMs);
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        method: options.method ?? "GET",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
          "Cache-Control": "no-store",
          ...(options.body === undefined
            ? {}
            : { "Content-Type": "application/json" }),
          ...(options.idempotencyKey
            ? { "Idempotency-Key": options.idempotencyKey }
            : {}),
        },
        ...(options.body === undefined
          ? {}
          : { body: JSON.stringify(options.body) }),
        signal,
      });
    } catch (cause) {
      const timedOut = signal.aborted && !options.signal?.aborted;
      throw new CloudError({
        code: timedOut
          ? "timeout"
          : options.signal?.aborted
            ? "cancelled"
            : "offline",
        message: timedOut
          ? "The request timed out. It can be retried safely."
          : options.signal?.aborted
            ? "The request was cancelled."
            : "The service could not be reached. This can retry later.",
        retryable: !options.signal?.aborted,
        cause,
      });
    } finally {
      cleanup();
    }

    const requestId = response.headers.get("x-request-id") ?? undefined;
    let json: unknown = null;
    if (response.status !== 204) {
      try {
        json = await response.json();
      } catch {
        if (response.ok) {
          throw new CloudError({
            code: "invalid_response",
            message: "The service returned an unreadable response.",
            requestId,
          });
        }
      }
    }
    if (!response.ok) {
      const parsed = errorResponseSchema.safeParse(json);
      throw cloudErrorFromStatus(response.status, {
        requestId: parsed.success
          ? (parsed.data.error.requestId ?? requestId)
          : requestId,
        serverCode: parsed.success ? parsed.data.error.code : undefined,
        serverMessage: parsed.success ? parsed.data.error.message : undefined,
      });
    }
    const parsed = schema.safeParse(json);
    if (!parsed.success) {
      throw new CloudError({
        code: "invalid_response",
        message: "The service response did not match this app version.",
        requestId,
      });
    }
    return parsed.data;
  }

  account(): Promise<MeResponse> {
    return this.request("/v2/me", meResponseSchema);
  }

  currentConsentDocument(): Promise<ConsentDocument> {
    return this.request("/v2/consent-documents/current", consentDocumentSchema);
  }

  listProductConsents(): Promise<{ items: ProductConsent[] }> {
    return this.request("/v2/consents", productConsentListSchema);
  }

  createProductConsent(
    document: ConsentDocument,
    idempotencyKey: string,
    deviceId?: string,
  ): Promise<ProductConsent> {
    return this.request("/v2/consents", productConsentSchema, {
      method: "POST",
      body: {
        documentId: document.documentId,
        documentVersion: document.documentVersion,
        documentSha256: document.documentSha256,
        accepted: true,
        ...(deviceId ? { deviceId } : {}),
      },
      idempotencyKey,
    });
  }

  revokeProductConsent(
    consentRecordId: string,
    idempotencyKey: string,
  ): Promise<ProductConsent> {
    return this.request(
      `/v2/consents/${encodeURIComponent(consentRecordId)}/revoke`,
      productConsentSchema,
      {
        method: "POST",
        body: { confirmation: "REVOKE" },
        idempotencyKey,
      },
    );
  }

  registerDevice(
    body: {
      installationId: string;
      platform: "ios" | "android" | "web";
      displayName?: string | null;
      publicKey?: string | null;
    },
    idempotencyKey: string,
  ): Promise<DeviceResponse> {
    return this.request("/v2/devices", deviceResponseSchema, {
      method: "POST",
      body,
      idempotencyKey,
    });
  }

  createScanSession(
    body: {
      protocol: string;
      deviceId?: string | null;
      consentRecordId: string;
    },
    idempotencyKey: string,
  ): Promise<ScanSessionResponse> {
    return this.request("/v2/scan-sessions", scanSessionResponseSchema, {
      method: "POST",
      body,
      idempotencyKey,
    });
  }

  createCaptureSet(
    scanSessionId: string,
    body: { region: string; protocol: string },
    idempotencyKey: string,
  ): Promise<CaptureSetResponse> {
    return this.request(
      `/v2/scan-sessions/${encodeURIComponent(scanSessionId)}/capture-sets`,
      captureSetResponseSchema,
      { method: "POST", body, idempotencyKey },
    );
  }

  createCaptureView(
    captureSetId: string,
    body: Record<string, unknown>,
    idempotencyKey: string,
  ): Promise<CaptureSetResponse> {
    return this.request(
      `/v2/capture-sets/${encodeURIComponent(captureSetId)}/views`,
      captureSetResponseSchema,
      { method: "POST", body, idempotencyKey },
    );
  }

  requestAssetUpload(assetId: string): Promise<AssetUploadTicket> {
    return this.request(
      `/v2/capture-assets/${encodeURIComponent(assetId)}/upload-intent`,
      assetUploadTicketSchema,
      { method: "POST" },
    );
  }

  finalizeAssetUpload(assetId: string) {
    return this.request(
      `/v2/capture-assets/${encodeURIComponent(assetId)}/finalize`,
      assetFinalizeResponseSchema,
      { method: "POST" },
    );
  }

  requestAssetDownload(assetId: string): Promise<AssetUploadTicket> {
    return this.request(
      `/v2/capture-assets/${encodeURIComponent(assetId)}/download-intent`,
      assetUploadTicketSchema,
      { method: "POST" },
    );
  }

  pushSync(
    operations: SyncOperationInput[],
    idempotencyKey: string,
  ): Promise<SyncPushResponse> {
    return this.request("/v2/sync/push", syncPushResponseSchema, {
      method: "POST",
      body: { operations },
      idempotencyKey,
    });
  }

  pullSync(cursor?: string, limit = 100): Promise<SyncPullResponse> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return this.request(`/v2/sync/pull?${query}`, syncPullResponseSchema);
  }

  createShare(
    resources: ResourceRef[],
    options: { expiresInSeconds?: number; maxExchanges?: number } = {},
    idempotencyKey: string,
  ): Promise<ShareCreateResponse> {
    return this.request("/v2/shares", shareCreateResponseSchema, {
      method: "POST",
      body: {
        resources,
        expiresInSeconds: options.expiresInSeconds ?? 86_400,
        maxExchanges: options.maxExchanges ?? 1,
      },
      idempotencyKey,
    });
  }

  listShares(): Promise<{ items: ShareLink[] }> {
    return this.request("/v2/shares", shareListSchema);
  }

  revokeShare(shareId: string, idempotencyKey: string): Promise<ShareLink> {
    return this.request(
      `/v2/shares/${encodeURIComponent(shareId)}/revoke`,
      shareLinkSchema,
      { method: "POST", idempotencyKey },
    );
  }

  accessHistory(cursor?: string): Promise<AccessHistoryResponse> {
    const path = cursor
      ? `/v2/access-history?cursor=${encodeURIComponent(cursor)}`
      : "/v2/access-history";
    return this.request(path, accessHistoryResponseSchema);
  }

  createJob(
    type:
      | "analysis"
      | "comparison"
      | "reconstruction"
      | "report"
      | "summary_video"
      | "data_export",
    payload: Record<string, unknown>,
    idempotencyKey: string,
    inputRefs: string[] = [],
  ): Promise<JobResponse> {
    return this.request("/v2/jobs", jobResponseSchema, {
      method: "POST",
      body: { type, inputRefs, payload, maxAttempts: 3 },
      idempotencyKey,
    });
  }

  listJobs(before?: string): Promise<JobListResponse> {
    const path = before
      ? `/v2/jobs?before=${encodeURIComponent(before)}&limit=50`
      : "/v2/jobs?limit=50";
    return this.request(path, jobListResponseSchema);
  }

  job(jobId: string): Promise<JobResponse> {
    return this.request(
      `/v2/jobs/${encodeURIComponent(jobId)}`,
      jobResponseSchema,
    );
  }

  generatedArtifact(artifactId: string): Promise<GeneratedArtifact> {
    return this.request(
      `/v2/generated-artifacts/${encodeURIComponent(artifactId)}`,
      generatedArtifactSchema,
    );
  }

  analysisRun(analysisRunId: string): Promise<AnalysisRun> {
    return this.request(
      `/v2/analysis-runs/${encodeURIComponent(analysisRunId)}`,
      analysisRunSchema,
    );
  }

  createMatchProposal(
    body: {
      currentObservationId: string;
      candidatePriorObservationId: string;
      candidateLesionId: string | null;
      proposalOrigin: "automatic_model" | "user_selected";
      score: number | null;
      rank: number | null;
      modelVersions: Record<string, string>;
      expiresAt: string | null;
    },
    idempotencyKey: string,
  ): Promise<MatchProposal> {
    return this.request("/v2/match-proposals", matchProposalSchema, {
      method: "POST",
      body,
      idempotencyKey,
    });
  }

  createLesion(
    body: { firstObservationId: string; label: string | null },
    idempotencyKey: string,
  ): Promise<Lesion> {
    return this.request("/v2/lesions", lesionSchema, {
      method: "POST",
      body,
      idempotencyKey,
    });
  }

  decideMatchProposal(
    proposalId: string,
    body: {
      decision: "confirmed" | "rejected" | "deferred";
      rationale: string | null;
    },
    idempotencyKey: string,
  ): Promise<MatchDecision> {
    return this.request(
      `/v2/match-proposals/${encodeURIComponent(proposalId)}/decisions`,
      matchDecisionSchema,
      { method: "POST", body, idempotencyKey },
    );
  }

  report(reportId: string): Promise<ReportArtifact> {
    return this.request(
      `/v2/reports/${encodeURIComponent(reportId)}`,
      reportArtifactSchema,
    );
  }

  dataExport(artifactId: string): Promise<DataExportArtifact> {
    return this.request(
      `/v2/data-exports/${encodeURIComponent(artifactId)}`,
      dataExportArtifactSchema,
    );
  }

  cancelJob(jobId: string, idempotencyKey: string): Promise<JobResponse> {
    return this.request(
      `/v2/jobs/${encodeURIComponent(jobId)}/cancel`,
      jobResponseSchema,
      { method: "POST", idempotencyKey },
    );
  }

  requestAccountDeletion(idempotencyKey: string): Promise<DeletionResponse> {
    return this.request("/v2/me/deletion-requests", deletionResponseSchema, {
      method: "POST",
      body: { confirmation: "DELETE" },
      idempotencyKey,
    });
  }

  deletionStatus(requestId: string): Promise<DeletionResponse> {
    return this.request(
      `/v2/me/deletion-requests/${encodeURIComponent(requestId)}`,
      deletionResponseSchema,
    );
  }

  analyticsConsent(): Promise<AnalyticsConsent> {
    return this.request("/v2/me/analytics-consent", analyticsConsentSchema);
  }

  updateAnalyticsConsent(enabled: boolean): Promise<AnalyticsConsent> {
    return this.request("/v2/me/analytics-consent", analyticsConsentSchema, {
      method: "PUT",
      body: { enabled, policyVersion: ANALYTICS_POLICY_VERSION },
    });
  }

  submitAnalytics(
    events: AnalyticsEvent[],
  ): Promise<{ accepted: number; retentionDays: 30 }> {
    return this.request("/v2/analytics/events", analyticsAcceptedSchema, {
      method: "POST",
      body: { events },
    });
  }
}
