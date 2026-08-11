interface SqlCipherVersionRow {
  cipher_version?: string | null;
}

interface SqlCipherHeaderRow {
  cipher_plaintext_header_size?: number | string | null;
}

export interface SqlCipherDatabase {
  getFirstAsync<T>(source: string): Promise<T | null>;
}

export async function assertSqlCipherRuntime(
  database: SqlCipherDatabase,
): Promise<void> {
  const version = await database.getFirstAsync<SqlCipherVersionRow>(
    "PRAGMA cipher_version;",
  );
  if (!version?.cipher_version?.trim()) {
    throw new Error(
      "Encrypted storage is unavailable in this build. Install an OralSight development or release build with SQLCipher enabled.",
    );
  }
  const header = await database.getFirstAsync<SqlCipherHeaderRow>(
    "PRAGMA cipher_plaintext_header_size;",
  );
  if (Number(header?.cipher_plaintext_header_size) !== 0) {
    throw new Error(
      "Encrypted storage is not configured to protect the database header.",
    );
  }
}
