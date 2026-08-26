import {
  MOUTH_REGION_DETAILS,
  MOUTH_REGIONS,
  type MouthRegion,
} from "@oralsight/contracts";

export interface AnatomyLesson {
  region: MouthRegion;
  name: string;
  shortName: string;
  purpose: string;
  captureInstruction: string;
  observationPrompt: string;
}

const PURPOSE_BY_REGION: Record<MouthRegion, string> = {
  dorsal_tongue: "The broad upper surface of the tongue.",
  ventral_tongue:
    "The underside of the tongue and the nearby floor of the mouth.",
  left_buccal_mucosa: "The soft lining inside the left cheek.",
  right_buccal_mucosa: "The soft lining inside the right cheek.",
  upper_lip: "The moist inner surface of the upper lip.",
  lower_lip: "The moist inner surface of the lower lip.",
  upper_dental_arch:
    "The upper teeth and the gum tissue immediately around them.",
  lower_dental_arch:
    "The lower teeth and the gum tissue immediately around them.",
};

const PROMPT_BY_REGION: Record<MouthRegion, string> = {
  dorsal_tongue:
    "Notice whether the same area can be seen clearly from the center to both sides.",
  ventral_tongue:
    "Keep the tongue lifted and avoid covering the tissue with a finger or tool.",
  left_buccal_mucosa:
    "Use nearby teeth as landmarks so a later photograph can use a similar angle.",
  right_buccal_mucosa:
    "Use nearby teeth as landmarks so a later photograph can use a similar angle.",
  upper_lip:
    "Keep the lip relaxed and include enough surrounding tissue for context.",
  lower_lip:
    "Keep the lip relaxed and include enough surrounding tissue for context.",
  upper_dental_arch:
    "Include the gumline without letting the teeth fill the entire frame.",
  lower_dental_arch:
    "Include the gumline without letting the teeth fill the entire frame.",
};

export const ANATOMY_LESSONS: readonly AnatomyLesson[] = MOUTH_REGIONS.map(
  (region) => {
    const detail = MOUTH_REGION_DETAILS.find((item) => item.id === region);
    if (!detail) throw new Error(`Missing education metadata for ${region}.`);
    return {
      region,
      name: detail.label,
      shortName: detail.shortLabel,
      purpose: PURPOSE_BY_REGION[region],
      captureInstruction: detail.captureInstruction,
      observationPrompt: PROMPT_BY_REGION[region],
    };
  },
);

export interface QualityPracticeScenario {
  id: string;
  title: string;
  prompt: string;
  choices: readonly string[];
  correctChoice: string;
  correction: string;
  visual:
    | "low_light"
    | "overexposure"
    | "too_near"
    | "too_far"
    | "glare"
    | "blur"
    | "obstruction"
    | "incomplete_coverage"
    | "ready";
  isPracticeOnly: true;
}

