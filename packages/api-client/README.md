# @civicconnect/api-client

Typed client for the CivicConnect v2 API: types **generated** from `backend/openapi.json` (openapi-typescript 7.13.0) and a thin wrapper over `openapi-fetch` 0.17.0. It uses only `fetch`, `Request`, `Headers` and `Response`, so it runs in browsers, Expo / React Native and Node 18+. Nothing here is edited by hand except `src/client.ts`, `errors.ts`, `pagination.ts` and `index.ts`; `src/schema.d.ts` and `src/schema.sha256` are generated.

## Install and regenerate

The package is consumed from source (`"main": "./src/index.ts"`, like `@civicconnect/ui`): add `"@civicconnect/api-client": "file:../../packages/api-client"` to an app's `package.json`, or import it through a path alias. After any backend API change run, from the repo root:

```powershell
.\scripts\dev\gen_api_client.ps1     # regenerates openapi.json, schema.d.ts, schema.sha256, then typecheck + tests
```

Commit the three generated files together. A backend test (`backend/tests/test_api_client_generated.py`) fails when `openapi.json` changed and the client was not regenerated. In the package: `npm run typecheck`, `npm run build`, `npm test`.

## Use

```ts
import { createApiClient, unwrap, ApiError, pages } from "@civicconnect/api-client";

const api = createApiClient({
  baseUrl: process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000",   // the origin; a trailing /api/v1 is accepted and stripped
  tokens: { get: () => store.read(), set: (t) => store.write(t), clear: () => store.erase() },  // SecureStore in Expo, localStorage in a browser
  onAuthLost: () => router.replace("/sign-in"),
});

await api.signIn("citizen001@demo.civicconnect.test", password);
const me = await unwrap(api.client.GET("/api/v1/auth/me"));
const created = await unwrap(api.client.POST("/api/v1/cases", { body: { /* typed */ } }));   // an Idempotency-Key is added for you
await api.signOut(expoPushToken);                                                             // revokes the session and that push device
```

Paths are the generated ones, so they start with `/api/v1`. What the wrapper does for you:

- **Bearer token** from your `TokenStore` on every request.
- **401 -> one refresh -> one retry.** Concurrent 401s share a single refresh request (the server rotates refresh tokens). The retry reuses the **same** `Idempotency-Key` and body. Sign-in, register, token, refresh and logout are never refreshed. If the refresh fails the tokens are cleared and `onAuthLost` is called.
- **`Idempotency-Key`** on every POST, PUT, PATCH and DELETE (a UUID; supply `uuid` where `crypto.randomUUID` is missing, a fallback exists).
- **Errors:** `unwrap(...)` throws `ApiError` with `status`, `code` (`RATE_LIMITED`, `PASSWORD_CHANGE_REQUIRED`, `FLAG_ALREADY_EXISTS`, ...), `message`, `details`, `requestId` and `retryAfterSeconds` (from `Retry-After`). Without `unwrap`, openapi-fetch returns `{ data, error, response }` and does not throw.
- **Pagination:** list endpoints return `{ items, next_cursor }`: `for await (const page of pages((cursor) => unwrap(api.client.GET("/api/v1/cases", { params: { query: { cursor } } })))) { ... }` or `fetchAll(...)` for small collections.

## With TanStack Query

```ts
const cases = useQuery({ queryKey: ["cases", filter], queryFn: () => unwrap(api.client.GET("/api/v1/cases", { params: { query: filter } })) });
const reject = useMutation({ mutationFn: (v: { id: string; reason: string }) =>
  unwrap(api.client.POST("/api/v1/cases/{case_id}/reject", { params: { path: { case_id: v.id } }, body: { reason: v.reason } })) });
const infinite = useInfiniteQuery({ queryKey: ["cases"], initialPageParam: undefined as string | undefined,
  queryFn: ({ pageParam }) => unwrap(api.client.GET("/api/v1/cases", { params: { query: { cursor: pageParam } } })),
  getNextPageParam: (p) => p.next_cursor ?? undefined });
```

Do not retry `ApiError`s with `status` 4xx in the query client's `retry` option (the wrapper already handled the 401): `retry: (n, e) => !(e instanceof ApiError && e.status < 500) && n < 2`.

## Notes for the apps

- Remote push does not work in Expo Go (development build needed); register the device with `POST /api/v1/me/devices` after sign-in and pass the token to `signOut`.
- `403 PASSWORD_CHANGE_REQUIRED` means the account must call `POST /api/v1/auth/change-password` first; `must_change_password` is on the sign-in response.
- Not verified: use inside a real Expo build or the Vite apps (the package has been type-checked and exercised with a scripted `fetch` in Node only).
