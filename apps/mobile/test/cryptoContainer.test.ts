import { describe, expect, it } from "vitest";

import { openAesGcm, sealAesGcm } from "../src/lib/cryptoContainer";

describe("AES-256-GCM protected file container", () => {
  const key = Uint8Array.from({ length: 32 }, (_, index) => index + 1);
  const nonce = Uint8Array.from({ length: 12 }, (_, index) => index + 10);

  it("round-trips protected bytes", () => {
    const plaintext = new TextEncoder().encode("Stoma3D protected fixture");
    expect(openAesGcm(key, sealAesGcm(key, nonce, plaintext))).toEqual(
      plaintext,
    );
  });

  it("rejects authenticated-ciphertext tampering", () => {
    const sealed = sealAesGcm(key, nonce, new Uint8Array([1, 2, 3]));
    sealed[sealed.length - 1] = (sealed.at(-1) ?? 0) ^ 1;
    expect(() => openAesGcm(key, sealed)).toThrow();
  });

  it("binds protected bytes to their record identity", () => {
    const recordA = new TextEncoder().encode("capture:a");
    const recordB = new TextEncoder().encode("capture:b");
    const sealed = sealAesGcm(key, nonce, new Uint8Array([4, 5, 6]), recordA);
    expect(openAesGcm(key, sealed, recordA)).toEqual(new Uint8Array([4, 5, 6]));
    expect(() => openAesGcm(key, sealed, recordB)).toThrow();
  });
});
