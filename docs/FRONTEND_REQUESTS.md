# Frontend requests to the backend

The **frontend session appends** an entry here whenever an app needs something the backend does not serve yet (endpoint missing, field missing, shape mismatch, error code needed, demo data, CORS origin, ...).
The **backend session reads this file at the start of every wave and after every work package** (plan WP10), answers each entry with `DONE <commit>`, `WON'T <reason>` or `QUESTION`, and does the work.
Contract changes the backend makes are recorded in `docs/V1_CHANGE_LOG.md`; the page-by-page reference of what is already served is `docs/FRONTEND_API_NEEDS.md`.

Rules: one entry per need; keep old entries (do not delete answered ones); contract changes are additive (a removed or renamed field needs a change-log entry and an entry here).

## Entry template

```
### YYYY-MM-DD · <app> · <page or screen> · <REQUEST | NOTE | QUESTION>
**Needed:** what is missing or wrong, in one or two sentences.
**Example request:** `GET /api/v1/...` (or the call the app makes today)
**Example response (wanted):** a small JSON sample of the shape the page needs
**Seen instead:** what the backend returns today (status, body, error code), if known
**Answer (backend):** DONE <commit> | WON'T <reason> | QUESTION <what we need to know>
```

## Entries

### 2026-10-08 · citizen-expo · report flow (voice note) · NOTE
**Needed (frontend):** handle a voice note that has no transcript. `POST /cases/intake/analyze` with only audio evidence, when no speech-to-text is available (no Groq key, quota spent, outage), now answers `200` (it used to be a `422`) with an EMPTY draft: `proposal.title == ""`, `proposal.description == ""`, `confidence 0.0`, `ai_metadata.source == "none"`, and a warning string that starts with `TRANSCRIPTION_UNAVAILABLE:` (plus `AUDIO_NOT_TRANSCRIBED: ...` per clip). The app should show the draft form empty with the message "We could not turn your voice note into text. Please type a short description." and still attach the audio as evidence of the report.
**Example response (shape):** `{"proposal": {"title": "", "description": "", "category": "other", "subcategory": "unclassified", "severity": "LOW", "language": "mr", "evidence_refs": ["<audio id>"]}, "confidence": 0.0, "warnings": ["AUDIO_NOT_TRANSCRIBED: ...", "TRANSCRIPTION_UNAVAILABLE: the voice note could not be turned into text; please type a short description of the problem"], "requires_confirmation": true, "ai_metadata": {"source": "none", "degraded": true}}`
**Also:** send `language_hint` (`en`, `hi` or `mr`: the language the citizen chose for this report) with every `intake/analyze` call that has audio. It is passed to the speech-to-text model, which obeys it (a wrong hint changes the text: `en` on a Hindi voice note comes back transliterated into Latin script). Without it the backend uses the profile's `preferred_language` only when that is Hindi or Marathi.
**Answer (backend):** DONE (this entry is the backend telling the apps; no reply needed)

### 2026-10-08 · citizen-expo, field-worker-expo · push notifications · NOTE
**Needed (frontend):** the backend now sends Expo push messages. Register the device token after every sign-in with `POST /api/v1/me/devices` (see `docs/FRONTEND_API_NEEDS.md`), call `DELETE /api/v1/me/devices/{id}` BEFORE signing out (logout does not revoke devices; on a shared phone the previous user would otherwise keep receiving pushes until the next user signs in and re-registers), and remember that **remote push does not work in Expo Go**: use a development build (`eas build --profile development`) to test it.
**Answer (backend):** DONE (note for the apps)

### 2026-10-09 · all apps · API client · NOTE
**Needed (frontend):** a typed client now exists: `packages/api-client` (`@civicconnect/api-client`), types generated from `backend/openapi.json`, with bearer token, one single-flight 401 refresh and retry (same `Idempotency-Key`), `Idempotency-Key` on mutations, an `ApiError` carrying the error code / request id / `Retry-After`, and cursor-pagination helpers. It is consumed from source like `@civicconnect/ui`; usage and the TanStack Query recipes are in `packages/api-client/README.md`. Using it is optional and the apps' own `fetch` code keeps working. Not verified: inside a real Expo build or the Vite apps (only type-checked and run against a scripted `fetch` in Node). After any API change the backend runs `scripts/dev/gen_api_client.ps1`; a backend test fails when the client is stale.
**Also:** `POST /auth/logout` no longer answers `422` for a malformed `expo_push_token`: it logs out and revokes nothing (only a value over 2000 characters is refused).
**Answer (backend):** DONE (note for the apps)
