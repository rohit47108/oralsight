import { describe, expect, it } from "vitest";

import { operationKeyFromForm, parseOperationKey } from "@/lib/operation-key";

describe("operation keys", () => {
  it("accepts a browser-generated UUID", () => {
    const key = "019cfd1d-9fb7-7a55-b261-a7510f678c21";
    expect(parseOperationKey(key)).toBe(key);
    const form = new FormData();
    form.set("operationKey", key);
    expect(operationKeyFromForm(form)).toBe(key);
  });

  it("fails closed for missing or malformed keys", () => {
    expect(parseOperationKey(undefined)).toBeNull();
    expect(parseOperationKey("retry-me")).toBeNull();
    expect(operationKeyFromForm(new FormData())).toBeNull();
  });
});
