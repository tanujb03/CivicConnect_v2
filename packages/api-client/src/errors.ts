/** The error envelope of the CivicConnect API: `{ "error": { "code", "message", "details", "request_id" } }` (design §51A.1). */
export interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: Record<string, unknown>; request_id?: string | null };
  detail?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  /** Stable machine code, e.g. `AUTH_INVALID_TOKEN`, `PASSWORD_CHANGE_REQUIRED`, `RATE_LIMITED`, `FLAG_ALREADY_EXISTS`. `HTTP_<status>` when the body had none. */
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;
  /** Seconds from the `Retry-After` header (429), when present. */
  readonly retryAfterSeconds: number | null;

  constructor(init: { status: number; code: string; message: string; details?: Record<string, unknown>; requestId?: string | null; retryAfterSeconds?: number | null }) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.details = init.details ?? {};
    this.requestId = init.requestId ?? null;
    this.retryAfterSeconds = init.retryAfterSeconds ?? null;
  }

  static from(response: Response, body: unknown): ApiError {
    const env = (typeof body === "object" && body !== null ? body : {}) as ErrorEnvelope;
    const err = env.error ?? {};
    const retry = Number(response.headers.get("retry-after"));
    return new ApiError({
      status: response.status,
      code: err.code ?? `HTTP_${response.status}`,
      message: err.message ?? (typeof env.detail === "string" ? env.detail : `Request failed with status ${response.status}`),
      details: err.details ?? {},
      requestId: err.request_id ?? response.headers.get("x-request-id"),
      retryAfterSeconds: Number.isFinite(retry) && retry > 0 ? retry : null,
    });
  }
}
