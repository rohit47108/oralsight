import { gcm } from "@noble/ciphers/aes.js";

export const AES_GCM_NONCE_LENGTH = 12;
const CONTAINER_VERSION = 2;

export function sealAesGcm(
  key: Uint8Array,
  nonce: Uint8Array,
  plaintext: Uint8Array,
  associatedData?: Uint8Array,
): Uint8Array {
  if (key.length !== 32)
    throw new Error("OralSight file keys must be 256 bits.");
  if (nonce.length !== AES_GCM_NONCE_LENGTH)
    throw new Error("OralSight AES-GCM nonces must be 96 bits.");
  const ciphertext = gcm(key, nonce, associatedData).encrypt(plaintext);
  const packed = new Uint8Array(1 + nonce.length + ciphertext.length);
  packed[0] = CONTAINER_VERSION;
  packed.set(nonce, 1);
  packed.set(ciphertext, 1 + nonce.length);
  return packed;
}

export function openAesGcm(
  key: Uint8Array,
  packed: Uint8Array,
  associatedData?: Uint8Array,
): Uint8Array {
  if (key.length !== 32)
    throw new Error("OralSight file keys must be 256 bits.");
  if (
    packed[0] !== CONTAINER_VERSION ||
    packed.length <= AES_GCM_NONCE_LENGTH + 1
  ) {
    throw new Error("Unsupported protected file format.");
  }
  const nonce = packed.slice(1, 1 + AES_GCM_NONCE_LENGTH);
  const ciphertext = packed.slice(1 + AES_GCM_NONCE_LENGTH);
  return gcm(key, nonce, associatedData).decrypt(ciphertext);
}
