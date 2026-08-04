import {
  analysisResultSchema,
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
    haptics: z.boolean(),
    voiceInstructions: z.boolean(),
    caregiverMode: z.boolean(),
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
    intakeProfile: intakeProfileSchema.nullable().optional(),
    consentedAt: isoDateSchema.nullable().optional(),
  })
  .strict();

const captureSchema = z
  .object({
    id: idSchema,
    sessionId: idSchema,
    region: mouthRegionSchema,
    capturedAt: isoDateSchema,
    encryptedUri: z.string().min(1).max(4_096).nullable(),
    mimeType: z.enum(["image/jpeg", "image/png"]),
    inputOrigin: inputOriginSchema,
    fixtureSha256: z
      .string()
      .regex(/^[a-f0-9]{64}$/)
      .optional(),
    captureSource: z
      .enum(["camera", "photo_library", "developer_demo"])
      .optional(),
    privacyConfirmedByUser: z.boolean().optional(),
    regionConfirmedByUser: z.boolean().optional(),
    quality: qualityResultSchema,
    samplePlaceholder: z.boolean().optional(),
  })
  .strict();

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
    schemaVersion: z.literal(2),
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
  const state = objectRecord(value);
  if (!state || state.schemaVersion !== 1) return value;
  const analyses = objectRecord(state.analyses);
  return {
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

export function parsePersistedAppState(value: unknown): PersistedAppState {
  return persistedAppStateSchema.parse(migratePersistedAppState(value));
}
