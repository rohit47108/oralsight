import { PlatformClient } from "./client";
import type { ConsentDocument, ProductConsent } from "./contracts";

export interface ProductConsentState {
  document: ConsentDocument;
  activeConsent: ProductConsent | null;
}

export async function loadProductConsentState(
  client = new PlatformClient(),
): Promise<ProductConsentState> {
  const [document, records] = await Promise.all([
    client.currentConsentDocument(),
    client.listProductConsents(),
  ]);
  const activeConsent =
    records.items.find(
      (record) =>
        record.active &&
        record.accepted &&
        record.documentId === document.documentId &&
        record.documentVersion === document.documentVersion &&
        record.documentSha256 === document.documentSha256,
    ) ?? null;
  return { document, activeConsent };
}

export async function requireActiveProductConsent(
  client = new PlatformClient(),
): Promise<ProductConsent> {
  const state = await loadProductConsentState(client);
  if (!state.activeConsent) {
    throw new Error(
      "Review and accept the current cloud consent before syncing health records.",
    );
  }
  return state.activeConsent;
}
