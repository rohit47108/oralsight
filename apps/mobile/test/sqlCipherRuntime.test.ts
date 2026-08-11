import { describe, expect, it, vi } from "vitest";

import { assertSqlCipherRuntime } from "../src/lib/sqlCipherRuntime";

describe("SQLCipher runtime verification", () => {
  it("accepts a codec build with an encrypted database header", async () => {
    const getFirstAsync = vi
      .fn()
      .mockResolvedValueOnce({ cipher_version: "4.6.1 community" })
      .mockResolvedValueOnce({ cipher_plaintext_header_size: 0 });

    await expect(
      assertSqlCipherRuntime({ getFirstAsync }),
    ).resolves.toBeUndefined();
  });

  it("fails closed when plain SQLite ignores the cipher pragma", async () => {
    const getFirstAsync = vi.fn().mockResolvedValueOnce(null);

    await expect(assertSqlCipherRuntime({ getFirstAsync })).rejects.toThrow(
      "Encrypted storage is unavailable",
    );
  });

  it("rejects a plaintext database header configuration", async () => {
    const getFirstAsync = vi
      .fn()
      .mockResolvedValueOnce({ cipher_version: "4.6.1" })
      .mockResolvedValueOnce({ cipher_plaintext_header_size: 32 });

    await expect(assertSqlCipherRuntime({ getFirstAsync })).rejects.toThrow(
      "database header",
    );
  });
});
