import { describe, expect, it, vi } from "vitest";

import { writeTemporaryBase64File } from "../src/lib/safeTemporaryWrite";

describe("temporary plaintext write cleanup", () => {
  it("deletes a partially written destination before returning the write error", async () => {
    const writeError = new Error("simulated partial write");
    const writeBase64 = vi.fn().mockRejectedValue(writeError);
    const deleteFile = vi.fn().mockResolvedValue(undefined);

    await expect(
      writeTemporaryBase64File("cache://share/report.pdf", "bytes", {
        writeBase64,
        delete: deleteFile,
      }),
    ).rejects.toBe(writeError);

    expect(deleteFile).toHaveBeenCalledOnce();
    expect(deleteFile).toHaveBeenCalledWith("cache://share/report.pdf");
  });

  it("fails closed when the partial file cannot be removed", async () => {
    const writeBase64 = vi.fn().mockRejectedValue(new Error("write failed"));
    const deleteFile = vi.fn().mockRejectedValue(new Error("delete failed"));

    await expect(
      writeTemporaryBase64File("cache://share/report.pdf", "bytes", {
        writeBase64,
        delete: deleteFile,
      }),
    ).rejects.toThrow("Temporary file cleanup failed");
  });
});
