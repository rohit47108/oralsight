export type CloudErrorCode =
  | "offline"
  | "timeout"
  | "unauthenticated"
  | "forbidden"
  | "recreation_required"
  | "not_found"
  | "conflict"
  | "validation"
  | "rate_limited"
  | "server"
  | "invalid_response"
  | "cancelled"
  | "integrity"
  | "upload_unavailable"
  | "unknown";

export interface CloudErrorOptions {
  code: CloudErrorCode;
  message: string;
  retryable?: boolean;
  status?: number;
  requestId?: string;
  serverCode?: string;
  cause?: unknown;
}

/** A deliberately small, safe error object suitable for UI and retry decisions. */
export class CloudError extends Error {
  readonly code: CloudErrorCode;
  readonly retryable: boolean;
  readonly status?: number;
  readonly requestId?: string;
  readonly serverCode?: string;

  constructor(options: CloudErrorOptions) {
    super(options.message, { cause: options.cause });
    this.name = "CloudError";
    this.code = options.code;
    this.retryable = options.retryable ?? false;
    this.status = options.status;
    this.requestId = options.requestId;
    this.serverCode = options.serverCode;
  }
}

export const isCloudError = (value: unknown): value is CloudError =>
  value instanceof CloudError;

export function cloudErrorFromStatus(
  status: number,
  options: {
    requestId?: string;
    serverCode?: string;
    serverMessage?: string;
  } = {},
): CloudError {
  const common = {
    status,
    requestId: options.requestId,
    serverCode: options.serverCode,
  };
  if (status === 401) {
    return new CloudError({
      ...common,
      code: "unauthenticated",
      message: "Please sign in again.",
    });
  }
  if (status === 403) {
    return new CloudError({
      ...common,
      code: "forbidden",
      message: "This action is not allowed.",
    });
  }
  if (
    status === 410 &&
    options.serverCode === "account_deleted_recreation_required"
  ) {
    return new CloudError({
      ...common,
      code: "recreation_required",
      message: "This account was deleted. Confirm recreation to continue.",
    });
  }
  if (status === 404) {
    return new CloudError({
      ...common,
      code: "not_found",
      message: "The requested item was not found.",
    });
  }
  if (status === 409) {
    return new CloudError({
      ...common,
      code: "conflict",
      message: "This change conflicts with a newer change.",
    });
  }
  if (status === 408 || status === 504) {
    return new CloudError({
      ...common,
      code: "timeout",
      message: "The request timed out.",
      retryable: true,
    });
  }
  if (status === 429) {
    return new CloudError({
      ...common,
      code: "rate_limited",
      message: "Too many requests. Please try again shortly.",
      retryable: true,
    });
  }
  if (status >= 500) {
    return new CloudError({
      ...common,
      code: "server",
      message: "The service is temporarily unavailable.",
      retryable: true,
    });
  }
  if (status === 400 || status === 422) {
    return new CloudError({
      ...common,
      code: "validation",
      message: options.serverMessage ?? "The request could not be accepted.",
    });
  }
  return new CloudError({
    ...common,
    code: "unknown",
    message: "The request could not be completed.",
  });
}
