import { z } from "zod";

import { deletionResponseSchema, type DeletionResponse } from "./contracts";

export const deletionPollingReceiptSchema = deletionResponseSchema
  .extend({
    accountId: z.string().min(1).max(128),
  })
  .strict();

export type DeletionPollingReceipt = z.infer<
  typeof deletionPollingReceiptSchema
>;

export type DeletionReceiptReadResult =
  | { kind: "missing" }
  | { kind: "present"; receipt: DeletionPollingReceipt }
  | { kind: "invalid" };

export interface DeletionReceiptStorageAdapter {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  deleteItem(key: string): Promise<void>;
}

export const DELETION_RECEIPT_KEY =
  "stoma3d.account-deletion.receipt.v1" as const;

export class DeletionReceiptRepository {
  constructor(
    private readonly storage: DeletionReceiptStorageAdapter,
    private readonly key = DELETION_RECEIPT_KEY,
  ) {}

  async read(): Promise<DeletionReceiptReadResult> {
    const raw = await this.storage.getItem(this.key);
    if (raw === null) return { kind: "missing" };
    try {
      const parsed = deletionPollingReceiptSchema.safeParse(JSON.parse(raw));
      return parsed.success
        ? { kind: "present", receipt: parsed.data }
        : { kind: "invalid" };
    } catch {
      return { kind: "invalid" };
    }
  }

  async write(receipt: DeletionPollingReceipt): Promise<void> {
    const parsed = deletionPollingReceiptSchema.parse(receipt);
    await this.storage.setItem(this.key, JSON.stringify(parsed));
  }

  clear(): Promise<void> {
    return this.storage.deleteItem(this.key);
  }
}

export function deletionReceiptFromResponse(
  accountId: string,
  response: DeletionResponse,
): DeletionPollingReceipt {
  return deletionPollingReceiptSchema.parse({ accountId, ...response });
}

export function deletionResponseFromReceipt(
  receipt: DeletionPollingReceipt,
): DeletionResponse {
  const { accountId: _accountId, ...response } = receipt;
  return deletionResponseSchema.parse(response);
}
