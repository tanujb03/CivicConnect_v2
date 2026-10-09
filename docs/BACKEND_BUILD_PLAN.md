# CivicConnect v2: Backend build plan (everything that is not the frontend)

**Audience:** the single backend Claude Code session (with sub-agents). **Owner:** Tanuj. **Written:** 8 Oct 2026, revised the same day after the repo census (section 1A). Branch `tanuj`, with `main` merged in by Tanuj (README commit `6a6663b` is in); WP0 re-reads `HEAD`.
**Scope:** `backend/`, `alembic/`, `ai/`, `infra/`, `scripts/`, `packages/api-client`, backend docs. **Not in scope:** `apps/**` (the frontend session owns it).
**Authority:** this file orders the work. `CLAUDE.md` rules still apply; where this file and `CLAUDE.md` disagree on session structure (one session, no lanes), this file wins. The design is `docs/CivicConnect_v2_V1_System_Design.md` (V1.1; Appendix A = what exists, Appendix C = what remains).

---

## 0. How to start (paste this to Claude Code)

> Follow `docs/BACKEND_BUILD_PLAN.md` from top to bottom: read it fully, then `CLAUDE.md`. Do WP0 yourself (including the tooling setup in section 2A), report, and wait for my "go". After that, run the waves with sub-agents and skills exactly as the plan says, keep the section 9 status table current, and stop only where section 11 says to ask me.

Launch this session as the backend session: `$env:CC_ROLE="backend"; claude` (PowerShell). The frontend session is launched with `$env:CC_ROLE="frontend"; claude`. The hooks created in WP0 use this variable to keep the two sessions out of each other's folders.

---

## 1. What is true right now (verified by reading the repo; the census report may refine it)

**Built and tested:** auth (register, login, rotating refresh, logout, `auth/me`), RBAC with object-level checks, cases and the state machine, evidence upload flow (local storage; S3 round trip once), work orders, verification, in-app notifications, map, analytics (including trends), incidents, offline sync API, admin users, admin settings, reference data, idempotency, pagination, error envelope, Redis Streams workers, AI gateway (Gemini/Groq/OpenAI-compatible providers with fakes), pgvector columns and indexes, Docker compose (db, redis, backend; profiles `s3`, `scan`, `obs`). 69 operations under `/api/v1`, migrations 0001 to 0003.

**Schema exists, behaviour does not:** `case_flags`, `device_tokens`, `evidence_items.scan_*`, `notifications.push_*` (all from migration 0003; Pydantic shapes already in `backend/schemas/platform.py`).

**Not built:** password change/reset, shared rate limiting, OpenTelemetry, embedding backfill, `packages/api-client`, an end-to-end HTTP smoke script, any live Gemini/Groq proof.

**Cut (do not build):** OTP login, Bhashini, local Indic models, model training, email/SMS, web push.

### 1A. Census results (8 Oct 2026, measured on Tanuj's laptop; these override anything above)

