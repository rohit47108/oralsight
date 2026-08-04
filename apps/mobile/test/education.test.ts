import { describe, expect, it } from "vitest";
import { MOUTH_REGIONS } from "@oralsight/contracts";

import {
  ANATOMY_LESSONS,
  KNOWLEDGE_QUESTIONS,
  QUALITY_PRACTICE_SCENARIOS,
} from "../src/lib/education";

describe("education content", () => {
  it("covers the exact canonical eight regions once", () => {
    expect(ANATOMY_LESSONS.map((item) => item.region)).toEqual(MOUTH_REGIONS);
    expect(new Set(ANATOMY_LESSONS.map((item) => item.region)).size).toBe(8);
  });

  it("keeps every practice scenario answer explicit", () => {
    for (const scenario of QUALITY_PRACTICE_SCENARIOS) {
      expect(scenario.choices).toContain(scenario.correctChoice);
      expect(scenario.correction.length).toBeGreaterThan(20);
    }
  });

  it("keeps every knowledge answer within its choices", () => {
    for (const question of KNOWLEDGE_QUESTIONS) {
      expect(question.correctIndex).toBeGreaterThanOrEqual(0);
      expect(question.correctIndex).toBeLessThan(question.choices.length);
    }
  });
});
