import { describe, expect, it } from "vitest";

import { reminderSuggestion } from "../src/lib/reminderPolicy";

describe("follow-up reminder policy", () => {
  it("suggests tomorrow only for an image-quality retake", () => {
    const suggestion = reminderSuggestion(null, {
      quality: { accepted: false },
    } as never);
    expect(suggestion).toMatchObject({
      reason: "quality_retake",
      delayDays: 1,
    });
  });

  it("uses a neutral seven-day user reminder without reading classifiers", () => {
    const suggestion = reminderSuggestion(
      {
        ageRange: "18_39",
        assisted: false,
        firstNoticed: "today",
        durationDays: 1,
        symptoms: [],
        change: "not_sure",
        tobaccoExposure: "none",
        alcoholExposure: "none",
        previousConditions: "",
        professionallyExamined: false,
      },
      {
        quality: { accepted: true },
        diseaseResearchOutput: {
          enabled: true,
          gatePassed: true,
          topLabel: "ignored",
        },
      } as never,
    );
    expect(suggestion).toMatchObject({
      reason: "user_follow_up",
      delayDays: 7,
    });
    expect(suggestion.description).not.toMatch(/classifier|cancer|risk/i);
  });
});
