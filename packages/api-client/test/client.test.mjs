// Runs against dist/ (npm test builds first). A scripted fetch stands in for the API: no network, no server.
import assert from "node:assert/strict";
import { test } from "node:test";
import { ApiError, createApiClient, fetchAll, normalizeBaseUrl, pages, unwrap } from "../dist/index.js";

function memoryTokens(initial) {
  let t = initial;
  return { get: () => t, set: (n) => { t = n; }, clear: () => { t = null; }, peek: () => t };
}
function scripted(handler) {
  const calls = [];
  const fn = async (req) => {
    const body = req.method === "GET" || req.method === "HEAD" ? null : await req.clone().text();
    const call = { url: new URL(req.url), method: req.method, headers: Object.fromEntries(req.headers), body };
    calls.push(call);
    return handler(call, calls.length);
  };
  fn.calls = calls;
  return fn;
}
const json = (status, body, headers = {}) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
const PAIR = { access_token: "A1", refresh_token: "R1" };

test("base url: the /api/v1 suffix and trailing slashes are stripped (generated paths already carry the prefix)", () => {
  assert.equal(normalizeBaseUrl("http://x.test/api/v1/"), "http://x.test");
  assert.equal(normalizeBaseUrl("http://x.test"), "http://x.test");
});

test("the bearer token is sent and a mutation gets an Idempotency-Key, a read does not", async () => {
  const f = scripted(() => json(200, { items: [], next_cursor: null }));
  const api = createApiClient({ baseUrl: "http://x.test/api/v1", tokens: memoryTokens(PAIR), fetch: f, uuid: () => "key-1" });
  await api.client.GET("/api/v1/cases");
  await api.client.POST("/api/v1/cases/{case_id}/reject", { params: { path: { case_id: "c1" } }, body: { reason: "duplicate of another case" } });
  assert.equal(f.calls[0].url.href, "http://x.test/api/v1/cases");
  assert.equal(f.calls[0].headers.authorization, "Bearer A1");
  assert.equal(f.calls[0].headers["idempotency-key"], undefined);
  assert.equal(f.calls[1].headers["idempotency-key"], "key-1");
});

test("a 401 refreshes ONCE and retries with the new token and the SAME idempotency key and body", async () => {
  const tokens = memoryTokens(PAIR);
  const f = scripted((c) => {
    if (c.url.pathname.endsWith("/auth/refresh")) return json(200, { access_token: "A2", refresh_token: "R2" });
    return c.headers.authorization === "Bearer A2" ? json(200, { ok: true }) : json(401, { error: { code: "AUTH_INVALID_TOKEN", message: "expired" } });
  });
  const api = createApiClient({ baseUrl: "http://x.test", tokens, fetch: f, uuid: () => "key-9" });
  const res = await api.client.POST("/api/v1/cases/{case_id}/reject", { params: { path: { case_id: "c1" } }, body: { reason: "same body twice" } });
  assert.equal(res.response.status, 200);
  const posts = f.calls.filter((c) => c.url.pathname.endsWith("/reject"));
  assert.equal(posts.length, 2);
  assert.equal(posts[0].headers["idempotency-key"], "key-9");
  assert.equal(posts[1].headers["idempotency-key"], "key-9");
  assert.equal(posts[1].body, posts[0].body);
  assert.deepEqual(tokens.peek(), { access_token: "A2", refresh_token: "R2" });
  assert.equal(f.calls.filter((c) => c.url.pathname.endsWith("/auth/refresh")).length, 1);
});

test("concurrent 401s share one refresh request", async () => {
  const tokens = memoryTokens(PAIR);
  const f = scripted(async (c) => {
    if (c.url.pathname.endsWith("/auth/refresh")) { await new Promise((r) => setTimeout(r, 20)); return json(200, { access_token: "A2", refresh_token: "R2" }); }
    return c.headers.authorization === "Bearer A2" ? json(200, { items: [] }) : json(401, { error: { code: "AUTH_INVALID_TOKEN", message: "expired" } });
  });
  const api = createApiClient({ baseUrl: "http://x.test", tokens, fetch: f });
  const out = await Promise.all([api.client.GET("/api/v1/cases"), api.client.GET("/api/v1/work-orders"), api.client.GET("/api/v1/me/notifications")]);
  assert.deepEqual(out.map((o) => o.response.status), [200, 200, 200]);
  assert.equal(f.calls.filter((c) => c.url.pathname.endsWith("/auth/refresh")).length, 1);
});

