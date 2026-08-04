import * as Crypto from "expo-crypto";
import { create } from "zustand";
import type {
  AnalysisResult,
  ComparisonResult,
  MouthRegion,
} from "@oralsight/contracts";
import { MOUTH_REGION_DETAILS } from "@oralsight/contracts";

import { ORAL_MAP_ASSET_VERSION } from "@/constants";
import {
  assertLiveMobileInput,
  assertLiveResultOrigin,
} from "@/lib/liveInputPolicy";
import { isChronologicalComparison } from "@/lib/longitudinalPolicy";
import { pinsAfterConfirmedComparison } from "@/lib/observationPins";
import { comparisonsWithoutCaptureIds } from "@/lib/scanLogic";
import {
  deleteAllLocalDataAndRotateKeys,
  loadPersistedState,
  queuePersistedState,
} from "@/lib/storage";
import {
  removeProtectedFile,
  removeUnreferencedProtectedFiles,
} from "@/lib/secureFiles";
import type {
  AccessibilitySettings,
  CaptureRecord,
  IntakeProfile,
  ObservationPin,
  PersistedAppState,
  ReportRecord,
  ScanSession,
} from "@/types";

interface OralSightState extends PersistedAppState {
  hydrated: boolean;
  storageError: string | null;
  hydrate: () => Promise<void>;
  finishConsent: (profile: IntakeProfile) => void;
  finishConsentAndStartSession: (profile: IntakeProfile) => Promise<string>;
  startFreshSession: () => string;
  setActiveSession: (sessionId: string) => void;
  addCapture: (
    capture: CaptureRecord,
    analysis: AnalysisResult,
  ) => Promise<void>;
  updateCaptureAnalysis: (
    captureId: string,
    analysis: AnalysisResult,
  ) => Promise<void>;
  discardCapture: (captureId: string) => Promise<void>;
  confirmObservationPin: (captureId: string) => void;
  addComparison: (comparison: ComparisonResult) => Promise<void>;
  addReport: (report: ReportRecord) => Promise<void>;
  updateSettings: (settings: Partial<AccessibilitySettings>) => void;
  deleteEverything: () => Promise<void>;
}

const DEFAULT_SETTINGS: AccessibilitySettings = {
  highContrast: false,
  largeText: false,
  reducedMotion: false,
  haptics: true,
  voiceInstructions: false,
  caregiverMode: false,
};

function initialPersistedState(): PersistedAppState {
  return {
    schemaVersion: 2,
    consentedAt: null,
    profile: null,
    settings: DEFAULT_SETTINGS,
    sessions: [],
    captures: [],
    analyses: {},
    comparisons: [],
    pins: [],
    reports: [],
    activeSessionId: null,
  };
}

function persistedSnapshot(state: OralSightState): PersistedAppState {
  return {
    schemaVersion: 2,
    consentedAt: state.consentedAt,
    profile: state.profile,
    settings: state.settings,
    sessions: state.sessions,
    captures: state.captures,
    analyses: state.analyses,
    comparisons: state.comparisons,
    pins: state.pins,
    reports: state.reports,
    activeSessionId: state.activeSessionId,
  };
}

function persist(
  state: OralSightState,
  onError: (message: string) => void,
): void {
  void queuePersistedState(persistedSnapshot(state)).catch(() => {
    onError(
      "OralSight could not save the latest local change. Retry before continuing.",
    );
  });
}

function snapshotProfile(profile: IntakeProfile | null): IntakeProfile | null {
  return profile ? { ...profile, symptoms: [...profile.symptoms] } : null;
}

function pinForAnalysis(
  existing: ObservationPin[],
  capture: CaptureRecord,
  analysis: AnalysisResult,
): ObservationPin[] {
  if (!analysis.candidateMask) return existing;
  const regionDetail = MOUTH_REGION_DETAILS.find(
    (detail) => detail.id === capture.region,
  );
  if (!regionDetail) return existing;
  const [x, y, width, height] = analysis.candidateMask.boundingBox;
  return [
    ...existing,
    {
      id: Crypto.randomUUID(),
      region: capture.region,
      meshId: regionDetail.meshId,
      uvX: Math.min(1, Math.max(0, x + width / 2)),
      uvY: Math.min(1, Math.max(0, y + height / 2)),
      assetVersion: ORAL_MAP_ASSET_VERSION,
      userConfirmed: true,
      firstObservedAt: capture.capturedAt,
      status: "review_unavailable",
      captureIds: [capture.id],
    },
  ];
}

