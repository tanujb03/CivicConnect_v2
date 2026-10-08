# AI live check (WP1), 2026-10-08

First contact of the AI layer with real providers. **Synthetic content only** (made-up complaint sentences, public test photos and synthetic voice clips from `D:\civic-test-media`, the seeded demo city). **No accuracy claim of any kind** follows from this page: a handful of calls says only whether the plumbing works.

## Configuration used (names; chosen by Tanuj)

| Variable | Value | Provider |
|---|---|---|
| `AI_INTAKE_MODEL` | `gemini-3.5-flash` | Gemini (OpenAI-compatible endpoint); triage and resolution fall back to this id |
| `AI_COPILOT_MODEL` | `gemini-3.5-flash` | Gemini |
| `AI_ANALYTICS_MODEL` | `gemini-3.5-flash-lite` | Gemini |
| `AI_EMBEDDING_MODEL` + `AI_EMBEDDING_DIM` | `gemini-embedding-001`, `768` | Gemini |
| `AI_TRANSCRIPTION_MODEL` | `whisper-large-v3` | Groq (the default route for transcription) |

**No id was rejected by a provider.** Every id answered at least once (below). Ids come from `live_check --list-models` of this account on 2026-10-08.

## Direct provider checks (`python -m backend.ai_gateway.providers.live_check`)

| Check | Result | Latency | Notes |
|---|---|---|---|
| Structured output, Hindi / Marathi / Hinglish text (`gemini-3.5-flash`) | PASS, 3 of 3 | 2.6 to 6.5 s | schema-valid JSON each time; the language label varies in casing (`Hindi`, `marathi`, `Hinglish`) |
| Vision plumbing (tiny gray image) | PASS | 5.9 s | answered `category: other`, which proves the payload shape works but says nothing about photos |
| Tool calling | PASS | 5.7 s | called `search_cases` |
| Embeddings (`gemini-embedding-001`, 768) | PASS, repeatedly | 4 to 6 s | length is exactly 768; cosine en~hi 0.91 and en~unrelated 0.69 (both high: see "Observations") |
| Transcription `whisper-large-v3` (Groq), Hindi clip | PASS | 0.5 s | text read as a plausible Hindi sentence, language `Hindi` |
| Transcription, Marathi clip | PASS | 0.5 s | Marathi text, but the reported language is `Hindi` |
| Transcription, English clip | PASS | 0.3 s | exact English sentence, language `English` |

Later in the day `gemini-3.5-flash` began answering **HTTP 429** to every call: *"You exceeded your current quota, please check your plan and billing details"* (free-tier quota; whether it is per minute or per day is not stated). `gemini-embedding-001` and Groq were not affected. The retry bursts of my own repeated runs probably contributed. **A real photo through `gemini-3.5-flash` was therefore never analysed**, and neither was the flash model on real endpoint prompts: those two items are still **unverified**.

## The endpoints (`scripts/dev/ai_live_pass.py` against the running API, dev database, 560 demo cases)

Run 1, keys set, `gemini-3.5-flash` quota-blocked (the degraded path under a real provider failure):

| Call | HTTP | Latency | Schema valid | Result |
|---|---|---|---|---|
| `POST /cases/intake/analyze` text en / hi / mr | 200 | 12.6 to 14.6 s | yes | `PROVIDER_UNAVAILABLE`, `NO_AI_AVAILABLE`, `LOW_CONFIDENCE`; confidence 0.0, category `other`, `requires_confirmation: true` |
| intake with a photo | 200 | 13.1 s | yes | same plus `IMAGE_NOT_ANALYZED` |
| intake with audio hi / mr / en | 200 | 12.8 to 13.0 s | yes | proposal `language` came back `hi` / `mr` / `en`, so transcription ran on Groq; the category stayed `other` because the text model was blocked (the transcript text itself was not inspected) |
| `POST /cases/{id}/fusion/analyze` | 200 | 91 ms | yes | rules only, `FUSION_UNCALIBRATED_PRIOR` |
| `POST /cases/{id}/triage/analyze` | 200 | 14.5 s | yes | rules only, confidence 0.5, `PROVIDER_UNAVAILABLE` |
| `POST /copilot/query` | 200 | 14.6 s | yes | `COPILOT_UNAVAILABLE` |