export const QUALITY_PRACTICE_SCENARIOS: readonly QualityPracticeScenario[] = [
  {
    id: "low_light",
    title: "Not enough light",
    prompt:
      "The target is dim and its edges disappear into shadow. What should change?",
    choices: [
      "Add soft, even light",
      "Move closer until the camera touches",
      "Accept the dark image",
    ],
    correctChoice: "Add soft, even light",
    correction:
      "Move to a brighter area or add a steady, diffuse light in front of the mouth without aiming a harsh beam at wet tissue.",
    visual: "low_light",
    isPracticeOnly: true,
  },
  {
    id: "overexposure",
    title: "Too much light",
    prompt: "Large pale areas have lost visible detail. What should change?",
    choices: [
      "Reduce or redirect the light",
      "Turn on another direct flash",
      "Cover the pale area",
    ],
    correctChoice: "Reduce or redirect the light",
    correction:
      "Turn down a direct light, move it farther away, or change its angle until natural tissue detail returns across the frame.",
    visual: "overexposure",
    isPracticeOnly: true,
  },
  {
    id: "too_near",
    title: "Too close",
    prompt:
      "A small patch fills the frame and the surrounding landmarks are missing. What should change?",
    choices: [
      "Back away slightly",
      "Zoom in farther",
      "Crop out the remaining landmarks",
    ],
    correctChoice: "Back away slightly",
    correction:
      "Back away until the full named region and nearby landmarks are visible, then wait for focus before capturing.",
    visual: "too_near",
    isPracticeOnly: true,
  },
  {
    id: "too_far",
    title: "Too far away",
    prompt: "The target is only a tiny part of the frame. What should change?",
    choices: [
      "Move closer while keeping context",
      "Use the distant image",
      "Cover the empty space with a finger",
    ],
    correctChoice: "Move closer while keeping context",
    correction:
      "Move closer until the named region is large enough to inspect while keeping enough surrounding tissue to recognize the location later.",
    visual: "too_far",
    isPracticeOnly: true,
  },
  {
    id: "glare",
    title: "Bright reflection",
    prompt: "A white reflection hides part of the target. What should change?",
    choices: [
      "Change the light angle",
      "Crop the reflection out",
      "Accept it anyway",
    ],
    correctChoice: "Change the light angle",
    correction:
      "Move the light or phone slightly so the reflection no longer covers the area, then check that the rest of the frame stays evenly lit.",
    visual: "glare",
    isPracticeOnly: true,
  },
  {
    id: "blur",
    title: "Soft detail",
    prompt:
      "The tissue edges and nearby landmarks look smeared. What should change?",
    choices: [
      "Hold still and refocus",
      "Turn the flash higher",
      "Move much closer",
    ],
    correctChoice: "Hold still and refocus",
    correction:
      "Brace your hands, wait for the stability ring, and let the camera refocus.",
    visual: "blur",
    isPracticeOnly: true,
  },
  {
    id: "obstruction",
    title: "Blocked view",
    prompt: "A finger covers the edge of the target. What should change?",
    choices: [
      "Move the obstruction",
      "Zoom until it disappears",
      "Use a filter",
    ],
    correctChoice: "Move the obstruction",
    correction:
      "Reposition the hand or ask a helper to move tissue gently without covering the named region or nearby landmarks.",
    visual: "obstruction",
    isPracticeOnly: true,
  },
  {
    id: "incomplete_coverage",
    title: "Region partly missing",
    prompt:
      "The center is visible, but one side of the named region is outside the frame. What should change?",
    choices: [
      "Reframe to include the whole region",
      "Treat the visible center as complete",
      "Stretch the saved image afterward",
    ],
    correctChoice: "Reframe to include the whole region",
    correction:
      "Reposition the phone and tissue until the full named region is visible from boundary to boundary with useful landmarks around it.",
    visual: "incomplete_coverage",
    isPracticeOnly: true,
  },
  {
    id: "ready",
    title: "Clear and centered",
    prompt:
      "The target is sharp, evenly lit, and surrounded by useful landmarks.",
    choices: ["Capture the image", "Add more glare", "Hide the landmarks"],
    correctChoice: "Capture the image",
    correction:
      "This practice framing is ready for the app's live quality and anatomy checks. Those checks can still ask for another image.",
    visual: "ready",
    isPracticeOnly: true,
  },
];

export interface KnowledgeQuestion {
  id: string;
  prompt: string;
  choices: readonly string[];
  correctIndex: number;
  explanation: string;
}

export const KNOWLEDGE_QUESTIONS: readonly KnowledgeQuestion[] = [
  {
    id: "quality",
    prompt: "Why does OralSight reject a blurry image?",
    choices: [
      "Blur can hide the detail needed for a useful comparison",
      "Blur always means an area is harmless",
      "Only expensive phones can take useful images",
    ],
    correctIndex: 0,
    explanation:
      "A clear image preserves landmarks and visible detail. Rejection is about image usefulness, not a medical conclusion.",
  },
  {
    id: "alignment",
    prompt: "Why use a similar angle for a follow-up image?",
    choices: [
      "It guarantees a diagnosis",
      "It reduces changes caused only by framing",
      "It makes every physical measurement exact",
    ],
    correctIndex: 1,
    explanation:
      "Similar framing makes visual comparison more useful, but tissue movement and lighting can still limit it.",
  },
  {
    id: "result",
    prompt: "What can an OralSight result establish?",
    choices: [
      "A visible observation and its stated limits",
      "That an area is cancer",
      "That an area is harmless",
    ],
    correctIndex: 0,
    explanation:
      "The app can organize visible observations and changes. It cannot determine the cause or replace an examination.",
  },
  {
    id: "sharing",
    prompt: "What should a shared report contain?",
    choices: [
      "Every item in the account",
      "Only the selected observations and needed context",
      "An invented urgency score when review rules are unavailable",
    ],
    correctIndex: 1,
    explanation:
      "Share only what is needed, for a limited time, and keep the link revocable.",
  },
];

export const APPOINTMENT_QUESTIONS = [
  "Does this area need a direct examination?",
  "Would a professional photograph make future comparison more useful?",
  "Are any additional tests or a specialist referral appropriate?",
  "What changes should prompt an earlier follow-up?",
  "When should this area be reviewed again?",
] as const;
