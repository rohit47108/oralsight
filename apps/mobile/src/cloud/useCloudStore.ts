import { create } from "zustand";

import {
  clearCloudState,
  cloudMetadata,
  updateCloudMetadata,
} from "@/lib/storage";
import { useOralSightStore } from "@/store/useOralSightStore";

import {
  registerCloudBackgroundSync,
  unregisterCloudBackgroundSync,
} from "./background";
import { trackProductEvent } from "./analytics";
import { PlatformClient, newIdempotencyKey } from "./client";
import { cloudConfigurationStatus, readCloudConfig } from "./config";
import type {
  AccessHistoryItem,
  AnalyticsConsent,
  ConsentDocument,
  DeletionResponse,
  GeneratedArtifact,
  JobResponse,
  MeResponse,
  ReportArtifact,
  DataExportArtifact,
  ProductConsent,
  ResourceRef,
  ShareLink,
} from "./contracts";
import { deleteCloudSyncKey, importCloudRecoveryCode } from "./crypto";
import { isCloudError } from "./errors";
import {
  clearCloudCredentials,
  restoreCloudSession,
  signInToCloud,
  signOutOfCloud,
} from "./session";
import { buildShareUrl } from "./shareUrl";
import { prepareCloudJob, type UserJobType } from "./jobLaunch";
import { syncEntityFingerprint } from "./syncModel";
import { loadProductConsentState } from "./consent";
import {
  clearCloudInstallationIdentity,
  cloudSyncSummary,
  rememberCloudSyncError,
  runCloudSync,
} from "./sync";

export type CloudSessionStatus =
  "checking" | "signed_out" | "signing_in" | "signed_in" | "unavailable";

interface CloudState {
  configured: boolean;
  configurationMessage: string;
  sessionStatus: CloudSessionStatus;
  account: MeResponse | null;
  busy: boolean;
  error: string | null;
  lastSyncAt: string | null;
  pendingOperations: number;
  syncError: string | null;
  recoveryCode: string | null;
  recoveryCodeWasCreated: boolean;
  shares: ShareLink[];
  latestShareUrl: string | null;
  shareUrls: Record<string, string>;
  accessHistory: AccessHistoryItem[];
  jobs: JobResponse[];
  artifacts: Record<string, GeneratedArtifact>;
  reportArtifacts: Record<string, ReportArtifact>;
  dataExports: Record<string, DataExportArtifact>;
  deletion: DeletionResponse | null;
  analyticsConsent: AnalyticsConsent | null;
  consentDocument: ConsentDocument | null;
  productConsent: ProductConsent | null;
  bootstrap: () => Promise<void>;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  syncNow: (confirmAccountRebind?: boolean) => Promise<void>;
  importRecoveryCode: (value: string) => Promise<void>;
  refreshAccountData: () => Promise<void>;
  createShare: (
    resources: ResourceRef[],
    options?: { expiresInSeconds?: number; maxExchanges?: number },
  ) => Promise<string>;
  revokeShare: (shareId: string) => Promise<void>;
  startJob: (type: UserJobType, localSessionId: string | null) => Promise<void>;
  refreshJob: (jobId: string) => Promise<void>;
  loadArtifact: (artifactId: string) => Promise<void>;
  loadJobOutput: (type: JobResponse["type"], outputId: string) => Promise<void>;
  cancelJob: (jobId: string) => Promise<void>;
  requestCloudDeletion: () => Promise<void>;
  refreshDeletion: () => Promise<void>;
  setAnalyticsOptIn: (enabled: boolean) => Promise<void>;
  acceptProductConsent: () => Promise<void>;
  revokeProductConsent: () => Promise<void>;
  clearError: () => void;
}

function friendlyError(error: unknown): string {
  if (isCloudError(error)) return error.message;
  return error instanceof Error
    ? error.message
    : "The account service could not complete this request.";
}

async function loadRemoteLists(client: PlatformClient) {
  const [shares, history, jobs] = await Promise.allSettled([
    client.listShares(),
    client.accessHistory(),
    client.listJobs(),
  ]);
  return {
    shares: shares.status === "fulfilled" ? shares.value.items : null,
    history: history.status === "fulfilled" ? history.value.items : null,
    jobs: jobs.status === "fulfilled" ? jobs.value.items : null,
  };
}

