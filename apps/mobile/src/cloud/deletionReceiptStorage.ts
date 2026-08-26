import * as SecureStore from "expo-secure-store";

import { DeletionReceiptRepository } from "./deletionReceipt";

const secureDeletionReceiptRepository = new DeletionReceiptRepository({
  getItem: (key) => SecureStore.getItemAsync(key),
  setItem: (key, value) =>
    SecureStore.setItemAsync(key, value, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    }),
  deleteItem: (key) => SecureStore.deleteItemAsync(key),
});

export const readDeletionPollingReceipt = () =>
  secureDeletionReceiptRepository.read();

export const persistDeletionPollingReceipt = (
  receipt: Parameters<DeletionReceiptRepository["write"]>[0],
) => secureDeletionReceiptRepository.write(receipt);

export const clearDeletionPollingReceipt = () =>
  secureDeletionReceiptRepository.clear();
