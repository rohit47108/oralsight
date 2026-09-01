import type { AnalysisResult } from "@stoma3d/contracts";

import type { IntakeProfile } from "@/types";

export type ReminderReason = "quality_retake" | "user_follow_up";

export interface ReminderSuggestion {
  reason: ReminderReason;
  delayDays: 1 | 7;
  title: string;
  description: string;
}

/**
 * This policy only chooses a convenient reminder time. It does not calculate
 * urgency and never reads appearance or disease-category model output.
 */
export function reminderSuggestion(
  profile: IntakeProfile | null,
  analysis: AnalysisResult | undefined,
): ReminderSuggestion {
  if (analysis && !analysis.quality.accepted) {
    return {
      reason: "quality_retake",
      delayDays: 1,
      title: "Retake reminder",
      description:
        "The saved image did not pass a quality check. Schedule a reminder for tomorrow if you want to try the photograph again.",
    };
  }

  const recentlyNoticed =
    profile?.durationDays !== undefined && profile.durationDays < 2;
  return {
    reason: "user_follow_up",
    delayDays: 7,
    title: recentlyNoticed
      ? "Optional seven-day follow-up"
      : "Follow-up reminder",
    description:
      "Choose this only as a personal reminder to review the saved observation. Do not wait for a reminder if the area changes, persists, worries you, or you want professional care.",
  };
}
