import { sha256 } from "@noble/hashes/sha2.js";
import { bytesToHex, utf8ToBytes } from "@noble/hashes/utils.js";
import { z } from "zod";

import type { AnalysisResult } from "@stoma3d/contracts";

import bundledGuidanceConfig from "../config/guidance-rules.json";
import { DISCLAIMER, NEUTRAL_SEEK_CARE_COPY } from "../constants";
import type { IntakeProfile } from "../types";

const INTENDED_USE =
  "Non-diagnostic review-priority messaging from clinician-approved deterministic rules.";
const REVIEW_SCOPE =
  "Exact wording, conditions, priorities, neutral fallback, and demo cases reviewed.";

const fieldSchema = z.enum([
  "pain",
  "bleeding",
  "numbness",
  "difficulty_swallowing",
  "duration_days",
  "rapidly_changing",
  "progression",
  "image_quality_score",
  "analysis_uncertainty",
]);
const scalarSchema = z.union([z.boolean(), z.number().finite(), z.string()]);
const conditionSchema = z
  .object({
    field: fieldSchema,
    operator: z.enum(["equals", "gte", "lte", "in"]),
    value: z.union([scalarSchema, z.array(scalarSchema).max(100)]),
  })
  .strict();
const ruleSchema = z
  .object({
    id: z.string().regex(/^[a-z0-9_]+$/),
    priority: z.number().int().nonnegative(),
    description: z.string().trim().min(1).max(500),
    all_conditions: z.array(conditionSchema).min(1).max(50),
    outcome: z
      .object({
        review_priority: z.enum(["neutral", "professional_review_suggested"]),
        message_key: z.string().regex(/^[a-z0-9_.-]+$/),
      })
      .strict(),
  })
  .strict();
const approvalSchema = z
  .object({
    reviewer_name: z.string().trim().min(1).max(200),
    credentials: z.string().trim().min(1).max(200),
    signed_at: z.string().datetime({ offset: true }),
    expires_at: z.string().datetime({ offset: true }),
    reviewed_payload_sha256: z.string().regex(/^[a-f0-9]{64}$/),
    scope: z.literal(REVIEW_SCOPE),
  })
  .strict();
const guidanceConfigSchema = z
  .object({
    schema_version: z.literal("1.1"),
    rules_version: z.string().trim().min(1).max(100),
    enabled: z.boolean(),
    intended_use: z.literal(INTENDED_USE),
    disclaimer: z.literal(DISCLAIMER),
    neutral_message: z.string().trim().min(1).max(1_000),
    messages: z.record(
      z.string().regex(/^[a-z0-9_.-]+$/),
      z.string().trim().min(1).max(1_000),
    ),
    approval: approvalSchema.nullable(),
    rules: z.array(ruleSchema).max(200),
  })
  .strict();

export type GuidanceField = z.infer<typeof fieldSchema>;
export type GuidanceConfig = z.infer<typeof guidanceConfigSchema>;
type GuidanceValue = boolean | number | string;
export type GuidanceContext = Partial<Record<GuidanceField, GuidanceValue>>;

export interface GuidanceDecision {
  enabled: boolean;
  rulesVersion: string | null;
  reviewPriority: "neutral" | "professional_review_suggested" | null;
  message: string;
  statusMessage: string;
  matchedRuleId: string | null;
}

function stableJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableJson(item)).join(",")}]`;
  }
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableJson(record[key])}`)
    .join(",")}}`;
}

export function reviewedPayloadSha256(
  config: Pick<
    GuidanceConfig,
    "neutral_message" | "messages" | "rules" | "rules_version"
  >,
): string {
  return bytesToHex(
    sha256(
      utf8ToBytes(
        stableJson({
          messages: config.messages,
          neutral_message: config.neutral_message,
          rules: config.rules,
          rules_version: config.rules_version,
        }),
      ),
    ),
  );
}

function disabledDecision(reason: string): GuidanceDecision {
  return {
    enabled: false,
    rulesVersion: null,
    reviewPriority: null,
    message: NEUTRAL_SEEK_CARE_COPY,
    statusMessage: `Review priority is unavailable because ${reason}`,
    matchedRuleId: null,
  };
}

function validateEnabledConfig(
  input: unknown,
  now: Date,
): GuidanceConfig | GuidanceDecision {
  const parsed = guidanceConfigSchema.safeParse(input);
  if (!parsed.success) return disabledDecision("the rule file is invalid.");
  const config = parsed.data;
  if (!config.enabled)
    return disabledDecision("no clinician-approved rule file is installed.");
  if (!config.approval)
    return disabledDecision("the installed rule file has no approval record.");
  const signedAt = new Date(config.approval.signed_at);
  const expiresAt = new Date(config.approval.expires_at);
  if (
    !Number.isFinite(signedAt.getTime()) ||
    !Number.isFinite(expiresAt.getTime()) ||
    signedAt > now ||
    expiresAt <= now
  ) {
    return disabledDecision("the clinician approval is not currently valid.");
  }
  if (
    reviewedPayloadSha256(config) !== config.approval.reviewed_payload_sha256
  ) {
    return disabledDecision(
      "the reviewed rule file changed after clinician approval.",
    );
  }
  if (
    config.rules.some(
      (rule) => config.messages[rule.outcome.message_key] === undefined,
    )
  ) {
    return disabledDecision("the rule file is missing reviewed wording.");
  }
  return config;
}

function conditionMatches(
  context: GuidanceContext,
  condition: z.infer<typeof conditionSchema>,
): boolean {
  const actual = context[condition.field];
  if (actual === undefined) return false;
  switch (condition.operator) {
    case "equals":
      return actual === condition.value;
    case "gte":
      return (
        typeof actual === "number" &&
        typeof condition.value === "number" &&
        actual >= condition.value
      );
    case "lte":
      return (
        typeof actual === "number" &&
        typeof condition.value === "number" &&
        actual <= condition.value
      );
    case "in":
      return Array.isArray(condition.value) && condition.value.includes(actual);
  }
}

export function evaluateGuidanceConfig(
  input: unknown,
  context: GuidanceContext,
  now = new Date(),
): GuidanceDecision {
  const validated = validateEnabledConfig(input, now);
  if ("matchedRuleId" in validated) return validated;
  const config = validated;
  const match = [...config.rules]
    .sort((left, right) => right.priority - left.priority)
    .find((rule) =>
      rule.all_conditions.every((condition) =>
        conditionMatches(context, condition),
      ),
    );
  if (!match) {
    return {
      enabled: true,
      rulesVersion: config.rules_version,
      reviewPriority: "neutral",
      message: config.neutral_message,
      statusMessage: `Clinician-reviewed guidance rules ${config.rules_version} are active.`,
      matchedRuleId: null,
    };
  }
  return {
    enabled: true,
    rulesVersion: config.rules_version,
    reviewPriority: match.outcome.review_priority,
    message:
      config.messages[match.outcome.message_key] ?? config.neutral_message,
    statusMessage: `Clinician-reviewed guidance rules ${config.rules_version} are active.`,
    matchedRuleId: match.id,
  };
}

function hasSymptom(profile: IntakeProfile | null, symptom: string): boolean {
  return (
    profile?.symptoms.some((item) => item.trim().toLowerCase() === symptom) ??
    false
  );
}

export function guidanceContext(
  profile: IntakeProfile | null,
  analyses: AnalysisResult[],
): GuidanceContext {
  const accepted = analyses.filter((analysis) => analysis.quality.accepted);
  const qualityScores = accepted.map((analysis) =>
    Math.min(
      analysis.quality.blurScore,
      analysis.quality.exposureScore,
      1 - analysis.quality.glareScore,
      1 - analysis.quality.obstructionScore,
    ),
  );
  const uncertainties = analyses.map(
    (analysis) => 1 - analysis.uncertainty.overallConfidence,
  );
  return {
    pain: hasSymptom(profile, "pain"),
    bleeding: hasSymptom(profile, "bleeding"),
    numbness: hasSymptom(profile, "numbness"),
    difficulty_swallowing: hasSymptom(profile, "difficulty swallowing"),
    ...(profile?.durationDays !== undefined
      ? { duration_days: profile.durationDays }
      : {}),
    rapidly_changing: profile?.change === "rapid_change",
    ...(profile ? { progression: profile.change } : {}),
    ...(qualityScores.length
      ? { image_quality_score: Math.min(...qualityScores) }
      : {}),
    ...(uncertainties.length
      ? { analysis_uncertainty: Math.max(...uncertainties) }
      : {}),
  };
}

export function evaluateBundledGuidance(
  profile: IntakeProfile | null,
  analyses: AnalysisResult[],
): GuidanceDecision {
  return evaluateGuidanceConfig(
    bundledGuidanceConfig,
    guidanceContext(profile, analyses),
  );
}

export function bundledGuidanceStatus(): GuidanceDecision {
  return evaluateGuidanceConfig(bundledGuidanceConfig, {});
}
