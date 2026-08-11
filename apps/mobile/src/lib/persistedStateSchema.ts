import {
  analysisResultSchema,
  calibrationResultSchema,
  captureAngleSchema,
  captureProtocolSchema,
  comparisonResultSchema,
  CONTRACT_VERSION,
  inputOriginSchema,
  mouthRegionSchema,
  qualityResultSchema,
} from "@oralsight/contracts";
import { z } from "zod";

import type { PersistedAppState } from "@/types";

const idSchema = z.string().trim().min(1).max(128);
const isoDateSchema = z.string().datetime({ offset: true });

const settingsSchema = z
  .object({
    highContrast: z.boolean(),
    largeText: z.boolean(),
    reducedMotion: z.boolean(),
    animationSpeed: z.enum(["slow", "standard"]),
    haptics: z.boolean(),
    voiceInstructions: z.boolean(),
    caregiverMode: z.boolean(),
    analyticsOptIn: z.boolean(),
  })
  .strict();

const intakeProfileSchema = z
  .object({
    ageRange: z.enum([
      "under_18",
      "18_39",
      "40_64",
      "65_plus",
      "prefer_not_to_say",
    ]),
    assisted: z.boolean(),
    firstNoticed: z.string().max(500),
    durationDays: z.number().int().min(0).max(36_500).optional(),
    symptoms: z.array(z.string().max(100)).max(30),
    bleedingFrequency: z.enum(["once", "occasionally", "often"]).optional(),
    bleedingDuration: z.string().max(500).optional(),
    change: z.enum(["not_sure", "no_change", "slow_change", "rapid_change"]),
    tobaccoExposure: z.enum(["none", "past", "current", "prefer_not_to_say"]),
    alcoholExposure: z.enum(["none", "some", "frequent", "prefer_not_to_say"]),
    previousConditions: z.string().max(2_000),
    professionallyExamined: z.boolean(),
  })
  .strict();

const sessionSchema = z
  .object({
    id: idSchema,
    createdAt: isoDateSchema,
    demo: z.boolean(),
    label: z.string().trim().min(1).max(200),
    protocol: captureProtocolSchema,
    intakeProfile: intakeProfileSchema.nullable().optional(),
    consentedAt: isoDateSchema.nullable().optional(),
  })
  .strict();

const captureSchema = z
  .object({
    id: idSchema,
    sessionId: idSchema,
    region: mouthRegionSchema,
    angle: captureAngleSchema,
    mediaKind: z.enum(["image", "video_frame"]),
    capturedAt: isoDateSchema,
    encryptedUri: z.string().min(1).max(4_096).nullable(),
    mimeType: z.enum(["image/jpeg", "image/png"]),
    inputOrigin: inputOriginSchema,
    fixtureSha256: z
      .string()
      .regex(/^[a-f0-9]{64}$/)
      .optional(),
    captureSource: z
      .enum(["camera", "photo_library", "video_sweep", "developer_demo"])
      .optional(),
    sourceVideoDurationMs: z.number().int().positive().max(60_000).optional(),
    frameTimeMs: z.number().int().nonnegative().max(60_000).optional(),
    calibrationRequested: z.boolean().optional(),
    calibrationPlaneConfirmed: z.boolean().optional(),
    calibrationCardVersion: z.literal("oralsight-calibration-v1").optional(),
    calibration: calibrationResultSchema.optional(),
    privacyConfirmedByUser: z.boolean().optional(),
    regionConfirmedByUser: z.boolean().optional(),
    captureGuidance: z
      .object({
        stabilityPercent: z.number().int().min(0).max(100).nullable(),
        tiltDegrees: z.number().min(-180).max(180).nullable(),
        rotationDegrees: z.number().min(-180).max(180).nullable(),
        targetWidthPercent: z.number().int().min(1).max(100),
        source: z.enum(["live_camera", "sweep_start", "imported_photo"]),
      })
      .strict()
      .optional(),
    quality: qualityResultSchema,
    samplePlaceholder: z.boolean().optional(),
  })
  .strict()
  .superRefine((capture, context) => {
    const isVideoFrame = capture.mediaKind === "video_frame";
    if (
      isVideoFrame !==
      (capture.captureSource === "video_sweep" &&
        capture.sourceVideoDurationMs !== undefined &&
        capture.frameTimeMs !== undefined)
    ) {
      context.addIssue({
        code: "custom",
        path: ["mediaKind"],
        message:
          "Video frames require their sweep source, duration, and frame time.",
      });
    }
    if (
      capture.frameTimeMs !== undefined &&
      capture.sourceVideoDurationMs !== undefined &&
      capture.frameTimeMs > capture.sourceVideoDurationMs
    ) {
      context.addIssue({
        code: "custom",
        path: ["frameTimeMs"],
        message: "A frame time cannot exceed its source sweep duration.",
      });
    }
    const calibrationFieldsPresent =
      capture.calibrationPlaneConfirmed !== undefined ||
      capture.calibrationCardVersion !== undefined ||
      capture.calibration !== undefined;
    if (capture.calibrationRequested !== true && calibrationFieldsPresent) {
      context.addIssue({
        code: "custom",
        path: ["calibrationRequested"],
        message:
          "Calibration evidence requires an explicit calibration request.",
      });
    }
    if (
      capture.calibrationRequested === true &&
      (capture.calibrationPlaneConfirmed !== true ||
        capture.calibrationCardVersion !== "oralsight-calibration-v1")
    ) {
      context.addIssue({
        code: "custom",
        path: ["calibrationPlaneConfirmed"],
        message:
          "A calibration request requires same-plane confirmation and the versioned card.",
      });
    }
    if (
      capture.calibration &&
      capture.calibration.captureViewId !== capture.id
    ) {
      context.addIssue({
        code: "custom",
        path: ["calibration", "captureViewId"],
        message: "Calibration evidence belongs to a different capture view.",
      });
    }
  });

