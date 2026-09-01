import Constants from "expo-constants";
import { Platform } from "react-native";

import { useStoma3DStore } from "../store/useStoma3DStore";

import { PlatformClient } from "./client";
import { analyticsEventSchema, type AnalyticsEvent } from "./contracts";
import { readCloudConfig } from "./config";
import { readDeletionPollingReceipt } from "./deletionReceiptStorage";
import { restoreCloudSession } from "./session";

export type ProductAnalyticsEvent = Pick<
  AnalyticsEvent,
  "name" | "surface" | "outcome"
>;

function appVersion(): string {
  const candidate = Constants.expoConfig?.version ?? "0.1.0";
  return /^[A-Za-z0-9._+-]{1,32}$/.test(candidate) ? candidate : "unknown";
}

/**
 * Sends a deliberately identifier-free event only after local and account
 * consent are both enabled. Events are best effort and never block product use.
 */
export async function trackProductEvent(
  event: ProductAnalyticsEvent,
): Promise<boolean> {
  const deletionReceipt = await readDeletionPollingReceipt().catch(() => ({
    kind: "invalid" as const,
  }));
  if (
    deletionReceipt.kind !== "missing" ||
    !useStoma3DStore.getState().settings.analyticsOptIn ||
    !readCloudConfig() ||
    !(await restoreCloudSession())
  ) {
    return false;
  }
  const platform =
    Platform.OS === "ios"
      ? "ios"
      : Platform.OS === "android"
        ? "android"
        : "web";
  const parsed = analyticsEventSchema.parse({
    ...event,
    platform,
    appVersion: appVersion(),
  });
  try {
    await new PlatformClient().submitAnalytics([parsed]);
    return true;
  } catch {
    return false;
  }
}
