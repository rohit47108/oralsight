import { DISCLAIMER } from "@oralsight/contracts";

export { DISCLAIMER };

export const APP_NAME = "OralSight";
export const APP_TAGLINE = "See changes. Track patterns. Seek care sooner.";
export const ORAL_MAP_ASSET_VERSION = "procedural-v1";
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_INFERENCE_URL ?? "http://127.0.0.1:8000";
export const TRANSPORT_IMAGE_BYTE_LIMIT = 1_750_000;

export const NEUTRAL_SEEK_CARE_COPY =
  "If an area persists, changes, or worries you, arrange an examination with a dentist or medical professional. Seek urgent care for trouble breathing, severe bleeding, or an inability to swallow.";
