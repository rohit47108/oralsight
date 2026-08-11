import type {
  AnalysisResult,
  CalibrationResult,
  CaptureAngle,
  CaptureProtocol,
  ComparisonResult,
  InputOrigin,
  MediaKind,
  MouthRegion,
  QualityResult,
} from "@oralsight/contracts";

import type { CaptureGuidanceSnapshot } from "@/components/captureGuidance";

export type AgeRange =
  "under_18" | "18_39" | "40_64" | "65_plus" | "prefer_not_to_say";

export type AnimationSpeed = "slow" | "standard";

export interface IntakeProfile {
  ageRange: AgeRange;
  assisted: boolean;
  firstNoticed: string;
  durationDays?: number;
  symptoms: string[];
  bleedingFrequency?: "once" | "occasionally" | "often";
  bleedingDuration?: string;
  change: "not_sure" | "no_change" | "slow_change" | "rapid_change";
  tobaccoExposure: "none" | "past" | "current" | "prefer_not_to_say";
  alcoholExposure: "none" | "some" | "frequent" | "prefer_not_to_say";
  previousConditions: string;
  professionallyExamined: boolean;
}

export interface AccessibilitySettings {
  highContrast: boolean;
  largeText: boolean;
  reducedMotion: boolean;
  animationSpeed: AnimationSpeed;
  haptics: boolean;
  voiceInstructions: boolean;
  caregiverMode: boolean;
  /** Optional, non-health product analytics. Always false until chosen. */
  analyticsOptIn: boolean;
}

export interface ScanSession {
  id: string;
  createdAt: string;
  demo: boolean;
  label: string;
  protocol: CaptureProtocol;
  /** Intake and consent are snapshotted so older reports cannot drift. */
  intakeProfile?: IntakeProfile | null;
  consentedAt?: string | null;
}

export interface CaptureRecord {
  id: string;
  sessionId: string;
  region: MouthRegion;
  angle: CaptureAngle;
  mediaKind: Extract<MediaKind, "image" | "video_frame">;
  capturedAt: string;
  encryptedUri: string | null;
  mimeType: "image/jpeg" | "image/png";
  inputOrigin: InputOrigin;
  fixtureSha256?: string;
  captureSource?: "camera" | "photo_library" | "video_sweep" | "developer_demo";
  /** Kept only for an extracted frame; the raw sweep is deleted after use. */
  sourceVideoDurationMs?: number;
  frameTimeMs?: number;
  calibrationRequested?: boolean;
  calibrationPlaneConfirmed?: boolean;
  calibrationCardVersion?: "oralsight-calibration-v1";
  calibration?: CalibrationResult;
  privacyConfirmedByUser?: boolean;
  regionConfirmedByUser?: boolean;
  captureGuidance?: CaptureGuidanceSnapshot;
  quality: QualityResult;
  samplePlaceholder?: boolean;
}

export interface ObservationPin {
  id: string;
  region: MouthRegion;
  meshId: string;
  uvX: number;
  uvY: number;
  assetVersion: string;
  userConfirmed: boolean;
  firstObservedAt: string;
  status:
    | "monitoring"
    | "retake_required"
    | "stable"
    | "visually_changed"
    | "review_unavailable";
  comparisonStatus?:
    | "stable"
    | "increased_estimated_size"
    | "decreased_estimated_size"
    | "color_or_texture_changed"
    | "shape_changed"
    | "insufficient_comparable_data";
  captureIds: string[];
}

export interface ReportRecord {
  id: string;
  createdAt: string;
  encryptedUri: string;
  sessionId: string;
}

export interface PersistedAppState {
  schemaVersion: 4;
  consentedAt: string | null;
  profile: IntakeProfile | null;
  settings: AccessibilitySettings;
  sessions: ScanSession[];
  captures: CaptureRecord[];
  analyses: Record<string, AnalysisResult>;
  comparisons: ComparisonResult[];
  pins: ObservationPin[];
  reports: ReportRecord[];
  activeSessionId: string | null;
}
