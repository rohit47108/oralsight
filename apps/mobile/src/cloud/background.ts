import * as BackgroundTask from "expo-background-task";
import * as TaskManager from "expo-task-manager";

import { readCloudConfig } from "./config";
import { restoreCloudSession } from "./session";
import { rememberCloudSyncError, runCloudSync } from "./sync";

export const CLOUD_SYNC_TASK = "oralsight-encrypted-cloud-sync-v1";

if (!TaskManager.isTaskDefined(CLOUD_SYNC_TASK)) {
  TaskManager.defineTask(CLOUD_SYNC_TASK, async () => {
    try {
      if (!readCloudConfig() || !(await restoreCloudSession())) {
        return BackgroundTask.BackgroundTaskResult.Success;
      }
      await runCloudSync();
      return BackgroundTask.BackgroundTaskResult.Success;
    } catch (error) {
      await rememberCloudSyncError(error).catch(() => undefined);
      return BackgroundTask.BackgroundTaskResult.Failed;
    }
  });
}

export async function registerCloudBackgroundSync(): Promise<void> {
  if (!readCloudConfig()) return;
  const registered = await TaskManager.isTaskRegisteredAsync(CLOUD_SYNC_TASK);
  if (registered) return;
  await BackgroundTask.registerTaskAsync(CLOUD_SYNC_TASK, {
    minimumInterval: 15,
  });
}

export async function unregisterCloudBackgroundSync(): Promise<void> {
  if (await TaskManager.isTaskRegisteredAsync(CLOUD_SYNC_TASK)) {
    await BackgroundTask.unregisterTaskAsync(CLOUD_SYNC_TASK);
  }
}
