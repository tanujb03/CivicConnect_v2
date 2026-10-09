import createClient, { type Client } from "openapi-fetch";
import { ApiError } from "./errors.js";
import type { paths } from "./schema.js";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

/** Where the app keeps its tokens (SecureStore in Expo, localStorage or memory in the browser). */
export interface TokenStore {
  get(): TokenPair | null | Promise<TokenPair | null>;
  set(tokens: TokenPair): void | Promise<void>;
  clear(): void | Promise<void>;
}

export interface ApiClientOptions {
  /** The API origin (`https://api.example.org`), or the origin plus `/api/v1`: the generated paths already start with `/api/v1`, so that suffix is stripped. */
  baseUrl: string;
  tokens: TokenStore;
  /** Defaults to the global `fetch` (browser, React Native, Node 18+). */
  fetch?: typeof fetch;
  /** Idempotency keys; the default uses `crypto.randomUUID()` and falls back to a random v4 string where it does not exist. */
  uuid?: () => string;
  /** Called when a 401 could not be repaired by a refresh: send the user to the sign-in screen. */
  onAuthLost?: () => void;
  /** Extra headers on every request (for example `Accept-Language`). */
  headers?: Record<string, string>;
}

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const NO_REFRESH = /\/api\/v1\/auth\/(login|register|token|refresh|logout)$/;

function randomUuid(): string {
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (c?.randomUUID) return c.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    return (ch === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "").replace(/\/api\/v1$/, "");
}

export interface ApiClient {
  /** The typed openapi-fetch client: `api.client.GET("/api/v1/cases/{case_id}", { params: { path: { case_id } } })`. */
  client: Client<paths>;
  /** Signs in and stores the token pair. */
  signIn(identifier: string, password: string): Promise<void>;
  /** Revokes the session (and, when given, the push device) and clears the stored tokens. Always clears locally, even when the request fails. */
  signOut(expoPushToken?: string): Promise<void>;
}

export function createApiClient(opts: ApiClientOptions): ApiClient {
  const origin = normalizeBaseUrl(opts.baseUrl);
  const doFetch = (...a: Parameters<typeof fetch>) => (opts.fetch ?? fetch)(...a);
  const uuid = opts.uuid ?? randomUuid;
  let refreshing: Promise<TokenPair | null> | null = null;

  function send(req: Request, access: string | null, idempotencyKey: string | null): Promise<Response> {
    const headers = new Headers(req.headers);
    for (const [k, v] of Object.entries(opts.headers ?? {})) if (!headers.has(k)) headers.set(k, v);
    if (access) headers.set("Authorization", `Bearer ${access}`);
    if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);
    return doFetch(new Request(req, { headers }));
  }

  /** One refresh at a time: concurrent 401s share the same request (the server rotates refresh tokens, a second use would revoke the session). */
  function refreshOnce(): Promise<TokenPair | null> {
    refreshing ??= (async () => {
      const current = await opts.tokens.get();
      if (!current?.refresh_token) return null;
      try {
        const res = await doFetch(new Request(`${origin}/api/v1/auth/refresh`, { method: "POST", headers: { "content-type": "application/json" },
                                                body: JSON.stringify({ refresh_token: current.refresh_token }) }));
        if (!res.ok) {
          await opts.tokens.clear();
          return null;
        }
        const next = (await res.json()) as TokenPair;
        await opts.tokens.set(next);
        return next;
      } catch {
        return null;                                   // network trouble is not a reason to forget the session
      }
    })().finally(() => { refreshing = null; });
    return refreshing;
  }

  async function authedFetch(input: Request): Promise<Response> {
    const pristine = input.clone();                   // a Request body can be read once: keep a copy for the retry
    const key = MUTATING.has(input.method) && !input.headers.has("Idempotency-Key") ? uuid() : null;
    const tokens = await opts.tokens.get();
    const first = await send(input, tokens?.access_token ?? null, key);
    if (first.status !== 401 || NO_REFRESH.test(new URL(input.url).pathname)) return first;
    const next = await refreshOnce();
    if (!next) {
      opts.onAuthLost?.();
      return first;
    }
    return send(pristine, next.access_token, key);    // the SAME Idempotency-Key: a retried mutation must not run twice
  }

  const client = createClient<paths>({ baseUrl: origin, fetch: authedFetch as typeof fetch });

  return {
    client,
    async signIn(identifier, password) {
      const { data, error, response } = await client.POST("/api/v1/auth/login", { body: { identifier, password } });
      if (!data) throw ApiError.from(response, error);
      await opts.tokens.set({ access_token: data.access_token, refresh_token: data.refresh_token });
    },
    async signOut(expoPushToken) {
      const tokens = await opts.tokens.get();
      try {
        if (tokens?.refresh_token) {
          await client.POST("/api/v1/auth/logout", { body: { refresh_token: tokens.refresh_token, ...(expoPushToken ? { expo_push_token: expoPushToken } : {}) } });
        }
      } finally {
        await opts.tokens.clear();
      }
    },
  };
}

/** Turns an openapi-fetch result into the data or a thrown `ApiError` (envelope `code`, `message`, `details`, `request_id`). */
export async function unwrap<T>(result: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await result;
  if (!response.ok) throw ApiError.from(response, error);
  return data as T;
}