Run 2, provider keys unset (API started without them):

| Call | HTTP | Latency | Result |
|---|---|---|---|
| intake text en / hi / mr, photo | 200 | 11 to 81 ms | `PROVIDER_NOT_CONFIGURED` plus `NO_AI_AVAILABLE`; schema valid |
| intake with **only** an audio clip | **422** `VALIDATION_ERROR` "The request could not be analysed." | 12 ms | no text and nothing to transcribe with: the request is refused instead of degrading with an `AUDIO_NOT_TRANSCRIBED` warning |
| fusion / triage / copilot | 200 | 24 to 47 ms | `RULES_ONLY`, `COPILOT_UNAVAILABLE`; schema valid |

So the degraded modes work and are visible in the response. Two real weaknesses showed up:
1. **A blocked provider made each request take 12 to 15 s** before degrading (the free-tier spacing times the retries). Fixed in this work package: after an HTTP 429 a model is not called again for 60 s (per model, so the embedding model keeps working), see `test_provider_cooldown.py`. The fix was **not re-run live** because the quota is still exhausted.
2. Audio-only intake without any transcription provider returns 422 (above). Not changed: it needs a decision on the contract (a 200 with an empty proposal and a warning would be friendlier for the citizen app, which should in any case send the text it has).

## Fixes made to the adapter in this package (each with a test using recorded fake responses)

- `AI_EMBEDDING_DIM`: the request asks the provider for that many dimensions, the length of every returned vector is checked (a different length is `ProviderResponseInvalid`, never stored), and vectors are L2-normalised (reduced-dimension vectors of this model are not unit length). `test_embedding_dimension.py`.
- Provider error messages now carry the provider's own explanation (at most 200 characters, the key scrubbed), so a quota 429 can be told from a rejected model id or a bad request. `test_embedding_dimension.py`.
- Per-model cooldown after a 429 (above). `test_provider_cooldown.py`.
- Empty `AI_*_MODEL` variables with keys present build no provider and the endpoints degrade cleanly with no network call. `test_ai_unconfigured_models.py`.

## Observations (not conclusions)