export const useCloudStore = create<CloudState>((set, get) => {
  const configuration = cloudConfigurationStatus();
  return {
    configured: configuration.configured,
    configurationMessage: configuration.message,
    sessionStatus: configuration.configured ? "checking" : "unavailable",
    account: null,
    busy: false,
    error: null,
    lastSyncAt: null,
    pendingOperations: 0,
    syncError: null,
    recoveryCode: null,
    recoveryCodeWasCreated: false,
    shares: [],
    latestShareUrl: null,
    shareUrls: {},
    accessHistory: [],
    jobs: [],
    artifacts: {},
    reportArtifacts: {},
    dataExports: {},
    deletion: null,
    analyticsConsent: null,
    consentDocument: null,
    productConsent: null,

    bootstrap: async () => {
      if (!configuration.configured) {
        set({ sessionStatus: "unavailable" });
        return;
      }
      try {
        const restored = await restoreCloudSession();
        if (!restored) {
          set({ sessionStatus: "signed_out" });
          return;
        }
        const client = new PlatformClient();
        const [
          account,
          summary,
          storedShareUrls,
          analyticsConsent,
          productConsentState,
        ] = await Promise.all([
          client.account(),
          cloudSyncSummary(),
          cloudMetadata("cloud.share_url."),
          client.analyticsConsent(),
          loadProductConsentState(client),
        ]);
        const cloudWorkEnabled = !account.deletionPending;
        useOralSightStore.getState().updateSettings({
          analyticsOptIn: cloudWorkEnabled && analyticsConsent.enabled,
        });
        set({
          account,
          analyticsConsent,
          consentDocument: productConsentState.document,
          productConsent: cloudWorkEnabled
            ? productConsentState.activeConsent
            : null,
          sessionStatus: "signed_in",
          lastSyncAt: summary.lastSyncAt,
          pendingOperations: summary.pending,
          syncError: summary.lastError,
          shareUrls: Object.fromEntries(
            Object.entries(storedShareUrls).flatMap(([key, value]) =>
              value
                ? [[key.slice("cloud.share_url.".length), value] as const]
                : [],
            ),
          ),
        });
        if (cloudWorkEnabled && productConsentState.activeConsent) {
          await registerCloudBackgroundSync().catch(() => undefined);
        }
        void trackProductEvent({
          name: "app_opened",
          surface: "app",
          outcome: "viewed",
        });
        if (cloudWorkEnabled && productConsentState.activeConsent)
          await get().syncNow();
      } catch (error) {
        if (isCloudError(error) && error.code === "unauthenticated") {
          await clearCloudCredentials().catch(() => undefined);
          set({ sessionStatus: "signed_out", account: null });
          return;
        }
        const summary = await cloudSyncSummary().catch(() => null);
        set({
          sessionStatus: "signed_in",
          error: friendlyError(error),
          ...(summary
            ? {
                lastSyncAt: summary.lastSyncAt,
                pendingOperations: summary.pending,
                syncError: summary.lastError,
              }
            : {}),
        });
      }
    },

    signIn: async () => {
      if (!get().configured) return;
      set({ busy: true, error: null, sessionStatus: "signing_in" });
      let authenticated = false;
      try {
        await signInToCloud();
        authenticated = true;
        const client = new PlatformClient();
        const [account, analyticsConsent, productConsentState] =
          await Promise.all([
            client.account(),
            client.analyticsConsent(),
            loadProductConsentState(client),
          ]);
        const cloudWorkEnabled = !account.deletionPending;
        useOralSightStore.getState().updateSettings({
          analyticsOptIn: cloudWorkEnabled && analyticsConsent.enabled,
        });
        set({
          account,
          analyticsConsent,
          consentDocument: productConsentState.document,
          productConsent: cloudWorkEnabled
            ? productConsentState.activeConsent
            : null,
          sessionStatus: "signed_in",
        });
        if (cloudWorkEnabled && productConsentState.activeConsent) {
          await registerCloudBackgroundSync().catch(() => undefined);
          await get().syncNow();
        }
        await get().refreshAccountData();
      } catch (error) {
        const sessionRejected =
          isCloudError(error) && error.code === "unauthenticated";
        if (authenticated && !sessionRejected) {
          set({
            sessionStatus: "signed_in",
            account: null,
            error: friendlyError(error),
          });
          return;
        }
        if (authenticated) {
          await clearCloudCredentials().catch(() => undefined);
        }
        set({
          sessionStatus: "signed_out",
          account: null,
          error: friendlyError(error),
        });
      } finally {
        set({ busy: false });
      }
    },

    signOut: async () => {
      set({ busy: true, error: null });
      try {
        await unregisterCloudBackgroundSync().catch(() => undefined);
        await signOutOfCloud();
        useOralSightStore.getState().updateSettings({ analyticsOptIn: false });
        set({
          sessionStatus: "signed_out",
          account: null,
          shares: [],
          accessHistory: [],
          jobs: [],
          artifacts: {},
          reportArtifacts: {},
          dataExports: {},
          latestShareUrl: null,
          shareUrls: {},
          recoveryCode: null,
          recoveryCodeWasCreated: false,
          deletion: null,
          analyticsConsent: null,
          consentDocument: null,
          productConsent: null,
        });
      } catch (error) {
        set({ error: friendlyError(error) });
      } finally {
        set({ busy: false });
      }
    },

    syncNow: async (confirmAccountRebind = false) => {
      if (get().sessionStatus !== "signed_in") return;
      if (!get().productConsent) {
        set({
          error:
            "Review and accept the current cloud consent before syncing health records.",
          syncError: "Cloud consent is required before sync.",
        });
        return;
      }
      set({ busy: true, error: null, syncError: null });
      try {
        const result = await runCloudSync(new PlatformClient(), {
          confirmAccountRebind,
        });
        set({
          lastSyncAt: result.completedAt,
          pendingOperations: result.pending,
          recoveryCode: result.recoveryCode,
          recoveryCodeWasCreated: result.recoveryCodeWasCreated,
        });
      } catch (error) {
        await rememberCloudSyncError(error).catch(() => undefined);
        const summary = await cloudSyncSummary().catch(() => null);
        set({
          error: friendlyError(error),
          syncError: friendlyError(error),
          ...(summary ? { pendingOperations: summary.pending } : {}),
        });
      } finally {
        set({ busy: false });
      }
    },

    importRecoveryCode: async (value) => {
      const account = get().account;
      if (!account) throw new Error("Sign in before restoring a sync key.");
      set({ busy: true, error: null, syncError: null });
      try {
        const material = await importCloudRecoveryCode(account.id, value);
        await updateCloudMetadata({ "cloud.cursor": null });
        set({
          recoveryCode: material.recoveryCode,
          recoveryCodeWasCreated: false,
        });
        await get().syncNow();
      } catch (error) {
        set({ error: friendlyError(error), syncError: friendlyError(error) });
        throw error;
      } finally {
        set({ busy: false });
      }
    },

    refreshAccountData: async () => {
      if (get().sessionStatus !== "signed_in") return;
      set({ busy: true, error: null });
      try {
        const client = new PlatformClient();
        const [account, lists, analyticsConsent, productConsentState] =
          await Promise.all([
            client.account(),
            loadRemoteLists(client),
            client.analyticsConsent(),
            loadProductConsentState(client),
          ]);
        const cloudWorkEnabled = !account.deletionPending;
        useOralSightStore.getState().updateSettings({
          analyticsOptIn: cloudWorkEnabled && analyticsConsent.enabled,
        });
        set({
          account,
          analyticsConsent,
          consentDocument: productConsentState.document,
          productConsent: cloudWorkEnabled
            ? productConsentState.activeConsent
            : null,
          ...(lists.shares ? { shares: lists.shares } : {}),
          ...(lists.history ? { accessHistory: lists.history } : {}),
          ...(lists.jobs ? { jobs: lists.jobs } : {}),
        });
      } catch (error) {
        set({ error: friendlyError(error) });
      } finally {
        set({ busy: false });
      }
    },

    createShare: async (resources, options = {}) => {
      if (resources.length === 0) throw new Error("Choose something to share.");
      if (!get().productConsent || get().account?.deletionPending) {
        throw new Error(
          "Cloud consent is required and account deletion must be inactive before sharing.",
        );
      }
      set({ busy: true, error: null, latestShareUrl: null });
      try {
        const client = new PlatformClient();
        const response = await client.createShare(
          resources,
          options,
          newIdempotencyKey("share"),
        );
        const config = readCloudConfig();
        if (!config) throw new Error("Share links are not configured.");
        const url = buildShareUrl(config.shareViewerBaseUrl, response);
        await updateCloudMetadata({
          [`cloud.share_url.${response.share.shareId}`]: url,
        });
        set((state) => ({
          latestShareUrl: url,
          shareUrls: {
            ...state.shareUrls,
            [response.share.shareId]: url,
          },
          shares: [
            response.share,
            ...state.shares.filter(
              (share) => share.shareId !== response.share.shareId,
            ),
          ],
        }));
        void trackProductEvent({
          name: "share_created",
          surface: "sharing",
          outcome: "shared",
        });
        return url;
      } catch (error) {
        set({ error: friendlyError(error) });
        throw error;
      } finally {
        set({ busy: false });
      }
    },

    revokeShare: async (shareId) => {
      set({ busy: true, error: null });
      try {
        const share = await new PlatformClient().revokeShare(
          shareId,
          newIdempotencyKey(`share-revoke:${shareId}`),
        );
        await updateCloudMetadata({ [`cloud.share_url.${shareId}`]: null });
        set((state) => ({
          shares: state.shares.map((value) =>
            value.shareId === shareId ? share : value,
          ),
          latestShareUrl: null,
          shareUrls: Object.fromEntries(
            Object.entries(state.shareUrls).filter(([id]) => id !== shareId),
          ),
        }));
        void trackProductEvent({
          name: "share_revoked",
          surface: "sharing",
          outcome: "revoked",
        });
      } catch (error) {
        set({ error: friendlyError(error) });
      } finally {
        set({ busy: false });
      }
    },

    startJob: async (type, localSessionId) => {
      if (!get().productConsent || get().account?.deletionPending) {
        throw new Error(
          "Cloud consent is required and account deletion must be inactive before processing.",
        );
      }
      set({ busy: true, error: null });
      try {
        const client = new PlatformClient();
        const prepared = await prepareCloudJob(
          type,
          localSessionId,
          get().jobs,
          client,
        );
        const key = `job:${type}:${syncEntityFingerprint(prepared.payload).slice(0, 48)}`;
        const job = await client.createJob(
          type,
          prepared.payload,
          key,
          prepared.inputRefs,
        );
        set((state) => ({
          jobs: [
            job,
            ...state.jobs.filter((value) => value.jobId !== job.jobId),
          ],
        }));
      } catch (error) {
        set({ error: friendlyError(error) });
        throw error;
      } finally {
        set({ busy: false });
      }
    },

    refreshJob: async (jobId) => {
      try {
        const job = await new PlatformClient().job(jobId);
        set((state) => ({
          jobs: [job, ...state.jobs.filter((value) => value.jobId !== jobId)],
        }));
      } catch (error) {
        set({ error: friendlyError(error) });
      }
    },

    loadArtifact: async (artifactId) => {
      try {
        const artifact = await new PlatformClient().generatedArtifact(
          artifactId,
        );
        set((state) => ({
          artifacts: { ...state.artifacts, [artifactId]: artifact },
        }));
      } catch (error) {
        set({ error: friendlyError(error) });
      }
    },

    loadJobOutput: async (type, outputId) => {
      try {
        const client = new PlatformClient();
        if (type === "report") {
          const artifact = await client.report(outputId);
          set((state) => ({
            reportArtifacts: {
              ...state.reportArtifacts,
              [outputId]: artifact,
            },
          }));
          return;
        }
        if (type === "data_export") {
          const artifact = await client.dataExport(outputId);
          set((state) => ({
            dataExports: { ...state.dataExports, [outputId]: artifact },
          }));
          return;
        }
        await get().loadArtifact(outputId);
      } catch (error) {
        set({ error: friendlyError(error) });
      }
    },

    cancelJob: async (jobId) => {
      try {
        const job = await new PlatformClient().cancelJob(
          jobId,
          newIdempotencyKey(`job-cancel:${jobId}`),
        );
        set((state) => ({
          jobs: [job, ...state.jobs.filter((value) => value.jobId !== jobId)],
        }));
      } catch (error) {
        set({ error: friendlyError(error) });
      }
    },

    requestCloudDeletion: async () => {
      set({ busy: true, error: null });
      try {
        const deletion = await new PlatformClient().requestAccountDeletion(
          newIdempotencyKey("account-delete"),
        );
        const accountId = get().account?.id;
        await unregisterCloudBackgroundSync().catch(() => undefined);
        useOralSightStore.getState().updateSettings({ analyticsOptIn: false });
        set({
          deletion,
          productConsent: null,
          recoveryCode: null,
          recoveryCodeWasCreated: false,
          account: get().account
            ? {
                ...get().account!,
                deletionPending: true,
                status: "deletion_pending",
              }
            : null,
        });
        const cleanup = await Promise.allSettled([
          clearCloudState(),
          ...(accountId
            ? [
                deleteCloudSyncKey(accountId),
                clearCloudInstallationIdentity(accountId),
              ]
            : []),
        ]);
        if (cleanup.some((result) => result.status === "rejected")) {
          set({
            error:
              "Cloud deletion started, but one or more device-side cloud keys still need cleanup. Keep this app installed and refresh the deletion status.",
          });
        }
      } catch (error) {
        set({ error: friendlyError(error) });
        throw error;
      } finally {
        set({ busy: false });
      }
    },

    refreshDeletion: async () => {
      const deletion = get().deletion;
      if (!deletion) return;
      try {
        const refreshed = await new PlatformClient().deletionStatus(
          deletion.requestId,
        );
        if (refreshed.status === "completed") {
          const accountId = get().account?.id;
          await unregisterCloudBackgroundSync().catch(() => undefined);
          await clearCloudCredentials().catch(() => undefined);
          await clearCloudState().catch(() => undefined);
          if (accountId)
            await deleteCloudSyncKey(accountId).catch(() => undefined);
          if (accountId)
            await clearCloudInstallationIdentity(accountId).catch(
              () => undefined,
            );
          useOralSightStore
            .getState()
            .updateSettings({ analyticsOptIn: false });
          set({
            deletion: refreshed,
            sessionStatus: "signed_out",
            account: null,
            analyticsConsent: null,
            consentDocument: null,
            productConsent: null,
            shares: [],
            accessHistory: [],
            jobs: [],
            artifacts: {},
            reportArtifacts: {},
            dataExports: {},
            shareUrls: {},
            latestShareUrl: null,
            recoveryCode: null,
          });
          return;
        }
        set({ deletion: refreshed });
      } catch (error) {
        set({ error: friendlyError(error) });
      }
    },

    setAnalyticsOptIn: async (enabled) => {
      set({ busy: true, error: null });
      try {
        if (get().sessionStatus !== "signed_in") {
          if (enabled) {
            throw new Error(
              "Sign in before enabling limited product analytics.",
            );
          }
          useOralSightStore
            .getState()
            .updateSettings({ analyticsOptIn: false });
          set({ analyticsConsent: null });
          return;
        }
        if (enabled && get().account?.deletionPending) {
          throw new Error(
            "Product analytics cannot be enabled while cloud deletion is pending.",
          );
        }
        const consent = await new PlatformClient().updateAnalyticsConsent(
          enabled,
        );
        useOralSightStore.getState().updateSettings({
          analyticsOptIn: consent.enabled,
        });
        set({ analyticsConsent: consent });
      } catch (error) {
        set({ error: friendlyError(error) });
        throw error;
      } finally {
        set({ busy: false });
      }
    },

    acceptProductConsent: async () => {
      const document = get().consentDocument;
      if (!document || get().sessionStatus !== "signed_in") {
        throw new Error("Sign in and load the current cloud consent first.");
      }
      if (get().account?.deletionPending) {
        throw new Error(
          "Cloud features cannot be enabled while deletion is pending.",
        );
      }
      set({ busy: true, error: null });
      try {
        const consent = await new PlatformClient().createProductConsent(
          document,
          `consent:${document.documentSha256.slice(0, 48)}`,
        );
        set({ productConsent: consent });
        await registerCloudBackgroundSync().catch(() => undefined);
        await get().syncNow();
      } catch (error) {
        set({ error: friendlyError(error) });
        throw error;
      } finally {
        set({ busy: false });
      }
    },

    revokeProductConsent: async () => {
      const consent = get().productConsent;
      if (!consent) return;
      set({ busy: true, error: null });
      try {
        const revoked = await new PlatformClient().revokeProductConsent(
          consent.consentRecordId,
          newIdempotencyKey(`consent-revoke:${consent.consentRecordId}`),
        );
        await unregisterCloudBackgroundSync().catch(() => undefined);
        set({ productConsent: revoked.active ? revoked : null });
      } catch (error) {
        set({ error: friendlyError(error) });
        throw error;
      } finally {
        set({ busy: false });
      }
    },

    clearError: () => set({ error: null }),
  };
});
