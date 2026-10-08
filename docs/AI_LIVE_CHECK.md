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

## Still to do for WP1

Run the flash model on the real photo and the six text and audio cases once the quota is available again (`python scripts/dev/ai_live_pass.py --photo ... --audio ...`), and append the results here.