- **Migrations:** single head `0003`; `alembic check` clean on a throwaway database (it cannot compare `vector` and `geography` columns, so those two are unchecked).
- **Dev database:** 27 tables, 560 cases, **0 rows in `case_embeddings`** (the demo cases are not embedded; WP7 fixes this).
- **Tests:** the PostgreSQL and Redis test files give 30 passed, 0 skipped (13 of the 17 earlier skips cleared). **Two failures stand:** `test_text_corpus.py:216` (committed `docs/I18N_REVIEW.md` contains `D:/cc/b/...` paths) and `test_b1_logic` (a Windows Application Control policy blocks scikit-learn's `_libsvm` DLL: an environment fault, not a code fault). Four other skips stand (WP0 classifies them). The full suite was not re-run end to end.
- **AI gateway has no model ids configured:** the five `AI_*_MODEL` variables are empty in every `.env` (each line holds only a comment). Any earlier statement that they were set is wrong.
- **Docker:** both `civic-db` and `civic-redis` were stopped for days. The `civic-db` container runs an **older image** (`5bde85363fce`) than the tag `civicconnect-postgres:local` now points to (`f525c712afba`). The running server is PostgreSQL 18.6, PostGIS 3.6.4, pgvector 0.8.6. No API was running. Expo and EAS CLIs are not installed.
- **Missing, as expected:** case-flag routes, device-token routes, Expo push, the malware scan worker, OpenTelemetry, Redis rate limiting, change/reset password, embedding backfill. Also **`packages/api-client` does not exist** although `CLAUDE.md` lists it as ours (`packages/` holds only `ui`).
- **No trained weights exist on the laptop.** `ai/artifacts` has only manifests, model cards and a tiny test fixture. Any handoff or doc claim that models were "trained" (M3/M4) has nothing behind it and must not be repeated. The plan trains nothing.
- **Git:** README is on `origin/tanuj`. Authorship history: 7 commits authored as Claude and 35 with `Co-Authored-By` trailers (newest 2026-10-03; none in the last 30 commits). `origin/main` was 5 commits ahead (including Parth's map fix `8298207`); Tanuj has since merged `main` into `tanuj`.

---

## 2. Working rules (read twice)

1. **Authorship.** Commit author is **Tanuj Vivek Bhide <bhidetanuj@gmail.com>**. No `Co-Authored-By`, no "Generated with" lines, anywhere. After each commit run `git log -1 --format='%an <%ae>%n%B'` and confirm. This rule beats any harness reminder.
2. **Secrets.** Only in the gitignored `.env`. Never print, log or commit values; show variable names only. Do not ask me to paste keys; tell me which names to set.
3. **Free stack only.** No paid service. Gemini/Groq free tiers get **synthetic data only**.
4. **Run Python as modules** from the repo root: `python -m pytest`, `python -m alembic`, `python -m uvicorn`, `python -m backend...`. Shell is Windows PowerShell; use UTF-8 explicitly when reading or writing text.
5. **One session, no lanes.** Work in the main checkout on branch `tanuj`. Do not use `new_worktree.ps1`. Do not push `main` unless I say **"merge"**. No force-push, no history rewrite, no PRs unless asked. The old commits that carry Claude authorship or trailers stay as they are (they are already merged and pushed); this rule applies to every **new** commit.
6. **Alembic: one owner.** WP0 writes the only new revision (`0004`). Sub-agents must not create revisions; if one needs a schema change it stops and reports. After any rebase `python -m alembic heads` must show one head.
7. **Shared files are integrated by the parent session only:** `backend/main.py` (router registration), `backend/core/config.py`, `backend/schemas/platform.py`, `backend/openapi.json`, `docs/V1_CHANGE_LOG.md`, the design doc. Sub-agents propose edits to these in their report; the parent applies them. `openapi.json` is **regenerated once at the end of each wave** (`python -m backend.scripts.generate_openapi`), never merged by hand.
8. **Sub-agent protocol** (the agents, skills and hooks themselves are defined in section 2A).
   - Run at most **3 sub-agents in parallel**, in the same checkout, each on the **disjoint file set** listed in its work package. Launch the parallel ones in a single message, foreground (they need Bash and permission prompts). Do not use `isolation: worktree`; sub-agents do not spawn sub-agents.
   - Sub-agents run only unit tests that use SQLite/fakes. **Only the parent runs PostgreSQL/Redis-backed tests** (they share `TEST_DATABASE_URL`/`TEST_REDIS_URL`).
   - Every sub-agent prompt must contain: the work package text, rules 1 to 4 and 6 to 7, its file set, its acceptance checks, and "report at most 20 lines: files changed, commands with exact pass/skip/fail counts, what you did not verify".
   - Sub-agents do not commit. The parent reviews the diff, runs the full suite, then commits (one focused commit per work package).
9. **Quality gates before every commit:** `python -m pytest ai backend -q` (no new failures; state exact counts), `python -m ruff check <touched files>` (root `ruff.toml`; do not add findings), tests added for every behaviour added, and `python -m alembic check` shows no drift.
10. **Deviations are logged.** Anything that departs from the design or this plan gets a dated entry in `docs/V1_CHANGE_LOG.md` (date, what, why, affects).
11. **Honest reporting.** Report failing tests, skipped steps and unverified claims plainly. Synthetic data gives no real-world accuracy claim.
12. **Frontend contract changes** are made only additively. Removing or renaming a field, or changing a meaning, needs a change-log entry and a note in `docs/FRONTEND_REQUESTS.md`.
13. **End every work package with a report of at most 25 lines:** files changed; commands and exact counts; failures; what was not verified.

---

## 2A. Skills, sub-agents, hooks: use them

Exactly two Claude Code sessions exist: this backend one (with sub-agents) and a frontend one that Tanuj starts when a frontend task comes up. Sub-agents are not extra sessions.

**Look before you build.** Run `/agents` and `/skills` (or list `.claude/agents` and `.claude/skills`) and read what is there. Names differ between machines; use what is listed and never assume one exists.

**Plugin already installed: `claude-code-setup`.** Its skill `claude-automation-recommender` is read-only: it scans the repo and recommends hooks, skills, MCP servers, sub-agents and plugins. Run it **once**, in WP0 step 0, as input to the setup below. Its output is advice, not orders. Adopt only what fits rules 1 to 13; **do not install any MCP server or plugin** that needs an account, a paid plan, or network access beyond this plan's free stack; list what you declined. It never touches `apps/**`.

**Who does what**

| Job | Use |
|---|---|
| Find code, patterns, usages; read many files; check "does X exist" (WP0 checks, "how do existing routers do pagination?", WP10 triage) | built-in **Explore** sub-agent (read-only; say "medium" or "very thorough") |
| Design a non-trivial change before coding (WP5 push worker, WP6 scan worker, WP7 embedder choice) | built-in **Plan** sub-agent, then the parent decides |
| Write the code and tests of one work package inside its file set | project sub-agent **`backend-implementer`** (up to 3 in parallel, disjoint file sets) |
| Review a finished work package with fresh eyes | project sub-agent **`backend-reviewer`** (read-only). **Mandatory** after WP2, WP3, WP4, WP5, WP6, WP11; optional elsewhere. Give it the diff and the work package text, **not** your own verdict |
| Look up current package names and versions on the web (WP8, WP9), provider docs (WP1) | **general-purpose** sub-agent with web access; it reports versions with source URLs, the parent pins them |
| Questions about Claude Code itself (hooks, agents, settings) | **claude-code-guide** sub-agent |
| Security pass on auth, gating and uploads | built-in `/security-review` if present, after WP2 and WP6, in addition to `backend-reviewer` |
| Repeated procedures | the project skills below |

**Created once in WP0 step 0** (small; committed under `.claude/` unless noted; show me the list in the WP0 report):

- `.claude/agents/backend-implementer.md`: tools `Read, Edit, Write, Glob, Grep, Bash`; `disallowedTools: Agent`; `model: inherit`. Body: you receive a work package, a file set and acceptance checks; touch no other file; **no commits, no Alembic revisions, no edits to shared files (rule 7), no PostgreSQL/Redis tests**; follow rules 1 to 4; write tests for every behaviour; report at most 20 lines (files changed, exact command counts, what you did not verify).
- `.claude/agents/backend-reviewer.md`: tools `Read, Glob, Grep, Bash`; `disallowedTools: Edit, Write, Agent`; `model: inherit`. Body: read-only; use Bash only for `git diff/log/status`, `python -m ruff check`, and SQLite/fake-backed `python -m pytest`. Review the diff against the work package acceptance and rules 1 to 13: authorization holes (object-level checks, wrong role, wrong ward), idempotency, error envelope and codes, audit rows, secrets in code or logs, trailers or wrong author, tests that only assert the happy path, files outside the file set, non-additive contract changes. Report findings ranked by severity, at most 25 lines, no fixes.
- `.claude/skills/add-endpoint/SKILL.md`: the checklist for a new endpoint (router in `backend/api/v1`, service function, schema, permission and object-level check, idempotency where it mutates, error codes, audit event, tests for each role, `docs/FRONTEND_API_NEEDS.md` entry; `main.py` registration and `openapi.json` regeneration left to the parent).
- `.claude/skills/quality-gates/SKILL.md`: the exact commands of rule 9 and how to report their counts (`python -m pytest ai backend -q`, ruff on touched files, `alembic heads`, `alembic check`, the Postgres/Redis test invocation with the test URLs).
- `.claude/skills/wp-report/SKILL.md`: the 25-line report template of rule 13 and the instruction to update the section 9 table.
- `.claude/hooks/guard.py` (stdlib only, reads the hook JSON from stdin, exit code 2 with a reason on stderr to block), wired in **`.claude/settings.local.json`** (gitignored, so teammates' sessions are unaffected):
  1. `PreToolUse` on `Bash` for `git commit*`: block if the command or message contains `Co-Authored-By`, `Generated with`, or `claude.ai/code`, or if `git config user.email` is not `bhidetanuj@gmail.com`.
  2. `PreToolUse` on `Bash`: block `git push --force*`, `git push *--force-with-lease*`, `git reset --hard*`, `git clean -f*`, `docker compose down -v*`, `docker volume rm*`, and any push to `main` (rule 5), and any command that prints `.env` contents.
  3. `PreToolUse` on `Edit|Write`: when `CC_ROLE=backend`, block paths under `apps/`; when `CC_ROLE=frontend`, block `backend/`, `alembic/`, `ai/`, `infra/`, `packages/api-client/`. When `CC_ROLE` is unset, allow everything.
  4. `PostToolUse` on `Edit|Write` for `*.py` under `backend/`, `ai/`, `scripts/`: run `python -m ruff check <file>` and print findings to stderr (non-blocking).
  5. Also in `settings.local.json`: `permissions.deny` for reading `.env` and `.env.*` (not `.env.example`), and the `attribution` setting with `commit` and `pr` set to empty strings so Claude Code stops adding trailers and PR lines (check the settings reference for the exact keys; verify with a throwaway commit on a scratch branch that the message has no trailer, then delete the branch).
  Test each hook once (a blocked case and an allowed case) and show me the result. Hooks are a safety net for rules 1, 2, 5; they do not replace following the rules. If a hook blocks something legitimate, tell me; do not edit around it.

A newly created `.claude/agents` directory needs a session restart to load. After creating it, tell me to run `/exit` and `claude --continue` (with `CC_ROLE=backend`), then carry on.

---

## 3. Two-session coordination

The frontend session never edits `backend/`; the backend session never edits `apps/`. They talk through two files, both in `docs/`:

- `docs/FRONTEND_REQUESTS.md`: the frontend session appends requests (endpoint missing, field missing, shape mismatch, error code needed), one entry each: date, app and page, what is needed, example request/response. **The backend session reads it at the start of every wave and after every work package, answers each entry (`DONE <commit>`, `WON'T <reason>` or `QUESTION`), and does the work in WP10.**
- `docs/V1_CHANGE_LOG.md`: the backend session records every contract change; the frontend session reads it.

`docs/FRONTEND_API_NEEDS.md` stays the page-by-page reference for the shapes already served. Create `docs/FRONTEND_REQUESTS.md` in WP0 with a header and the entry template.

---

## 4. Waves at a glance

| Wave | Work packages | Run as |
|---|---|---|
| **0** | WP0 baseline, migration 0004, repo hygiene | parent alone |
| **1** | WP1 live AI proof (needs my keys), WP2 auth hardening, WP3 rate limiting | WP1 parent with me; WP2 and WP3 as 2 sub-agents |
| **2** | WP4 community flags, WP5 Expo push, WP6 upload scan | 3 sub-agents |
| **3** | WP7 embeddings, WP8 tracing, WP9 API client | 3 sub-agents |
| **4** | WP10 frontend requests (repeats until the demo), WP11 deployment and smoke, WP12 docs | parent, sub-agents as needed |

For every work package that runs as a sub-agent: parent writes the sub-agent prompt (work package text, file set, acceptance checks) → `backend-implementer` → parent reads the diff → `backend-reviewer` where section 2A makes it mandatory → parent fixes or sends findings back → parent runs the quality gates (skill `quality-gates`) → one commit → `wp-report`.

After each wave: the parent applies the shared-file edits, regenerates `openapi.json`, runs the full suite (including PostgreSQL and Redis tests), commits, pushes `origin/tanuj` (`git fetch`, `git rebase origin/tanuj`, re-test, `git push origin HEAD:tanuj`), and reports.

---

## 5. Wave 0: WP0 baseline (parent alone)

**Goal:** a known-good starting point and the one migration everything else needs.

0. **Tooling (section 2A).** Run the `claude-automation-recommender` skill once, then create the two sub-agents, three skills, the hook script and `settings.local.json` entries listed in 2A, test the hooks, and have me restart the session so the agents load. Do this before anything else, because every later step uses them.
1. `git fetch --all --prune`; confirm you are on `tanuj`, clean, and level with `origin/tanuj` (Tanuj merged `main` in; confirm `git log origin/main..HEAD` and `HEAD..origin/main` are as expected and the map fix `8298207` is present). If other worktrees or branches (`multigpu`, `D:\cc\*`) hold unpushed work, list it and **stop for my decision**.
2. Read the census report if present; section 1A already carries its results. Anything new that contradicts section 1 or 1A: trust the census and edit them and the status table.
3. **Refresh the containers.** `civic-db` runs a stale image. Recreate it from the current tag without deleting the data volume (`docker compose ... up -d --force-recreate db`, or the repo's `db_up.ps1` if it does that), then confirm `SELECT extname, extversion FROM pg_extension` shows PostGIS 3.6.x and vector 0.8.6. If the data volume turns out incompatible with the new image, **stop and ask**; do not `down -v` the dev database without my word. Then `python -m alembic upgrade head`, `python -m backend.scripts.seed_demo` (only if the dev DB is empty or I say so), `python -m pytest ai backend -q`. Record exact counts, and classify the four remaining skips (reason for each).
4. **Make the suite green in a clean environment, and fix the two known failures.**
   - Optional training packages (`sklearn`, `scipy`, `nbclient`/`nbformat`) missing in a clean venv: `pytest.importorskip` at the top of the affected `ai/training/tests/*` and `ai/evaluation/tests/test_tracks_real.py`. This also covers `test_b1_logic` on machines where an OS policy blocks scikit-learn's DLL (the import raises `ImportError`; if the skip does not catch it, catch `ImportError` explicitly and skip with that reason).
   - `docs/I18N_REVIEW.md` has `D:/cc/b/...` paths, so `test_text_corpus.py:216` fails anywhere except one old lane. Regenerate the block with `python -m ai.training.src.text_corpus.review_sample` and make the generator write repo-relative paths so it stays portable.
   - Do not change what any test asserts.
4a. **Honesty sweep (docs only):** `grep -rniE "trained|M3|M4|weights" CLAUDE.md docs README.md ai/artifacts` and correct any statement that implies trained models exist (none are on disk and none are used). Replace with the truth: pretrained hosted models through `AIProvider`, no training. Also fix `CLAUDE.md`'s claim that `packages/api-client` exists (it is created in WP9) and its implication that the compose stack is running. List what you changed in the report; log it in `docs/V1_CHANGE_LOG.md`.
5. **Migration 0004** (the only new revision in this plan), SQLite-portable like 0001 to 0003, reversible:
   - `users.must_change_password BOOLEAN NOT NULL DEFAULT false`
   - `users.password_changed_at TIMESTAMP NULL`
   - `device_tokens`: add an index on `(user_id, revoked_at)` if absent
   - `notifications`: add an index on `(push_status, created_at)`
   - `evidence_items`: add an index on `(scan_status)`
   - `case_flags`: confirm the unique `(case_id, user_id, kind)` and an index on `(case_id, status)`
   Verify upgrade, `downgrade -1`, upgrade, and `alembic check` on both SQLite and PostgreSQL.
6. Create `docs/FRONTEND_REQUESTS.md` (section 3). Create `scripts/dev/smoke.py` as an empty stub with a docstring (filled in WP11).
7. Commit WP0. Report. **Wait for my "go".**

**Acceptance:** `pytest ai backend -q` has 0 failures in a clean venv with only `backend/requirements.txt` plus `pytest`, **and** 0 failures on Tanuj's laptop (the two census failures gone); `civic-db` runs the current image with the expected extension versions; one Alembic head (`0004`); the report lists exact counts, the classified skips, and the honesty-sweep edits.

---

## 6. Wave 1

### WP1: Live AI proof (parent, with me)

**Why first:** nothing in the AI layer has ever been run against a real provider.
**Files:** `backend/ai_gateway/providers/*`, `backend/ai_gateway/*`, tests.
0. **Precondition (census):** all five `AI_*_MODEL` variables are empty in every `.env`, so the gateway has no model ids. First confirm and record what the gateway does with empty ids (it must degrade cleanly and say so in the response, not crash). Do not guess model ids and do not copy them from memory or old docs.
1. I put the keys in `.env` (you never ask for key values). Run `python -m backend.ai_gateway.providers.live_check --list-models`; show me the model **names** per provider and **wait**: I choose the ids and set the `AI_*_MODEL` variables. Choose from what the provider lists as available on the free tier at that moment.
2. With keys present run the live checks for text, `--image`, and `--audio` (a short Marathi or Hindi clip from `D:\civic-test-media\voice`; synthetic clips). Use only synthetic content.
3. Fix adapters for whatever misbehaves (structured output rejection, rate limits, vision payload shape, Whisper response format). Each fix gets a regression test with a recorded fake response.
4. Exercise the real endpoints once: `POST /cases/intake/analyze` with text, with photo, with an audio transcript; `POST /cases/{id}/fusion/analyze`; `POST /cases/{id}/triage/analyze`; `POST /copilot/query`. Record, per call: provider, latency, schema validity, confidence, and what the degraded path does when the provider is blocked (unset the key and re-run).
5. Write the results (no accuracy claims) to `docs/AI_LIVE_CHECK.md` with date and model names.

**Acceptance:** each of the six AI capabilities has either a recorded live pass or a recorded, explained failure with the fallback behaviour confirmed. **Never** claim accuracy.

### WP2: Auth hardening (sub-agent)

**Files:** `backend/api/v1/auth.py`, `backend/services/auth.py`, `backend/services/admin_users.py`, `backend/schemas/auth*.py` (new schemas allowed), `backend/tests/test_api_auth*.py`, `backend/tests/test_api_admin_users.py`.
- `POST /auth/change-password` `{current_password, new_password}`: verifies the current password, enforces a password policy (minimum 10 characters, not equal to the current, not in a small deny-list of obvious passwords), sets `password_changed_at`, clears `must_change_password`, **revokes every other refresh token** of the user, writes an audit event `user.password_changed` (never the password), returns a fresh token pair.
- `POST /admin/users/{id}/reset-password` (CITY_ADMIN, SYSTEM_ADMIN; same elevated-role rule as `PATCH`): generates a one-time password, returns it once, sets `must_change_password = true`, revokes the user's refresh tokens, audits `user.password_reset`. Idempotency: ignore the key on purpose, like `POST /admin/users`.
- `POST /admin/users` now creates staff with `must_change_password = true`.
- `GET /auth/me` and the login response expose `must_change_password`. While it is true, every endpoint except `/auth/change-password`, `/auth/logout`, `/auth/refresh`, `/auth/me` answers **403 `PASSWORD_CHANGE_REQUIRED`**.
- Seeded demo accounts keep `must_change_password = false`.
**Acceptance:** tests for success, wrong current password, weak password, reuse of an old refresh token after change (401), forced-change gating, audit rows without secrets, role rules on reset.

### WP3: Rate limiting (sub-agent)

**Files:** `backend/core/rate_limit.py` (new), `backend/core/exceptions.py` (add `RATE_LIMITED`), `backend/api/deps.py`, small dependency additions on routers (parent registers), `backend/tests/test_rate_limit.py`.
- Fixed-window or sliding-window counters in Redis (`INCR` + `EXPIRE`, keyed by user id or client IP), with an **in-process fallback** when Redis is unreachable (never fail open silently: log a warning once per minute).
- Limits (configurable in `config.py` with these defaults): login 10/min per IP and 5/min per identifier; register 5/min per IP; `POST /cases` 20/hour per user; `POST /evidence/upload-init` 60/hour per user; AI endpoints (`intake/analyze`, `fusion/analyze`, `triage/analyze`, `copilot/query`) 30/hour per user (protects the free-tier quotas); everything else 600/min per user.
- Answer **429** with the standard error envelope, code `RATE_LIMITED`, `Retry-After` header, and `X-RateLimit-Limit/Remaining/Reset` on limited routes.
- `ENVIRONMENT=test` and `RATE_LIMIT_ENABLED=false` switch it off; tests that need it turn it on.
**Acceptance:** tests for each limited route class, the 429 envelope and headers, window reset, Redis-down fallback, and that exempt routes (`/health/*`) are never limited.

---

## 7. Wave 2 (three sub-agents in parallel; file sets are disjoint)

### WP4: Community flags

**Files:** `backend/api/v1/flags.py` (new), `backend/services/flags.py` (new), `backend/tests/test_api_flags.py`. Parent registers the router and reads shapes from `backend/schemas/platform.py` (`CaseFlagIn/Out/ResolveIn`).
- `POST /cases/{case_id}/flags` (any authenticated user who may view the case; one flag per user per kind per case, duplicate = 409 `FLAG_ALREADY_EXISTS`; a reporter cannot flag their own case as `INAPPROPRIATE`).
- `GET /cases/{case_id}/flags` (staff with access to the case: list with counts by kind and status).
- `POST /flags/{flag_id}/resolve` `{status: UPHELD | DISMISSED}` (staff; audited, timeline event).
- When the number of **open** flags on a case reaches `flag_review_threshold` (system setting, default 3): add a timeline event, notify the department operators and ward officer, and mark the case for review in a way the queue can show (an `AIAnalysis`-free boolean or a derived `needs_flag_review` field on the case view; additive only).
- `INAPPROPRIATE` flags at threshold hide the case from the public map (`/map/cases`) until resolved.
**Acceptance:** tests for permissions (citizen, other citizen, staff, wrong ward), duplicate flag, threshold crossing, notification fan-out, resolve flow, map hiding, audit rows.

### WP5: Expo push

**Files:** `backend/api/v1/devices.py` (new), `backend/services/push.py` (new), `backend/events/workers.py` (the notification worker only: add the push step), `backend/tests/test_api_devices.py`, `backend/tests/test_push.py`.
- `POST /me/devices` (`DeviceTokenIn`: upsert by `expo_push_token`, bind to the current user, reset `revoked_at`), `GET /me/devices`, `DELETE /me/devices/{id}` (revoke). Logout can optionally revoke the device (`device_id` in the body, additive).
- Sender: for each new `Notification`, if `notification_policy.push` is true and the user has active tokens, POST batches (<= 100) to `https://exp.host/--/api/v2/push/send` via `httpx`, set `push_status` (`NONE` → `PENDING` → `SENT` / `FAILED`), store `push_receipt_id`, `push_attempts`; a second pass fetches receipts (`/push/getReceipts`); on `DeviceNotRegistered` revoke that token. Retry with backoff up to 3 attempts. Respect Expo's documented limits and add an optional `EXPO_ACCESS_TOKEN` environment variable (name only; never log it).
- A fake Expo server for tests (respx or a local `httpx.MockTransport`); **no real push is sent in tests**.
- Payload: title, body (localised from the user's `preferred_language`, English fallback), `data: {case_id, type}` so the app can deep-link.
**Acceptance:** tests for register/upsert/revoke, batching, success, partial failure, `DeviceNotRegistered`, policy switched off, no tokens, and that failures never break the notification write.
**Note:** remote push does not work in Expo Go; it needs a development build. Say so in the endpoint docs.

### WP6: Upload malware scan

**Files:** `backend/services/malware_scan.py` (new), `backend/services/evidence.py` (hook only: enqueue a scan job on `complete`), `backend/events/workers.py` (add a scan worker group; coordinate with WP5 by keeping edits to separate functions), `backend/tests/test_malware_scan.py`.
- clamd client over TCP using the `INSTREAM` protocol (no third-party dependency needed; or `clamd` if added to `requirements.txt` with a pinned version). Configuration: `SCAN_ENABLED` (default false), `CLAMD_HOST`, `CLAMD_PORT` (3310), `SCAN_MAX_BYTES`.
- Flow: `complete` sets `scan_status = PENDING` and enqueues; the worker streams the stored object to clamd; `CLEAN` / `INFECTED` (with `scan_signature`) / `ERROR` (retry up to 3 times, then leave `ERROR` and alert via an audit event).
- **Gate:** a signed GET for `INFECTED` evidence is refused (403 `EVIDENCE_QUARANTINED`); `PENDING` is allowed only when `SCAN_ENABLED=false`; an `INFECTED` result writes an audit event and a timeline note, and the evidence is hidden from non-staff.
- When `SCAN_ENABLED=false` (the default), new rows are marked `UNSCANNED` instead of `PENDING` so the state never lies.
- Tests use a fake clamd socket server; one optional integration test runs against the compose `scan` profile with the **EICAR** string and is skipped when clamd is unreachable.
**Acceptance:** tests for clean, infected, daemon down, retry exhaustion, gating, the disabled mode, and that the upload flow still completes when scanning fails.

---

## 8. Wave 3 and Wave 4

### WP7: Embeddings and duplicate search (sub-agent)

**Files:** `backend/scripts/backfill_embeddings.py` (new), `backend/services/ai_jobs.py`, `backend/ai_gateway/service.py`, `backend/ai_gateway/sql.py`, `backend/ai_gateway/vectors.py`, tests.
- Decide the embedder from the WP1 results (provider embeddings via `AI_EMBEDDING_MODEL`, or the pretrained multilingual-e5-small if `sentence-transformers`/ONNX is available). State the choice and dimension in the change log; **do not train anything**.
- Embed on case creation through the existing `embed` job; `python -m backend.scripts.backfill_embeddings [--limit N] [--only-missing] [--dry-run]` embeds existing cases in batches, resumable, rate-limit aware, writing `embedding_dim` and `embedding_model`.
- `seed_demo --with-embeddings` calls the same code path.
- Verify with `EXPLAIN` that the correct partial HNSW index is used for the chosen dimension; if the chosen dimension has no index, drop that migration question to me (do not add a revision yourself).
- Evaluate duplicate detection on the demo city with `python -m ai.evaluation.run_eval` (fusion track) and record before/after in `docs/AI_LIVE_CHECK.md`. No accuracy claims on real citizens.
**Acceptance:** backfill is idempotent, a Python-cosine fallback still works without pgvector, tests cover dimension mismatch, empty text and provider failure.

### WP8: OpenTelemetry (sub-agent)

**Files:** `backend/core/telemetry.py` (new), `backend/main.py` (parent hooks it), `backend/requirements.txt`, `backend/tests/test_telemetry.py`.
- **Verify the current package names and versions on PyPI before adding them** (the OpenTelemetry API/SDK, OTLP HTTP exporter, FastAPI, SQLAlchemy, Redis and httpx instrumentations). Pin them in `requirements.txt`. Do not assume FastAPI has built-in tracing.
- Off by default (`OTEL_ENABLED=false`); when on, export OTLP/HTTP to `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://localhost:4318`; `http://jaeger:4318` in compose). Propagate trace context into the Redis event envelope so API → worker → AI call is one trace. Add `service.name=civicconnect-backend` and the request id as an attribute.
- Tests use the in-memory span exporter. Document the Jaeger URL (`http://localhost:16686`) in `docs/infra/COMPOSE.md`.
**Acceptance:** with the `obs` profile and `OTEL_ENABLED=true`, a created case appears in Jaeger as one trace with API, SQL and worker spans (verify manually and record it); with it off there is no overhead and no import error.

### WP9: Generated API client (sub-agent)

**Files:** `packages/api-client/**` (new), `scripts/dev/gen_api_client.ps1` (new), a test that fails when the generated types are stale.
- Generate TypeScript types from `backend/openapi.json` (for example `openapi-typescript`; verify the current package name and version first) and a thin typed `fetch` wrapper that handles: base URL (`API_BASE_URL` injected), bearer token, **401 → refresh once → retry**, `Idempotency-Key` generation for mutations, the error envelope (`ApiError` with `code`, `message`, `details`, `request_id`), and cursor-pagination helpers. Must work in React Native and in the browser (no Node-only APIs).
- A short `README.md` in the package: install, regenerate, usage with TanStack Query.
- Regenerate it in the parent's end-of-wave step, together with `openapi.json`.
- Do **not** edit `apps/**`. Tell the frontend session (via `docs/FRONTEND_REQUESTS.md`, a `NOTE` entry) that the package exists and how to consume it.
**Acceptance:** `npm run build` and `npm run typecheck` pass in the package; the staleness test fails when `openapi.json` changes without regeneration.

### WP10: Frontend requests (parent, repeating)

At the start of every wave and after every work package: read `docs/FRONTEND_REQUESTS.md`, triage each entry (small additive change = do it now with tests; contract change = log it; larger = tell me), answer each entry with the commit hash. Typical items to expect: missing fields on list views, enum values, error codes, CORS origins, signed-URL base address on devices, notification payload shapes, demo data the apps need.

### WP11: Deployment and the end-to-end smoke (parent)

1. **`scripts/dev/smoke.py`** (stdlib + `httpx`): against a running API, with demo accounts, perform the full loop over HTTP and assert each step: citizen registers/logs in → `intake/analyze` → creates a case (idempotency key; replay returns the same case) → duplicate fusion → admin lists and triages → creates a work order → field worker starts, uploads evidence (init → PUT → complete), completes → citizen verifies "YES" → case is `RESOLVED` → analytics reflect it. Also assert: forged token rejected (401), another citizen cannot read the case (403/404), missing idempotency key rejected, a rate-limited route returns 429 when the limit is lowered, change-password flow, a flag crossing the threshold, a device registration, an infected-file upload refused (when the scan profile is up). Exit non-zero on any failure; print a pass/fail table.
2. **Demo reset:** `python -m backend.scripts.demo_reset` recreates the demo city (reference data, 560 cases, accounts) **plus one scripted case per stage** of the lifecycle so the demo never starts empty (a case awaiting triage, one with a work order, one awaiting verification, one reopened, one resolved), including a field-worker work order that exists in the real database (the earlier sandbox-only demo case `CC-2026-000006` must exist here).
3. **Compose from empty volumes:** `docker compose -f infra/compose/docker-compose.yml down -v`, then up with `--wait`, migrate, seed, smoke. Record timing.
4. **Phone reachability:** verify `PUBLIC_BASE_URL` with a LAN address and with a Cloudflare Tunnel (`docs/infra/TUNNEL.md`); confirm a signed evidence URL opens from a phone. If you cannot test from a phone, say so and give me the exact manual steps. **Rate limits behind the tunnel** (`docs/infra/TUNNEL.md` section C): `RATE_LIMIT_TRUST_FORWARDED_FOR=true` only when the tunnel is the sole way into the backend (API bound to 127.0.0.1); the smoke test must show that two different client IPs behind the tunnel get separate sign-in buckets and that a forged `X-Forwarded-For` does not buy a fresh bucket.
5. **CORS and hosting values:** list the origins needed for the Vercel apps and the Expo web build, put them in `.env.example`, never `*` with credentials.
6. **Backup for the demo:** a `scripts/dev/snapshot_demo_db.ps1` (and restore) using `pg_dump`, so a broken demo can be reset in under a minute. **Embeddings are part of the snapshot** (`case_embeddings` is dumped and restored with the rest): restoring or resetting the demo must NEVER re-embed all cases (embedding quota: 1000 requests/day, 30K tokens/minute). `demo_reset` and the restore script say so in their `--help` text, embed only rows that are missing an embedding, and refuse a full re-embed without an explicit `--allow-reembed`.
**Acceptance:** `smoke.py` passes from empty volumes on this machine; the report states timing and any step you could not verify.

### WP12: Documentation (parent, last)

- Update Appendix A and C of the design doc to the new truth (status words per capability, counts re-measured), add the final entries to `docs/V1_CHANGE_LOG.md`, update `backend/README.md`, `docs/FRONTEND_API_NEEDS.md` for every new endpoint (shapes and errors), `docs/infra/COMPOSE.md` (profiles actually wired), and regenerate `openapi.json`.
- Re-measure and record: test counts, number of operations, migration head, idle memory.
- Confirm `README.md` still matches reality (commands in Quick Start run; endpoint and test counts; no feature listed that is not built). Report discrepancies to me; do not silently rewrite the README's tone.

---

## 9. Status table (the session keeps this current; one line per update)

| WP | Title | State | Commit | Notes |
|---|---|---|---|---|
| 0 | Baseline, migration 0004, hygiene | DONE (tests green) | 93311d4 | clean venv 968 passed / 39 skipped / 0 failed; PostgreSQL+Redis run green; `civic-db` recreated on the current image (PostgreSQL 18.6, PostGIS 3.6.4, pgvector 0.8.6, data intact); dev DB at 0004 |
| 1 | Live AI proof | DONE (tests green) | 7f2b264, b913472 | every capability has a recorded live pass on `gemini-3.5-flash-lite` / `gemini-embedding-001` (768) / Groq `whisper-large-v3` (docs/AI_LIVE_CHECK.md) plus the degraded paths; no accuracy claim. OPEN on Tanuj's word: one comparison photo on `gemini-3.5-flash` (at most 5 flash calls, 13 s apart); no flash call has been made. Open observations: a 29 s latency outlier, audio-only intake contract (done: 200 + TRANSCRIPTION_UNAVAILABLE) |
| 2 | Auth hardening | DONE (tests green) | 6e6c2f1 | backend-reviewer: no blocker, minor items fixed (own pwchange counter, Retry-After, no-store, gate also on AI gateway routes); /security-review pass: nothing reportable; known limit: old access tokens live up to 30 min after a change |
| 3 | Rate limiting | DONE (tests green) | 033d8ef | backend-reviewer: no blocker; majors fixed (rightmost X-Forwarded-For, media routes counted, test against the real app); not run against a real Redis in the unit tests (fake); full suite with Redis green |
| 4 | Community flags | DONE (tests green) | de33b0f | backend-reviewer: no blocker, 3 majors fixed (UPHELD keeps the case hidden, `map_hidden` for staff, flag fields on every staff view) + minors; PostgreSQL-specific SQL (grouped counts) ran in the full PG suite |
| 5 | Expo push | DONE (tests green) | f3bfa52 | backend-reviewer: no blocker, 4 majors fixed (no attempts burned on outages/config errors, 400 bisect, per-batch commit + SKIP LOCKED, device cap); never run against real Expo; at-least-once delivery; logout `device_id` not built (apps revoke the device first) |
| 6 | Upload malware scan | DONE (tests green) | 6f83237 | backend-reviewer: 1 blocker (signed PUT could swap a CLEAN file) + 6 majors fixed; my own read of the gate code found nothing more; clamd never run for real (EICAR test skipped), S3 presigned windows documented |
| 7 | Embeddings and duplicate search | DONE (tests green) | 447cbf5, c643f06, 50c1066 | full backfill run 2026-10-08: 560 of 560 cases embedded (768 dims, norm 1.0, pgvector filled; 550 via the provider in 11 calls, 612.8 s, 0 failures); AI Studio expected about 578 of 1000 (per-input counting; the script's own counter said 39 because of an override bug, fixed, Redis set to 578); calibration on 27 synthetic positives (no real-world claim, policy file unchanged: owner decides); HNSW partial index usable per EXPLAIN; details in docs/AI_LIVE_CHECK.md and docs/DUPLICATE_CALIBRATION.md |
| 8 | OpenTelemetry | DONE (tests green) | 6deef82 | native FastAPI spans + SQLAlchemy + Redis-envelope trace context, off by default; reviewed; verified against a real Jaeger on 2026-10-09: one created case = one trace of 101 spans (API, 89 SQL, Redis publish, worker process, Gemini HTTP), see docs/infra/COMPOSE.md; the compose `obs` profile with a containerised backend was not run |
| 9 | Generated API client | DONE (tests green) | 426ca53 | packages/api-client (openapi-typescript 7.13.0 + openapi-fetch 0.17.0): typecheck, build, 10 node tests, 3 Python staleness tests; not tried inside a real Expo build or the Vite apps; not security-sensitive, no reviewer run. Full suite 1609 passed, 5 skipped, 0 failed (PostgreSQL + Redis) |
| 10 | Frontend requests | ONGOING | | 2026-10-09: FRONTEND_REQUESTS.md has no open request from the apps (four entries, all backend notes, answered DONE); re-read it at the start of the next wave |
| 11 | Deployment and smoke | DONE except the phone and the tunnel (tests green) | 72a3769 | scripts/dev/smoke.py 42/42 on the dev API, on a fresh compose project from empty volumes (up --build --wait 67 s) and through the LAN address; demo_reset keeps the 560 embeddings (md5 identical, quota counters unchanged); snapshot+restore 3 s; backend-reviewer: no blocker, 4 majors fixed. NOT verified: a real phone, a Cloudflare Tunnel (cloudflared not installed; forwarded-for logic simulated), `down -v` (blocked by the guard hook; volumes were already empty), the s3 profile |
| 12 | Documentation | DONE (numeric facts only in README.md) | 2b516fd | README.md: operations 69 to 78, tests 1,621 passed / 5 skipped, migrations 3 to 4; backend/README.md, COMPOSE.md, TUNNEL.md, AI_LIVE_CHECK.md, change log updated. Mismatches reported, not rewritten: README Roadmap still lists Expo push, malware scanning, tracing and the typed client (all built now); README says Redis 7.4 (compose and db_up pull `redis:7`); the design doc has no Appendix A or C |

States: `TODO`, `IN PROGRESS`, `DONE (tests green)`, `BLOCKED (reason)`.

---

## 10. Definition of done for the backend

- `python -m pytest ai backend -q` has **0 failures** in a clean venv, and the exact counts are in the final report.
- `python -m alembic heads` shows one head; `python -m alembic check` shows no drift on PostgreSQL.
- `scripts/dev/smoke.py` passes against the compose stack started from empty volumes.
- `backend/openapi.json` and `packages/api-client` are current.
- Every AI capability has a recorded live pass or an explained fallback (`docs/AI_LIVE_CHECK.md`).
- Every deviation is in `docs/V1_CHANGE_LOG.md`; the design doc's Appendix A matches reality.
- Nothing in the repo or in any commit contains a secret value, a trailer, or a non-Tanuj author.
- `docs/FRONTEND_REQUESTS.md` has no unanswered entries.
- Every mandatory review (section 2A) has a recorded outcome in the status table notes.

## 11. Things that need me (stop and ask; do not guess)

- API keys and model names (WP1).
- Any unpushed work found in other worktrees or branches (WP0 step 1).
- A data-volume problem when refreshing the `civic-db` container (never `down -v` the dev database unasked).
- Whether to rewrite old authorship (7 commits authored as Claude, 35 with trailers). Default: **no**; the commits are pushed and already merged, and a rewrite means force-pushing shared branches and breaking teammates' clones.
- A schema change a sub-agent needs beyond migration 0004.
- Which embedder and dimension if WP1 shows the provider embeddings are unusable.
- Anything that would remove or rename a field the apps already read.
- Anything paid.
- A recommendation from the setup plugin that would install an MCP server or plugin, or change settings shared with teammates (`.claude/settings.json`).
