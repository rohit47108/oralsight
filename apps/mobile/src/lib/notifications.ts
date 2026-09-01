import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { DISCLAIMER } from "@/constants";
import type { ReminderSuggestion } from "@/lib/reminderPolicy";

const REMINDER_CHANNEL_ID = "stoma3d-follow-up";

export async function configureLocalNotifications(): Promise<void> {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldPlaySound: false,
      shouldSetBadge: false,
      shouldShowBanner: true,
      shouldShowList: true,
    }),
  });
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync(REMINDER_CHANNEL_ID, {
      name: "Stoma3D follow-up reminders",
      description: "Reminders you explicitly schedule for saved observations.",
      importance: Notifications.AndroidImportance.DEFAULT,
      vibrationPattern: [0, 180],
      lightColor: "#0B7A75",
      sound: null,
    });
  }
}

async function notificationPermissionGranted(): Promise<boolean> {
  const current = await Notifications.getPermissionsAsync();
  if (current.granted) return true;
  const requested = await Notifications.requestPermissionsAsync();
  return requested.granted;
}

export async function scheduleObservationReminder(input: {
  captureId: string;
  suggestion: ReminderSuggestion;
}): Promise<{ id: string; scheduledFor: Date }> {
  await configureLocalNotifications();
  if (!(await notificationPermissionGranted())) {
    throw new Error(
      "Notifications are disabled. You can enable them in device settings or continue without a reminder.",
    );
  }
  const seconds = input.suggestion.delayDays * 24 * 60 * 60;
  const scheduledFor = new Date(Date.now() + seconds * 1_000);
  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title:
        input.suggestion.reason === "quality_retake"
          ? "Your Stoma3D retake reminder"
          : "Your Stoma3D follow-up reminder",
      body: `You asked to review a saved mouth observation. ${DISCLAIMER}`,
      data: {
        kind: "stoma3d_observation_reminder",
        captureId: input.captureId,
      },
      sound: false,
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds,
      repeats: false,
      channelId: REMINDER_CHANNEL_ID,
    },
  });
  return { id, scheduledFor };
}

export async function cancelAllStoma3DReminders(): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
  await Notifications.setBadgeCountAsync(0).catch(() => false);
}

export function reminderCaptureId(
  notification: Notifications.Notification,
): string | null {
  const data = notification.request.content.data;
  if (data?.kind !== "stoma3d_observation_reminder") return null;
  const captureId = data.captureId;
  return typeof captureId === "string" &&
    captureId.length <= 128 &&
    /^[A-Za-z0-9:_-]+$/.test(captureId)
    ? captureId
    : null;
}
