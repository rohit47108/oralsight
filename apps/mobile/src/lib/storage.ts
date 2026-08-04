import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import * as SQLite from "expo-sqlite";

import { deleteProtectedFilesAndRotateKey } from "@/lib/secureFiles";
import { parsePersistedAppState } from "@/lib/persistedStateSchema";
import type { PersistedAppState } from "@/types";

const DATABASE_NAME = "oralsight.db";
const DATABASE_KEY_NAME = "oralsight.database-key.v1";
let databasePromise: Promise<SQLite.SQLiteDatabase> | null = null;
let writeQueue: Promise<void> = Promise.resolve();

async function databaseKey(): Promise<string> {
  const stored = await SecureStore.getItemAsync(DATABASE_KEY_NAME);
  if (stored) return stored;
  const bytes = await Crypto.getRandomBytesAsync(32);
  const key = [...bytes]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  await SecureStore.setItemAsync(DATABASE_KEY_NAME, key, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  return key;
}

async function openDatabase(): Promise<SQLite.SQLiteDatabase> {
  const key = await databaseKey();
  const database = await SQLite.openDatabaseAsync(DATABASE_NAME);
  await database.execAsync(`PRAGMA key = "x'${key}'";`);
  await database.execAsync(`
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS app_state (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      payload TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
  `);
  return database;
}

async function getDatabase(): Promise<SQLite.SQLiteDatabase> {
  databasePromise ??= openDatabase();
  return databasePromise;
}

export async function loadPersistedState(): Promise<PersistedAppState | null> {
  const database = await getDatabase();
  const row = await database.getFirstAsync<{ payload: string }>(
    "SELECT payload FROM app_state WHERE id = 1",
  );
  if (!row) return null;
  return parsePersistedAppState(JSON.parse(row.payload) as unknown);
}

export function queuePersistedState(state: PersistedAppState): Promise<void> {
  const payload = JSON.stringify(state);
  const operation = writeQueue.then(async () => {
    const database = await getDatabase();
    await database.runAsync(
      `INSERT INTO app_state (id, payload, updated_at)
         VALUES (1, ?, ?)
         ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at`,
      payload,
      new Date().toISOString(),
    );
  });
  writeQueue = operation.catch(() => {
    console.warn("[ORALSIGHT_STORAGE_WRITE_FAILED]");
  });
  return operation;
}

export async function deleteAllLocalDataAndRotateKeys(): Promise<void> {
  const failures: string[] = [];
  try {
    await writeQueue;
  } catch {
    failures.push("WRITE_QUEUE");
  }
  if (databasePromise) {
    const pendingDatabase = databasePromise;
    databasePromise = null;
    try {
      const database = await pendingDatabase;
      await database.closeAsync();
    } catch {
      failures.push("DB_CLOSE");
    }
  }
  try {
    await SQLite.deleteDatabaseAsync(DATABASE_NAME);
  } catch {
    failures.push("DB_DELETE");
  }
  try {
    await SecureStore.deleteItemAsync(DATABASE_KEY_NAME);
  } catch {
    failures.push("DB_KEY_DELETE");
  }
  try {
    await deleteProtectedFilesAndRotateKey();
  } catch {
    failures.push("VAULT_RESET");
  }
  try {
    await databaseKey();
  } catch {
    failures.push("DB_KEY_ROTATE");
  }
  if (failures.length > 0) {
    throw new Error(`ORALSIGHT_LOCAL_RESET_INCOMPLETE:${failures.join(",")}`);
  }
}