const pinSchema = z
  .object({
    id: idSchema,
    region: mouthRegionSchema,
    meshId: z.string().trim().min(1).max(200),
    uvX: z.number().finite(),
    uvY: z.number().finite(),
    assetVersion: z.string().trim().min(1).max(200),
    userConfirmed: z.boolean(),
    firstObservedAt: isoDateSchema,
    status: z.enum([
      "monitoring",
      "retake_required",
      "stable",
      "visually_changed",
      "review_unavailable",
    ]),
    comparisonStatus: z
      .enum([
        "stable",
        "increased_estimated_size",
        "decreased_estimated_size",
        "color_or_texture_changed",
        "shape_changed",
        "insufficient_comparable_data",
      ])
      .optional(),
    captureIds: z.array(idSchema).max(100),
  })
  .strict();

const reportSchema = z
  .object({
    id: idSchema,
    createdAt: isoDateSchema,
    encryptedUri: z.string().min(1).max(4_096),
    sessionId: idSchema,
  })
  .strict();

export const persistedAppStateSchema = z
  .object({
    schemaVersion: z.literal(4),
    consentedAt: isoDateSchema.nullable(),
    profile: intakeProfileSchema.nullable(),
    settings: settingsSchema,
    sessions: z.array(sessionSchema).max(1_000),
    captures: z.array(captureSchema).max(8_000),
    analyses: z.record(idSchema, analysisResultSchema),
    comparisons: z.array(comparisonResultSchema).max(8_000),
    pins: z.array(pinSchema).max(8_000),
    reports: z.array(reportSchema).max(1_000),
    activeSessionId: idSchema.nullable(),
  })
  .strict();

function objectRecord(value: unknown): Record<string, unknown> | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function migrateLegacyAnalysis(value: unknown): unknown {
  const analysis = objectRecord(value);
  if (!analysis || analysis.contractVersion !== "1.0.0") return value;
  const uncertainty = objectRecord(analysis.uncertainty);
  const fixtureDerived =
    analysis.analysisOrigin === "manual_fixture" ||
    analysis.analysisOrigin === "cached_model_result";
  return {
    ...analysis,
    contractVersion: CONTRACT_VERSION,
    ...(uncertainty
      ? {
          uncertainty: {
            ...uncertainty,
            datasetSimilarity: fixtureDerived
              ? (uncertainty.datasetSimilarity ?? null)
              : null,
            modelAgreement: fixtureDerived
              ? (uncertainty.modelAgreement ?? null)
              : null,
          },
        }
      : {}),
  };
}

function migrateLegacyComparison(value: unknown): unknown {
  const comparison = objectRecord(value);
  if (!comparison || comparison.contractVersion !== "1.0.0") return value;
  return { ...comparison, contractVersion: CONTRACT_VERSION };
}

function migratePersistedAppState(value: unknown): unknown {
  let state = objectRecord(value);
  if (!state) return value;
  if (state.schemaVersion === 1) {
    const analyses = objectRecord(state.analyses);
    state = {
      ...state,
      schemaVersion: 2,
      analyses: analyses
        ? Object.fromEntries(
            Object.entries(analyses).map(([captureId, analysis]) => [
              captureId,
              migrateLegacyAnalysis(analysis),
            ]),
          )
        : state.analyses,
      comparisons: Array.isArray(state.comparisons)
        ? state.comparisons.map(migrateLegacyComparison)
        : state.comparisons,
    };
  }
  if (state.schemaVersion === 2) {
    state = {
      ...state,
      schemaVersion: 3,
      sessions: Array.isArray(state.sessions)
        ? state.sessions.map((session) => ({
            ...(objectRecord(session) ?? {}),
            protocol: "standard_eight_region",
          }))
        : state.sessions,
      captures: Array.isArray(state.captures)
        ? state.captures.map((capture) => ({
            ...(objectRecord(capture) ?? {}),
            angle: "primary",
            mediaKind: "image",
          }))
        : state.captures,
    };
  }
  if (state.schemaVersion === 3) {
    const settings = objectRecord(state.settings);
    state = {
      ...state,
      schemaVersion: 4,
      settings: settings
        ? {
            ...settings,
            analyticsOptIn:
              typeof settings.analyticsOptIn === "boolean"
                ? settings.analyticsOptIn
                : false,
            animationSpeed: "standard",
          }
        : state.settings,
    };
  }
  return state;
}

export function parsePersistedAppState(value: unknown): PersistedAppState {
  return persistedAppStateSchema.parse(migratePersistedAppState(value));
}
