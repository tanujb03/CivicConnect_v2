# CivicConnect v2 — Free-stack proposal (no paid service anywhere)

**Status: PROPOSAL, not a change to the locked design.** `CivicConnect_v2_V1_System_Design.md` stays frozen. Almost nothing below needs a design change: the design is already provider-agnostic (`AIProvider` abstraction §30, "S3-compatible" storage §31, "Vercel *or equivalent*" / "*equivalent* container host" §48, OTP transport unspecified §51A.2). The OpenAI favouring is confined to §30, §63.6, §63.7 and the reference list; everything else is open-source or already has a free option. Deviations that DO need a team nod are listed in §4.

**How this was researched.** Every section of the design doc and the four implementation plans was read for paid or account-gated elements. The sandbox could not open the vendors' own pages (`openai.com`, `ai.google.dev`, Bhashini docs … are blocked from here), so prices, quotas and limits below come from **third-party summaries found by web search (Oct 2026)** and are marked *(reported)*. Free tiers change often: **re-check each limit on the vendor's page when you create the account.** Nothing in this file was tested against a live paid or free service.

---

## 1. Where money was assumed — and what replaces it

| # | Element (design §) | Assumed | Free replacement | Verdict / catch |
|---|---|---|---|---|
| 1 | **LLM + vision + structured output** — intake, triage severity, AI-4 compare, AI-5 text, copilot (§11, §30, §63.6) | OpenAI API (prepaid) | **Google Gemini API free tier** via AI Studio key *(reported: Flash models free; ~10–15 requests/min; hundreds–~1,500 requests/day; no card)* · **Groq** free tier *(reported: 30 req/min, ~14.4k req/day; text and some vision models)* · **OpenRouter** `:free` models · **Cloudflare Workers AI** *(reported: 10,000 neurons/day, no card)* | **Implemented** (`backend/ai_gateway/providers/`): one OpenAI-compatible provider + per-task routing. **Privacy catch:** Gemini's free tier *may use your prompts to improve Google products* *(reported)* → send only synthetic / demo data, never real citizen reports. **Rate-limit catch:** 10–15 req/min is fine for a demo, not for load; a built-in throttle spaces calls. |
| 2 | **Embeddings** — semantic duplicates, search (§30, §37, §63.7) | `text-embedding-3-small` | **Local multilingual encoder** (multilingual-e5-small / BGE-M3 / LaBSE as ONNX on CPU — free, offline, private, cross-lingual) · Gemini embeddings free tier *(reported)* · Cloudflare Workers AI embeddings | Best = **local** (also fixes the weak lexical duplicate signal across Hindi/Marathi/English). Planned as part of the text-model notebook. Provider route already supports Gemini embeddings. |
| 3 | **Speech-to-text** — voice reports in Marathi/Hindi/English (§14, C05) | OpenAI transcription | **Browser Web Speech API** (Chrome/Android: `hi-IN`, `mr-IN`, `en-IN` *(reported)*; free; audio goes to Google's servers; no iOS Safari/Firefox) · **Groq Whisper** *(reported: whisper-large-v3 / -turbo, 2,000 req/day, ~8 h audio/day)* · **Bhashini ASR** (below) · **AI4Bharat IndicConformer** (MIT, self-host) | Use Web Speech for live dictation (zero backend), Groq Whisper for uploaded clips (**implemented**: transcription route), Bhashini as the Indic-quality option. Marathi accuracy of generic Whisper is weaker than Bhashini/IndicConformer: test it. |
| 4 | **Translation / "department language rendering" / "citizen-language response"** (§14) | an LLM | **Bhashini NMT** (govt DPI, 22 languages, *free for non-commercial*) · **IndicTrans2** (AI4Bharat, open) · the LLM route | Bhashini needs a free registration (ULCA portal → profile → `userID`, `ulcaApiKey`, inference key) *(reported)*. Flow is two calls (pipeline config → compute); audio must be 16 kHz wav/flac. **Not implemented here** (docs unreachable from the sandbox; I will not ship an unverifiable adapter) — the LLM route covers translation meanwhile. |
| 5 | **Image understanding** (AI-1 photos, AI-4) | OpenAI vision | **Our own YOLO road-damage detector** (notebook 06, ONNX, CPU, free, offline — already built) + Gemini vision for everything else | Local model first, cloud vision second (merge policy already implemented). |
| 6 | **Object storage** (§31, §44) | Cloudflare R2 or AWS S3 | **MinIO** (S3-compatible, Docker) for dev/demo · **Supabase Storage** (1 GB free) · **Cloudflare R2** (10 GB/mo, zero egress *(reported)*; may ask for a card) · Backblaze B2 free 10 GB | No design change (it says "S3-compatible"). Use MinIO locally; R2 only if you accept the card prompt. |
| 7 | **Managed PostgreSQL 18 + PostGIS + pgvector** (§28, §48) | paid managed DB | **Docker `postgis` + `pgvector` on a laptop/VM (free, no pause)** · **Supabase free** (PostGIS + pgvector both available, 500 MB, **auto-pauses after 1 week idle** *(reported)*) · Neon free | Postgres 18 is not required by any feature; 15–17 works. Supabase's pause is the catch — wake it before demos. |
| 8 | **Managed Redis 8 / Streams** (§29, §48) | paid Redis | **Redis in Docker** (free) · Redis Cloud free (30 MB) · *Upstash free (500k commands/month) is a trap for workers: polling consumer groups burns the quota in days* *(reported)* | For a hosted free setup consider a **Postgres job table** (`SELECT … FOR UPDATE SKIP LOCKED`) or in-process background tasks instead of Redis — one less service. The backend already degrades when Redis is down (events fire-and-forget). |
| 9 | **Frontend hosting** — 3 apps (§48) | Vercel | **Cloudflare Pages** (unlimited sites, free, commercial OK) · **Vercel Hobby** (free, non-commercial) · Netlify · GitHub Pages | Pages gives HTTPS (required for PWA / service worker / web push). |
| 10 | **Backend hosting** (§48: DigitalOcean/Railway/Render/AWS) | paid container host | **Best for a hackathon: run the whole stack on one machine with Docker Compose and publish it with a free Cloudflare Tunnel** · Render free web service *(reported: 512 MB, sleeps after 15 min, bandwidth cut to 5 GB)* · Oracle Cloud Always Free VM *(reported: now ~2 OCPU / 12 GB; card at signup; idle instances reclaimed)* · **GitHub Student Pack: Azure $100 (no card), DigitalOcean $200 credit** *(reported)* | A laptop + tunnel avoids every cold-start/pause/quotas risk on demo day. Use Student Pack credits as the "real deployment" if wanted. |
| 11 | **Domains** (`citizen.civicconnect…` §48) | purchased domain | `*.pages.dev`, `*.vercel.app`, `*.trycloudflare.com`; free `.me` via Student Pack *(reported)* | — |
| 12 | **Map tiles** (§26 MapLibre; tile source unspecified) | Mapbox/MapTiler tiers | **OpenFreeMap** vector tiles (no key, no limits *(reported)*) · OSM raster tiles (policy: light use + attribution; the imported SIH apps already use them) · Protomaps PMTiles self-hosted (also gives **offline** tiles) | MapLibre itself is free. Do not hammer `tile.openstreetmap.org` in a load test. |
| 13 | **Geocoding / reverse geocoding** (landmark, ward lookup §33) | Google/Mapbox | **Nominatim** (max 1 req/s, identify your app, cache) · **Photon** (Apache-2.0, public instance, be gentle) · ward polygons from OSM / DataMeet and **PostGIS `ST_Contains`** (no API) | GPS coordinates are primary; geocoding is optional. |
| 14 | **OTP login** (C02, §51A.2) | SMS gateway | **Email OTP / magic link** (Brevo or Resend free plans *(reported)*) · password login (exists) · Google Sign-In · Supabase Auth (50k MAU free) · **demo mode: fixed OTP**, clearly flagged | **SMS is the one thing that is never free in India** (Firebase phone auth needs a billing plan, ~₹6/OTP; MSG91/2Factor ~₹0.10–0.25/SMS + DLT registration *(reported)*). The API paths stay the same; only the transport changes. |
| 15 | **Notifications** (§53) | push/SMS vendors | **In-app (DB) + Web Push (VAPID, free)** · FCM (free) · email later | SMS "later" per the design — skip. |
| 16 | **Observability** (§47) | Datadog-class | **OpenTelemetry → local Jaeger / Grafana stack** (free) · Grafana Cloud free · Sentry free dev plan | For the hackathon: structured logs + `/health` + one OTel console exporter is enough. |
| 17 | **CI / tests** (§56) | — | **GitHub Actions** (free for public repos), Vitest, Playwright | Already free. |
| 18 | **Malware scan** (§44) | paid scanner | **ClamAV** (Docker) | Optional. |
| 19 | **Search** (§54) | search cluster | PostgreSQL FTS + pgvector (design already says no external cluster) | Already free. |
| 20 | **ML training / compute** (Tanuj plan) | paid GPU | **Kaggle** (free GPU, ~30 h/week *(reported)*), Colab free | Already the plan. Licences of the data and Ultralytics (AGPL-3.0) apply — fine for a hackathon. |
| 21 | **Synthetic-text generation** (ML track) | OpenAI | Gemini/Groq free routes · **IndicTrans2** on Kaggle GPU to translate real English 311 complaints to Hindi/Marathi | Replaces the "LLM-written complaints cost a few dollars" idea. |

Free-and-open already (nothing to replace): FastAPI, SQLAlchemy, Alembic, Pydantic, Uvicorn, React, Vite, TypeScript, TanStack Query, Zustand, Tailwind, Lucide, MapLibre, Recharts, Zod, Workbox, Vitest, Playwright, PostgreSQL/PostGIS/pgvector, Redis OSS, OpenTelemetry, Docker, JWT.

Note for the frontend team: the imported SIH2025 apps still depend on `@supabase/supabase-js`. Supabase has a free tier, but the design's backend is FastAPI + Postgres — decide whether the apps keep talking to Supabase directly (they should not; "do not bypass the API layer").

---

## 2. The AI layer on a zero budget — three tiers, all already wired

| Tier | Needs | What works |
|---|---|---|
| **0 · Local only** | nothing (no key, no internet) | B0 text classifier (weak; being replaced), **YOLO road-damage detector** (after notebook 06), deterministic triage/priority/SLA, hotspot/recurrence/SLA analytics, template analytics text, duplicate detection (lexical + geo + time). Every response says it is degraded. |
| **1 · Free cloud** | `GEMINI_API_KEY` (+ optional `GROQ_API_KEY`) | multimodal intake with structured output, LLM severity, AI-4 photo comparison, analytics prose, **copilot**, Whisper speech-to-text. |
| **2 · Local semantic** | the notebook-07 encoder (planned) | cross-language duplicate detection and a real multilingual text classifier without any API. |

Configuration (all optional; model IDs come from configuration only — pick them from each provider's model list when you create the key):

```env
GEMINI_API_KEY=...            # Google AI Studio -> Get API key (free)
GROQ_API_KEY=...              # console.groq.com -> API keys (free, no card)
AI_INTAKE_MODEL=<a vision-capable model that supports JSON schema output>
AI_ANALYTICS_MODEL=<a cheap/fast text model>      # also used for the copilot unless AI_COPILOT_MODEL is set
AI_EMBEDDING_MODEL=<an embedding model>           # optional; local encoder planned
AI_TRANSCRIPTION_MODEL=<a Whisper model id on Groq>
# AI_ROUTES=intake=gemini,transcription=groq      # default: transcription -> groq when keyed, everything else -> first keyed backend
# AI_GEMINI_RPM=10   AI_GROQ_RPM=20               # throttle to the free-tier limits
# AI_GEMINI_STRUCTURED=json_object                # if a model rejects json_schema output
AI_VISION_ONNX_PATH=ai/artifacts/road_damage/road_damage/best.onnx   # tier-0 image model
```

Implemented and tested on mock transports (`backend/tests/test_free_providers.py`, 12 tests): `ChatCompletionsProvider` (OpenAI-compatible chat completions / embeddings / audio transcriptions: structured output with automatic JSON-mode fallback, image data URLs, tool calling, `Retry-After` retries, RPM throttle, key never in `repr`), `CompositeProvider` (task routing), `build_provider_from_env`. **Not yet run against a live endpoint** — do one manual call per backend before the demo. Base URLs used: Gemini `https://generativelanguage.googleapis.com/v1beta/openai`, Groq `https://api.groq.com/openai/v1`, OpenRouter `https://openrouter.ai/api/v1`, Cloudflare `…/accounts/{id}/ai/v1` (override with `AI_<BACKEND>_BASE_URL` if a provider changes them).

---

## 3. Recommended free deployment for 1–7 October

1. **Demo machine:** one laptop (or a free VM) running **Docker Compose**: FastAPI + Postgres(PostGIS+pgvector) + Redis (or none) + MinIO + the ONNX model. Public URL via **Cloudflare Tunnel**.
2. **Frontends:** Cloudflare Pages (3 sites) pointing at the tunnel URL; maps via OpenFreeMap.
3. **AI:** Gemini + Groq keys from team members' Google/Groq accounts (free); keep the demo on **synthetic data only**. Keep the keys in env variables, never in git.
4. **Voice:** Web Speech API in the PWA for dictation; Groq Whisper endpoint for uploaded audio.
5. **Login:** password + email OTP (or a flagged fixed demo OTP). No SMS.
6. **Fallback on demo day:** if the network or a free quota fails, the app still runs in tier 0 and says so — that is the point of the degradation design.

---

## 4. Deviations from the locked design that need a team nod

| Change | Why | Risk |
|---|---|---|
| Free LLM backends instead of OpenAI | §30 allows another provider behind `AIProvider` | Free-tier privacy and rate limits; model quality on Marathi must be tested |
| Postgres 15–17 (Supabase/Neon/Docker) instead of 18.6 | none of the design's features need 18 | none |
| Redis in Docker, or Postgres/in-process jobs, instead of managed Redis 8 | free | slightly different ops story; events already fire-and-forget |
| Email OTP instead of SMS OTP | SMS has no free route in India | demo realism only |
| Local + tunnel hosting instead of cloud hosting | zero cost, zero cold starts | machine must stay online during judging |
| Web Speech API for dictation | free, instant | Chrome/Android only; audio goes to Google |

Everything else in §1 is "the design already says S3-compatible / equivalent host".

---

## 5. What I need from the team (nothing is paid)

1. Pick the free LLM account(s): create a Gemini key (and a Groq key), and **try one Marathi + one photo request in each provider's playground** before choosing model IDs.
2. Decide the hosting plan in §3 (laptop + tunnel vs Student-Pack VM).
3. Parth: Postgres + pgvector in Docker Compose; MinIO as the `ObjectStorage` implementation; email-OTP transport.
4. Krrish/Vedant: OpenFreeMap style URL in MapLibre; Web Speech API button in C05.
5. Tanuj: confirm the notebook-06 smoke run and the notebook-07 plan (real English 311 text + IndicTrans2 translation, no paid LLM).