test("a failed refresh clears the tokens, calls onAuthLost and returns the original 401", async () => {
  const tokens = memoryTokens(PAIR);
  let lost = 0;
  const f = scripted((c) => c.url.pathname.endsWith("/auth/refresh") ? json(401, { error: { code: "AUTH_INVALID_TOKEN", message: "used" } }) : json(401, { error: { code: "AUTH_INVALID_TOKEN", message: "expired" } }));
  const api = createApiClient({ baseUrl: "http://x.test", tokens, fetch: f, onAuthLost: () => { lost++; } });
  const res = await api.client.GET("/api/v1/cases");
  assert.equal(res.response.status, 401);
  assert.equal(tokens.peek(), null);
  assert.equal(lost, 1);
});

test("sign-in 401s are never refreshed (wrong password is not an expired session)", async () => {
  const f = scripted(() => json(401, { error: { code: "AUTH_INVALID_CREDENTIALS", message: "Incorrect identifier or password." } }));
  const api = createApiClient({ baseUrl: "http://x.test", tokens: memoryTokens(PAIR), fetch: f });
  await assert.rejects(() => api.signIn("a@b.test", "nope"), (e) => e instanceof ApiError && e.code === "AUTH_INVALID_CREDENTIALS" && e.status === 401);
  assert.equal(f.calls.length, 1);
});

test("signIn stores the pair; signOut sends the optional push token and clears the tokens even when the request fails", async () => {
  const tokens = memoryTokens(null);
  const f = scripted((c) => c.url.pathname.endsWith("/auth/login") ? json(200, { user: { id: "u", name: "n", role: "CITIZEN", must_change_password: false }, access_token: "A1", refresh_token: "R1", token_type: "bearer" }) : json(500, {}));
  const api = createApiClient({ baseUrl: "http://x.test", tokens, fetch: f });
  await api.signIn("a@b.test", "pw");
  assert.deepEqual(tokens.peek(), PAIR);
  await api.signOut("ExponentPushToken[abc]");
  const logout = f.calls.find((c) => c.url.pathname.endsWith("/auth/logout"));
  assert.deepEqual(JSON.parse(logout.body), { refresh_token: "R1", expo_push_token: "ExponentPushToken[abc]" });
  assert.equal(tokens.peek(), null);
});

test("unwrap throws ApiError with code, message, details, request id and Retry-After", async () => {
  const f = scripted(() => json(429, { error: { code: "RATE_LIMITED", message: "Too many requests.", details: { retry_after_seconds: 7, rule: "ai" }, request_id: "req-1" } }, { "retry-after": "7" }));
  const api = createApiClient({ baseUrl: "http://x.test", tokens: memoryTokens(PAIR), fetch: f });
  await assert.rejects(() => unwrap(api.client.GET("/api/v1/cases")), (e) =>
    e instanceof ApiError && e.status === 429 && e.code === "RATE_LIMITED" && e.requestId === "req-1" && e.retryAfterSeconds === 7 && e.details.rule === "ai");
});

test("ApiError copes with bodies that are not the envelope", () => {
  const e = ApiError.from(new Response("boom", { status: 502 }), "boom");
  assert.equal(e.code, "HTTP_502");
  assert.equal(e.status, 502);
});

test("pages follows next_cursor, stops at the end and guards against a repeated cursor", async () => {
  const data = { undefined: { items: [1, 2], next_cursor: "b" }, b: { items: [3], next_cursor: "c" }, c: { items: [4], next_cursor: null } };
  assert.deepEqual(await fetchAll(async (cursor) => data[cursor]), [1, 2, 3, 4]);
  let n = 0;
  for await (const _ of pages(async () => ({ items: [1], next_cursor: "same" }))) n++;
  assert.equal(n, 2);                                          // first page, then the repeated cursor ends it
});
