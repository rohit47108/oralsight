import { describe, expect, it } from "vitest";

import {
  evaluateGuidanceConfig,
  reviewedPayloadSha256,
  type GuidanceConfig,
} from "../src/lib/guidanceRules";

const NOW = new Date("2026-07-27T12:00:00Z");

function approvedConfig(): GuidanceConfig {
  const config: GuidanceConfig = {
    schema_version: "1.1",
    rules_version: "2026.1",
    enabled: true,
    intended_use:
      "Non-diagnostic review-priority messaging from clinician-approved deterministic rules.",
    disclaimer: "This result is not a diagnosis.",
    neutral_message: "Use the neutral reviewed message.",
    messages: {
      "review.suggested": "Arrange a professional review.",
    },
    approval: {
      reviewer_name: "Test clinician",
      credentials: "Test credentials",
      signed_at: "2026-07-01T12:00:00Z",
      expires_at: "2027-07-01T12:00:00Z",
      reviewed_payload_sha256: "0".repeat(64),
      scope:
        "Exact wording, conditions, priorities, neutral fallback, and demo cases reviewed.",
    },
    rules: [
      {
        id: "persistent_change",
        priority: 10,
        description: "Test-only deterministic rule",
        all_conditions: [
          { field: "duration_days", operator: "gte", value: 14 },
          { field: "rapidly_changing", operator: "equals", value: true },
        ],
        outcome: {
          review_priority: "professional_review_suggested",
          message_key: "review.suggested",
        },
      },
    ],
  };
  config.approval!.reviewed_payload_sha256 = reviewedPayloadSha256(config);
  return config;
}

describe("clinician guidance rules", () => {
  it("activates only an approved, unexpired, hash-matched rule file", () => {
    const result = evaluateGuidanceConfig(
      approvedConfig(),
      { duration_days: 20, rapidly_changing: true },
      NOW,
    );

    expect(result.enabled).toBe(true);
    expect(result.reviewPriority).toBe("professional_review_suggested");
    expect(result.message).toBe("Arrange a professional review.");
    expect(result.matchedRuleId).toBe("persistent_change");
  });

  it("uses reviewed neutral wording when no rule matches", () => {
    const result = evaluateGuidanceConfig(
      approvedConfig(),
      { duration_days: 2, rapidly_changing: false },
      NOW,
    );

    expect(result.enabled).toBe(true);
    expect(result.reviewPriority).toBe("neutral");
    expect(result.message).toBe("Use the neutral reviewed message.");
    expect(result.matchedRuleId).toBeNull();
  });

  it("fails closed after any reviewed payload edit", () => {
    const config = approvedConfig();
    config.messages["review.suggested"] = "Edited after approval.";
    const result = evaluateGuidanceConfig(
      config,
      { duration_days: 20, rapidly_changing: true },
      NOW,
    );

    expect(result.enabled).toBe(false);
    expect(result.reviewPriority).toBeNull();
    expect(result.statusMessage).toContain("changed after clinician approval");
  });

  it("fails closed when approval is expired or the file is disabled", () => {
    const expired = approvedConfig();
    expired.approval!.expires_at = "2026-07-27T11:59:59Z";
    expect(evaluateGuidanceConfig(expired, {}, NOW).enabled).toBe(false);

    const disabled = approvedConfig();
    disabled.enabled = false;
    expect(evaluateGuidanceConfig(disabled, {}, NOW).enabled).toBe(false);
  });

  it("does not match conditions whose inputs are missing", () => {
    const result = evaluateGuidanceConfig(
      approvedConfig(),
      { rapidly_changing: true },
      NOW,
    );

    expect(result.reviewPriority).toBe("neutral");
    expect(result.matchedRuleId).toBeNull();
  });
});
