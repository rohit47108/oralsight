const OPERATION_KEY_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function parseOperationKey(value: unknown): string | null {
  const key = typeof value === "string" ? value.trim() : "";
  return OPERATION_KEY_PATTERN.test(key) ? key : null;
}

export function operationKeyFromForm(formData: FormData): string | null {
  return parseOperationKey(formData.get("operationKey"));
}