function normalizePersistedPins(pins: ObservationPin[]): ObservationPin[] {
  return pins.flatMap((pin) => {
    if (pin.userConfirmed !== true) return [];
    const regionDetail = MOUTH_REGION_DETAILS.find(
      (detail) => detail.id === pin.region,
    );
    if (!regionDetail) return [];
    const captureIds = [...new Set(pin.captureIds)];
    if (captureIds.length === 0) return [];
    return [
      {
        ...pin,
        meshId: regionDetail.meshId,
        assetVersion: ORAL_MAP_ASSET_VERSION,
        uvX: Math.min(1, Math.max(0, pin.uvX)),
        uvY: Math.min(1, Math.max(0, pin.uvY)),
        captureIds,
      },
    ];
  });
}

function withoutDemoData(persisted: PersistedAppState): PersistedAppState {
  const sessions = persisted.sessions.filter((session) => !session.demo);
  const sessionIds = new Set(sessions.map((session) => session.id));
  const captures = persisted.captures.filter(
    (capture) =>
      sessionIds.has(capture.sessionId) &&
      capture.inputOrigin === "live_capture" &&
      !capture.samplePlaceholder,
  );
  const captureIds = new Set(captures.map((capture) => capture.id));
  const analyses = Object.fromEntries(
    Object.entries(persisted.analyses).filter(([captureId]) =>
      captureIds.has(captureId),
    ),
  );
  const comparisons = persisted.comparisons.filter(
    (comparison) =>
      comparison.inputOrigin === "live_capture" &&
      captureIds.has(comparison.baselineCaptureId) &&
      captureIds.has(comparison.currentCaptureId),
  );
  const pins = persisted.pins.flatMap((pin) => {
    const linkedCaptureIds = pin.captureIds.filter((captureId) =>
      captureIds.has(captureId),
    );
    return linkedCaptureIds.length > 0
      ? [{ ...pin, captureIds: linkedCaptureIds }]
      : [];
  });
  return {
    ...persisted,
    sessions,
    captures,
    analyses,
    comparisons,
    pins,
    reports: persisted.reports.filter((report) =>
      sessionIds.has(report.sessionId),
    ),
    activeSessionId:
      persisted.activeSessionId && sessionIds.has(persisted.activeSessionId)
        ? persisted.activeSessionId
        : null,
  };
}

function assertPersistedReferences(state: PersistedAppState): void {
  const sessionsById = new Map(
    state.sessions.map((session) => [session.id, session]),
  );
  const capturesById = new Map(
    state.captures.map((capture) => [capture.id, capture]),
  );
  if (state.activeSessionId && !sessionsById.has(state.activeSessionId)) {
    throw new Error("Persisted active session is missing.");
  }
  for (const capture of state.captures) {
    if (!sessionsById.has(capture.sessionId)) {
      throw new Error("Persisted capture refers to a missing session.");
    }
  }
  for (const [captureId, analysis] of Object.entries(state.analyses)) {
    const capture = capturesById.get(captureId);
    if (
      !capture ||
      analysis.captureId !== captureId ||
      analysis.region !== capture.region ||
      analysis.inputOrigin !== capture.inputOrigin
    ) {
      throw new Error("Persisted analysis identity is inconsistent.");
    }
  }
  for (const comparison of state.comparisons) {
    const baseline = capturesById.get(comparison.baselineCaptureId);
    const current = capturesById.get(comparison.currentCaptureId);
    if (
      !baseline ||
      !current ||
      baseline.region !== comparison.region ||
      current.region !== comparison.region ||
      baseline.inputOrigin !== comparison.inputOrigin ||
      current.inputOrigin !== comparison.inputOrigin
    ) {
      throw new Error("Persisted comparison identity is inconsistent.");
    }
  }
  for (const pin of state.pins) {
    if (
      pin.captureIds.some(
        (captureId) => capturesById.get(captureId)?.region !== pin.region,
      )
    ) {
      throw new Error("Persisted map pin identity is inconsistent.");
    }
  }
  for (const report of state.reports) {
    if (!sessionsById.has(report.sessionId)) {
      throw new Error("Persisted report refers to a missing session.");
    }
  }
}