- Cosine 0.69 between unrelated English sentences means the duplicate threshold of the fusion step must be calibrated on these vectors before it is trusted (WP7 measures it on the demo city).
- Groq reported `Hindi` for a Marathi clip. If the language label matters downstream, derive it from the script or ask the citizen, not from this field.
- `gemini-3.5-flash` free-tier quota is small enough that a few live-check runs in a row exhausted it. The rate limiter (`RATE_LIMIT_AI_PER_HOUR=30` per user) protects against one user; it does not protect the shared quota. Consider `gemini-3.5-flash-lite` for `AI_INTAKE_MODEL` if quota is the constraint (not changed: the ids are Tanuj's choice).

## Quota notes

**Limits as shown by Google AI Studio's rate-limit page and the Groq console, read by Tanuj on 2026-10-08** (these change; they are data in `backend/ai_gateway/providers/model_limits.json`, overridable with `AI_MODEL_LIMITS`, not code):

| Model | Requests/min | Tokens/min | Requests/day |
|---|---|---|---|
| `gemini-3.5-flash` | 5 | 250K | **20** |
| `gemini-3.5-flash-lite` | 15 | 250K | 500 |
| `gemini-embedding-001` | 100 | 30K | 1000 |
| Groq `whisper-large-v3` | 20 | not stated (2K requests/day) | 2000 |

What we learned:
- **The earlier `gemini-3.5-flash` HTTP 429 ("You exceeded your current quota") was the DAILY cap**: the account had made 21 requests against a limit of 20. It was not a per-minute limit and it was not a rejected model id. My own repeated live-check runs spent most of the 20. Whether the retried and rejected attempts also counted against Google's counter is not known; the adapter now avoids sending them at all while a model is cooling down or its budget is spent.
- The embedding model has its own quota: it kept answering while the flash model was exhausted.
- `gemini-3.5-flash` has 5 requests/min and 20/day: that is about one rehearsal of the whole endpoint set, so it is **not** a development model.
- Where the reset happens: Gemini API daily quotas reset at midnight **Pacific time**, which is 07:00 UTC (12:30 IST) while daylight saving time is in effect (until 1 November 2026). **The actual reset has not been observed yet**; when a 429 for the day limit ends, record the time here. The provider adapter now computes the next reset for its cooldown.
- The Gemini 429 body can name the limit (`QuotaFailure.quotaId`, `quotaMetric`, `RetryInfo.retryDelay`). The adapter now surfaces those fields in the error and in the log, with the model and the time, and applies a long cooldown when the quota id says "per day"; no real 429 body with those fields has been recorded yet (only the plain message above), so the parsing is tested against recorded **fake** bodies in the shape Google documents.

What the gateway now does about it (all configurable, see `.env.example`):
- **Per-model budgets** (requests/min, requests/day, tokens/min for embeddings): a full minute budget waits at most `AI_BUDGET_MAX_WAIT_S` (8 s); a spent daily budget sends nothing and the call degrades; the daily counter is kept in Redis (shared by every process), with an in-process fallback; "budget spent" is logged once per model per day.
- **Routes:** no default selects any model; the text tasks use whatever `AI_INTAKE_MODEL`, `AI_ANALYTICS_MODEL` and `AI_COPILOT_MODEL` name (dev default: `gemini-3.5-flash-lite`). `gemini-3.5-flash` is reachable only by putting its id in those variables yourself. Optional `AI_FALLBACK_TEXT_MODEL` names a Groq text model used once when the Gemini call cannot be served (never for images).
- **Optional response cache** (`AI_CACHE_ENABLED`, off by default, 24 h): repeated identical calls cost no quota. **It stores the model's answers to citizen text, images and audio in Redis for the TTL: keep it off for real data.**

**Demo-day note:** rehearse on `gemini-3.5-flash-lite` (500 requests/day, 15/min). Spend `gemini-3.5-flash` calls only on the final photo run and the final Marathi run (at most 5 requests per minute, 20 per day, and wait at least 13 s between calls). Turn the response cache on for rehearsals on the synthetic demo city so reruns are free.

## Endpoint pass on `gemini-3.5-flash-lite` (2026-10-08, after the intake model id was corrected)

One run of `scripts/dev/ai_live_pass.py` against the real API (dev database, 560 demo cases, current code with per-model budgets), 7 s between calls, no reruns. Configured: intake, triage, analytics, copilot = `gemini-3.5-flash-lite`; embedding `gemini-embedding-001` (768); transcription `whisper-large-v3`. **No 429, no rejected id, no flash call.** Synthetic sentences, the public test photo `Pot_holes.jpg` and the synthetic voice clips only.

| Call | HTTP | Latency | Schema valid | Confidence | Result |
|---|---|---|---|---|---|
| `intake/analyze` text en | 200 | 1.5 s | yes | 0.95 | roads / pothole / HIGH, language en, no warnings |
| text hi | 200 | **29.3 s** | yes | 0.95 | roads / pothole / HIGH, language hi |
| text mr | 200 | 5.4 s | yes | 0.95 | roads / pothole / HIGH, language mr |
| photo + the text "Road damage here" | 200 | 3.2 s | yes | 0.95 | roads / pothole / MEDIUM |
| audio hi / mr / en (language hint sent) | 200 | 2.9 / 3.0 / 1.8 s | yes | 0.95 / 0.95 / 0.99 | roads / pothole / MEDIUM, language hi / mr / en |
| `triage/analyze` on a demo case | 200 | 3.3 s | yes | 0.85 | MEDIUM severity, HIGH priority, drainage_sewerage, source `provider+rules` |
| `copilot/query` | 200 | 4.4 s | yes | none | 196-character answer, 1 tool call |
| `fusion/analyze` | 200 | 52 ms | yes | none | NO_MATCH, rules only, `FUSION_UNCALIBRATED_PRIOR` |

What this does and does not show:
- All nine AI calls were answered by the provider (`source: provider`), schema-valid, with no warnings. This is the first real endpoint pass; it proves the plumbing, not quality. All seven intake answers say roads / pothole, which is the right shape for these sentences; **no accuracy claim** is made from nine synthetic calls, and the severity differs between text (HIGH) and audio/photo (MEDIUM) runs without our knowing which is better.
- The photo call carried the words "Road damage here", so it **cannot show that the model used the image**. A photo-only call and a comparison against flash are still open.
- **One latency outlier of 29 s** (the Hindi text call) with no warning in the API log; the cause is not known (provider latency is the likely one). Not reproduced.
- **Timing is now logged so the next outlier can be diagnosed** (the cause of the 29 s is still not found). Every provider call writes one INFO line, `ai provider call: task= backend= model= attempts= provider_ms= waited_ms= total_ms= outcome=`: `provider_ms` is the time inside the HTTP calls, `waited_ms` is everything else (throttle, budget waits, retry sleeps), so a slow answer shows whether the provider was slow or we were waiting. Each intake / triage / copilot / analytics-explain response carries the sum in `ai_metadata.timing` (`provider_ms`, `waited_ms`, `total_ms`, `provider_calls`; the localisation call counts in it). One provider call now has an overall deadline of `AI_PROVIDER_TIMEOUT_S` (default 20 s, retries and waits included); on a timeout the Groq text fallback answers with its own fresh deadline, otherwise the rules-based answer is returned with the usual `PROVIDER_UNAVAILABLE` warning. `test_ai_timeouts.py`; not run against the live API.
- **Quota cost:** the nine endpoint calls used **14** `gemini-3.5-flash-lite` requests (Redis day counter 14 of 500) and 3 Groq Whisper requests (3 of 2000). The difference is the extra localisation call that non-English answers make (title and summary in the citizen's language): a Hindi or Marathi intake costs two Gemini requests, an English one costs one. Budget about **2 requests per non-English intake** when planning a demo.
- The speech-to-text language label was measured directly (not through this pass): an explicit `mr` hint labels the Marathi clip `Marathi`, no hint labels it `Hindi`. This pass always sent a hint, so it does not show what an app that sends none gets.

## Groq fallback text model comparison (2026-10-08; the owner decides)

`scripts/dev/compare_fallback_models.py`, one real run: the production intake pipeline (`AIService.analyze_intake`) over the production Groq provider, retries and per-model budgets off, no images, the same 6 rows for both models (2 Hindi, 2 Marathi, 2 Hinglish; fixed rule; ids are a content hash because the gold file has no id column). The gold file is **LLM-written (`llm_authored_claude`)**, not human gold, and its Hindi and Marathi rows still await native-speaker review. **6 rows per model say nothing about accuracy.** 12 calls, no 429, no retry, no rejected model id.

| | `openai/gpt-oss-120b` | `qwen/qwen3.8-27b` |
|---|---|---|
| Schema-valid answers | 6 / 6 | 6 / 6 |
| Category agrees with gold | 6 / 6 | 6 / 6 |
| Subcategory agrees with gold | 5 / 6 | 6 / 6 |
| Median provider time | 1485 ms | 552 ms |
| Average tokens per call (prompt + completion) | 1379 (917 + 462) | 645 (459 + 186) |
| Largest single call | 1482 tokens | 690 tokens |
| Calls per minute under the 8K tokens/min limit (floor(8000 / average)) | **5** | **12** |
| Structured mode | `json_schema`, never rejected | `json_schema`, never rejected |

Notes: the one miss was a Hindi row labelled roads/pothole that `gpt-oss-120b` answered roads/road_cave_in (category right, subcategory wrong). The 7,000-token pacing window made the script wait 50.8 s once, on `gpt-oss-120b`; `qwen` needed none. The 8K tokens/min figure is the owner's reading of the Groq console on 2026-10-08, not verified here, and none of the 12 calls reached it. Calls per minute ignore the 20 requests/minute cap. `qwen` reports about half the prompt tokens for the same prompt: Groq's usage reporting, not investigated. One run on one machine, no repeats.

What it suggests, without a claim: at the same 8K tokens/min a fallback on `qwen/qwen3.8-27b` could serve about twice as many calls per minute as `gpt-oss-120b` here, and was faster; the sample is far too small to say which is more accurate. A Hindi or Marathi intake makes two model calls (answer plus localization), which halves those figures.

## Still to do for WP1

- One comparison photo through `gemini-3.5-flash` (at most 5 flash calls in total, 13 s apart) only when Tanuj says the quota has rested; until then **no claim is made about any quality difference between flash and flash-lite**.
