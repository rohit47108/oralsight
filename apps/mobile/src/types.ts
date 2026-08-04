import type {
  AnalysisResult,
  ComparisonResult,
  InputOrigin,
  MouthRegion,
  QualityResult,
} from "@oralsight/contracts";

export type AgeRange =
  "under_18" | "18_39" | "40_64" | "65_plus" | "prefer_not_to_say";

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
  haptics: boolean;
  voiceInstructions: boolean;
  caregiverMode: boolean;
}

export interface ScanSession {
  id: string;
  createdAt: string;
  demo: boolean;
  label: string;
  /** Intake and consent are snapshotted so older reports cannot drift. */
  intakeProfile?: IntakeProfile | null;
  consentedAt?: string | null;
}

export interface CaptureRecord {
  id: string;
  sessionId: string;
  region: MouthRegion;
  capturedAt: string;
  encryptedUri: string | null;
  mimeType: "image/jpeg" | "image/png";
  inputOrigin: InputOrigin;
  fixtureSha256?: string;
  captureSource?: "camera" | "photo_library" | "developer_demo";
  privacyConfirmedByUser?: boolean;
  regionConfirmedByUser?: boolean;
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
  captureIds: string[];
}

export interface ReportRecord {
  id: string;
  createdAt: string;
  encryptedUri: string;
  sessionId: string;
}

export interface PersistedAppState {
  schemaVersion: 2;
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