export const useOralSightStore = create<OralSightState>((set, get) => ({
  ...initialPersistedState(),
  hydrated: false,
  storageError: null,

  hydrate: async () => {
    set({ hydrated: false, storageError: null });
    try {
      const loaded = await loadPersistedState();
      const persisted = loaded ? withoutDemoData(loaded) : null;
      if (persisted) {
        assertPersistedReferences(persisted);
        try {
          await removeUnreferencedProtectedFiles([
            ...persisted.captures.map((capture) => capture.encryptedUri),
            ...persisted.reports.map((report) => report.encryptedUri),
          ]);
        } catch {
          console.warn("[ORALSIGHT_ORPHAN_CLEANUP_FAILED]");
        }
      }
      set({
        ...(persisted ?? initialPersistedState()),
        pins: normalizePersistedPins(persisted?.pins ?? []),
        hydrated: true,
        storageError: null,
      });
      if (loaded && persisted !== loaded) {
        await queuePersistedState(persistedSnapshot(get()));
      }
    } catch (error) {
      console.warn("[ORALSIGHT_STORAGE_OPEN_FAILED]");
      set({
        hydrated: true,
        storageError:
          "The protected local workspace could not be opened or validated. OralSight has not replaced it with an empty workspace.",
      });
    }
  },

  finishConsent: (profile) => {
    set({
      profile,
      consentedAt: new Date().toISOString(),
      storageError: null,
    });
    persist(get(), (message) => set({ storageError: message }));
  },

  finishConsentAndStartSession: async (profile) => {
    const stateBeforeCommit = get();
    const consentedAt = new Date().toISOString();
    const id = Crypto.randomUUID();
    const session: ScanSession = {
      id,
      createdAt: consentedAt,
      demo: false,
      label: "Structured mouth scan",
      intakeProfile: snapshotProfile(profile),
      consentedAt,
    };
    set((state) => ({
      profile,
      consentedAt,
      sessions: [...state.sessions, session],
      activeSessionId: id,
      storageError: null,
    }));
    try {
      await queuePersistedState(persistedSnapshot(get()));
    } catch {
      set(stateBeforeCommit);
      throw new Error(
        "Consent and intake could not be saved in the protected workspace.",
      );
    }
    return id;
  },

  startFreshSession: () => {
    const id = Crypto.randomUUID();
    const session: ScanSession = {
      id,
      createdAt: new Date().toISOString(),
      demo: false,
      label: "New structured scan",
      intakeProfile: snapshotProfile(get().profile),
      consentedAt: get().consentedAt,
    };
    set((state) => ({
      sessions: [...state.sessions, session],
      activeSessionId: id,
      storageError: null,
    }));
    persist(get(), (message) => set({ storageError: message }));
    return id;
  },

  setActiveSession: (sessionId) => {
    if (!get().sessions.some((session) => session.id === sessionId)) return;
    set({ activeSessionId: sessionId, storageError: null });
    persist(get(), (message) => set({ storageError: message }));
  },

  addCapture: async (capture, analysis) => {
    const stateBeforeCommit = get();
    const targetSession = stateBeforeCommit.sessions.find(
      (session) => session.id === capture.sessionId,
    );
    assertLiveMobileInput(capture.inputOrigin);
    assertLiveResultOrigin(analysis.analysisOrigin);
    if (!targetSession || targetSession.demo) {
      throw new Error("A live capture requires a valid non-demo scan session.");
    }
    if (
      analysis.captureId !== capture.id ||
      analysis.region !== capture.region ||
      analysis.inputOrigin !== capture.inputOrigin
    ) {
      throw new Error("The analysis identity does not match this capture.");
    }
    if (
      !capture.encryptedUri ||
      !capture.quality.accepted ||
      capture.privacyConfirmedByUser !== true ||
      capture.regionConfirmedByUser !== true ||
      (capture.captureSource !== "camera" &&
        capture.captureSource !== "photo_library")
    ) {
      throw new Error(
        "Only a protected, accepted, user-confirmed camera or photo-library capture can be saved.",
      );
    }
    const supersededCaptures = stateBeforeCommit.captures.filter(
      (item) =>
        item.sessionId === capture.sessionId && item.region === capture.region,
    );
    const invalidatedReports = stateBeforeCommit.reports.filter(
      (report) => report.sessionId === capture.sessionId,
    );
    set((state) => {
      const replacedCaptureIds = supersededCaptures
        .filter((item) =>
          state.captures.some((current) => current.id === item.id),
        )
        .map((item) => item.id);
      const retainedCaptures = state.captures.filter(
        (item) => !replacedCaptureIds.includes(item.id),
      );
      const retainedPins = state.pins.filter(
        (pin) =>
          !pin.captureIds.some((captureId) =>
            replacedCaptureIds.includes(captureId),
          ),
      );
      const retainedAnalyses = Object.fromEntries(
        Object.entries(state.analyses).filter(
          ([captureId]) => !replacedCaptureIds.includes(captureId),
        ),
      );
      const retainedComparisons = comparisonsWithoutCaptureIds(
        state.comparisons,
        replacedCaptureIds,
      );
      return {
        captures: [...retainedCaptures, capture],
        analyses: { ...retainedAnalyses, [capture.id]: analysis },
        pins: retainedPins,
        comparisons: retainedComparisons,
        reports: state.reports.filter(
          (report) => report.sessionId !== capture.sessionId,
        ),
      };
    });
    try {
      await queuePersistedState(persistedSnapshot(get()));
    } catch {
      set(stateBeforeCommit);
      await removeProtectedFile(capture.encryptedUri);
      throw new Error(
        "The protected capture was not saved. The previous capture is unchanged.",
      );
    }
    const cleanupResults = await Promise.allSettled([
      ...supersededCaptures.map((item) =>
        removeProtectedFile(item.encryptedUri),
      ),
      ...invalidatedReports.map((report) =>
        removeProtectedFile(report.encryptedUri),
      ),
    ]);
    if (cleanupResults.some((result) => result.status === "rejected")) {
      console.warn("[ORALSIGHT_SUPERSEDED_FILE_CLEANUP_FAILED]");
    }
  },

  updateCaptureAnalysis: async (captureId, analysis) => {
    const stateBeforeCommit = get();
    const capture = stateBeforeCommit.captures.find(
      (item) => item.id === captureId,
    );
    if (!capture) {
      throw new Error("The protected observation could not be found.");
    }
    assertLiveMobileInput(capture.inputOrigin);
    assertLiveResultOrigin(analysis.analysisOrigin);
    if (
      analysis.captureId !== capture.id ||
      analysis.region !== capture.region ||
      analysis.inputOrigin !== capture.inputOrigin
    ) {
      throw new Error(
        "The updated analysis identity does not match this capture.",
      );
    }
    set((state) => ({
      captures: state.captures.map((item) =>
        item.id === captureId ? { ...item, quality: analysis.quality } : item,
      ),
      analyses: { ...state.analyses, [captureId]: analysis },
      storageError: null,
    }));
    try {
      await queuePersistedState(persistedSnapshot(get()));
    } catch {
      set(stateBeforeCommit);
      throw new Error(
        "The new analysis response could not be saved. The previous result is unchanged.",
      );
    }
  },

  discardCapture: async (captureId) => {
    const stateBeforeCommit = get();
    const capture = stateBeforeCommit.captures.find(
      (item) => item.id === captureId,
    );
    if (!capture) return;
    const removedReports = stateBeforeCommit.reports.filter(
      (report) => report.sessionId === capture.sessionId,
    );
    set((state) => ({
      captures: state.captures.filter((item) => item.id !== captureId),
      analyses: Object.fromEntries(
        Object.entries(state.analyses).filter(([id]) => id !== captureId),
      ),
      comparisons: comparisonsWithoutCaptureIds(state.comparisons, [captureId]),
      pins: state.pins.filter((pin) => !pin.captureIds.includes(captureId)),
      reports: state.reports.filter(
        (report) => report.sessionId !== capture.sessionId,
      ),
      storageError: null,
    }));
    try {
      await queuePersistedState(persistedSnapshot(get()));
    } catch {
      set(stateBeforeCommit);
      throw new Error(
        "The rejected observation could not be removed safely. Retry local deletion from Settings.",
      );
    }
    const cleanup = await Promise.allSettled([
      removeProtectedFile(capture.encryptedUri),
      ...removedReports.map((report) =>
        removeProtectedFile(report.encryptedUri),
      ),
    ]);
    if (cleanup.some((result) => result.status === "rejected")) {
      set({
        storageError:
          "The rejected observation was removed from history, but one or more protected files still require cleanup.",
      });
      throw new Error(
        "The observation record was removed, but protected-file cleanup did not finish.",
      );
    }
  },

  confirmObservationPin: (captureId) => {
    const state = get();
    if (state.pins.some((pin) => pin.captureIds.includes(captureId))) {
      return;
    }
    const capture = state.captures.find((item) => item.id === captureId);
    const analysis = state.analyses[captureId];
    if (!capture || !analysis?.candidateMask) return;
    set({
      pins: pinForAnalysis(state.pins, capture, analysis),
      storageError: null,
    });
    persist(get(), (message) => set({ storageError: message }));
  },

  addComparison: async (comparison) => {
    const stateBeforeCommit = get();
    const baseline = stateBeforeCommit.captures.find(
      (capture) => capture.id === comparison.baselineCaptureId,
    );
    const current = stateBeforeCommit.captures.find(
      (capture) => capture.id === comparison.currentCaptureId,
    );
    assertLiveMobileInput(comparison.inputOrigin);
    assertLiveResultOrigin(comparison.analysisOrigin);
    if (
      !comparison.userConfirmedMatch ||
      !baseline ||
      !current ||
      baseline.region !== comparison.region ||
      current.region !== comparison.region ||
      !isChronologicalComparison(baseline, current)
    ) {
      throw new Error(
        "Only a user-confirmed, chronological comparison of two saved live observations can be stored.",
      );
    }
    set((state) => ({
      comparisons: [
        ...state.comparisons.filter(
          (item) =>
            item.baselineCaptureId !== comparison.baselineCaptureId ||
            item.currentCaptureId !== comparison.currentCaptureId,
        ),
        comparison,
      ],
      pins: pinsAfterConfirmedComparison(
        state.pins,
        state.captures,
        comparison,
      ),
      storageError: null,
    }));
    try {
      await queuePersistedState(persistedSnapshot(get()));
    } catch {
      set(stateBeforeCommit);
      throw new Error(
        "The comparison could not be saved. Existing history is unchanged.",
      );
    }
  },

  addReport: async (report) => {
    const stateBeforeCommit = get();
    const replaced = stateBeforeCommit.reports.filter(
      (item) => item.sessionId === report.sessionId,
    );
    set((state) => ({
      reports: [
        ...state.reports.filter((item) => item.sessionId !== report.sessionId),
        report,
      ],
      storageError: null,
    }));
    try {
      await queuePersistedState(persistedSnapshot(get()));
    } catch {
      set(stateBeforeCommit);
      await removeProtectedFile(report.encryptedUri);
      throw new Error(
        "The protected report could not be saved. The previous report is unchanged.",
      );
    }
    const cleanup = await Promise.allSettled(
      replaced.map((item) => removeProtectedFile(item.encryptedUri)),
    );
    if (cleanup.some((result) => result.status === "rejected")) {
      console.warn("[ORALSIGHT_REPLACED_REPORT_CLEANUP_FAILED]");
    }
  },

  updateSettings: (settings) => {
    set((state) => ({
      settings: { ...state.settings, ...settings },
      storageError: null,
    }));
    persist(get(), (message) => set({ storageError: message }));
  },

  deleteEverything: async () => {
    await deleteAllLocalDataAndRotateKeys();
    set({
      ...initialPersistedState(),
      hydrated: true,
      storageError: null,
    });
    try {
      await queuePersistedState(persistedSnapshot(get()));
    } catch {
      throw new Error(
        "Local data was removed, but the empty protected state could not be initialized.",
      );
    }
  },
}));

export function regionLabelForId(region: MouthRegion): string {
  return region.replaceAll("_", " ");
}
