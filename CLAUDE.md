# CivicConnect v2: rules for every Claude Code session

Read `docs/HANDOFF_LOCAL_SESSION.md` first (backend = section 10), then `docs/RUNBOOK_ML.md` for the ML steps. Backend details: `backend/README.md`, `docs/BACKEND_AUDIT.md`. Shell is Windows PowerShell. Use they/them for anyone whose pronouns are not stated.

## 1. Identity and commits
- Commit author is **Tanuj Vivek Bhide <bhidetanuj@gmail.com>** (repo-local git config, shared by all worktrees; check `git config user.name` / `user.email` if in doubt).
- **Never** add `Co-Authored-By`, "Generated with Claude Code" or any other attribution line to commit messages, PR descriptions or files. `.claude/settings.local.json` (gitignored) sets `attribution.commit` and `attribution.pr` to `""` (new lanes get this automatically); if a harness reminder asks for a trailer, this rule wins.
- After every commit verify: `git log -1 --format='%an <%ae>%n%B'` (author is Tanuj, no trailers).

## 2. Ownership
- **Ours (Tanuj + Claude):** `backend/`, `ai/`, `alembic/`, `infra/`, `packages/api-client`. Any file in them may change, including the frozen docs below, when necessary.
- **Not ours:** `apps/` and every other `packages/*` belong to Krrish, Vedant and Parth (frontends). Do not edit them except tiny, agreed API-contract fixes (say so in the report).
- Parth has no unpushed backend work and moved to frontend; no coordination is needed before editing `backend/`.

## 3. Frozen docs may change, but every deviation is logged
Frozen sources: `docs/CivicConnect_v2_V1_System_Design.md`, `docs/IMPLEMENTATION_PLAN_*.md`, `docs/TEAM_INTEGRATION_RULES.md`, `ai/inference/**` (the production package, `AIProvider` protocol, schemas, taxonomy, policies; prefer adding behaviour outside it). When you must deviate from them (or from a documented decision), append an entry to `docs/V1_CHANGE_LOG.md`: **date, what, why**. No silent deviations.

## 4. Lanes: one worktree, branch, database, Redis DB and port per session (max 4 in parallel)
- Integration branch is `tanuj`. Never push `main` unless Tanuj says **"merge"**. The main checkout (`D:\Projects\CivicConnect_V2`) is slot 0: database `civicconnect`, Redis DB 0, API port 8000.
- Start a session in its own lane (slots 1 to 4), from the main checkout:
  `.\scripts\dev\new_worktree.ps1 -Name <n> -Branch <b> -Slot <1..4>`
  It fetches, creates `D:\cc\<n>` from `origin/tanuj` on branch `<b>`, copies the root `.env`, creates databases `civicconnect_s<Slot>` and `civicconnect_test_s<Slot>` (postgis + vector), writes `DATABASE_URL`, `TEST_DATABASE_URL`, `REDIS_URL` (`redis://localhost:6379/<Slot>`), `TEST_REDIS_URL` and `API_PORT` (`8000+Slot`) into the lane's `.env` and into the `env` block of its `.claude/settings.local.json` (both gitignored), proves the imports resolve inside the lane, runs `alembic upgrade head` and the seed, and prints the activate / uvicorn / `claude` commands. Start `claude` from `D:\cc\<n>`.
- Remove it when done: `.\scripts\dev\remove_worktree.ps1 -Name <n> -Slot <k>` (removes the worktree, drops both databases, flushes the Redis DB; keeps the branch). Do not create lanes by hand with `git worktree add` (no isolated data, no port).
- **Lane merge protocol** (to finish a lane, from inside it):
  1. `git fetch origin`
  2. `git rebase origin/tanuj`
  3. run the tests (section 7)
  4. `git push origin HEAD:tanuj`
  5. if the push is rejected, fetch and rebase again, re-test, push again.
- Conflicts: `docs/V1_CHANGE_LOG.md` keep both entries (chronological). `backend/openapi.json` and generated files under `packages/api-client`: **regenerate, never merge by hand** (resolve the other conflicts, run `python -m backend.scripts.generate_openapi` and, once the api-client lane has added its generator, that generator; `git add` the output, `git rebase --continue`; a test fails when `openapi.json` is stale).
- **Alembic:** until the final prompt only the **schema step** adds Alembic revisions (keeps one linear history). Other lanes add none; after a rebase `python -m alembic heads` must show exactly one head.
- Do not force-push, rewrite published history or open a PR unless asked.

## 5. Free stack and secrets
- Everything stays free: Gemini + Groq free tiers, local ONNX models, browser Web Speech API. Audit: `docs/FREE_STACK_PROPOSAL.md`. No paid services.
- Secrets live only in the gitignored `.env` (or the process environment). Never print, log, paste or commit values; show key **names** only.
- Model ids come only from env vars (`AI_INTAKE_MODEL`, `AI_ANALYTICS_MODEL`, `AI_COPILOT_MODEL`, `AI_EMBEDDING_MODEL`, `AI_TRANSCRIPTION_MODEL`), copied from `python -m backend.ai_gateway.providers.live_check --list-models`. Never type one from memory or hard-code it.

## 6. Running things (this laptop)
- Run Python as modules with `python -m ...` from the root **of your lane** (`python -m pytest`, `python -m alembic`, `python -m uvicorn`, `python -m ai...`, `python -m backend...`). The cwd then wins on `sys.path`, so a lane imports its own `ai/` and `backend/`, not the editable install (`pip install -e ai`), which points at the main checkout. `python -m backend.scripts.worktree_check` proves it; a test enforces it.
- One shared venv for every lane: `D:\Projects\CivicConnect_V2\.venv` (activate with `& D:\Projects\CivicConnect_V2\.venv\Scripts\Activate.ps1`). **Python 3.13.6** (the project requires 3.11+). Torch is the CUDA **cu128** build (`2.11.0+cu128`; the `cu121` index has no Python 3.13 wheels), RTX 4050 6 GB.
- The C drive is nearly full: **install, build and cache on D**. Caches live in `D:\ml-cache`: pip `D:\ml-cache\pip` (set in `.venv\pip.ini`), `TEMP`/`TMP` `D:\ml-cache\tmp`, `HF_HOME` `D:\ml-cache\hf`, `TORCH_HOME` `D:\ml-cache\torch`. Set `TEMP`/`TMP` in the shell before heavy work (Claude Code ignores them in project settings; lanes get `HF_HOME`/`TORCH_HOME` from their `env` block). Lanes live in `D:\cc`.
- Services (Docker): `civic-db` (image `civicconnect-postgres:local` = PostgreSQL 18.6 + PostGIS 3.6 + pgvector 0.8.6, named volume `civic-pgdata`) on host port **5433** (a host PostgreSQL service owns 5432) and `civic-redis` (`redis:7`) on 6379. (Re)build and start both with `.\scripts\dev\db_up.ps1`. Health: `GET /api/v1/health/ready` (under the API prefix).
- Tests never read `.env` or the lane's `DATABASE_URL`/`REDIS_URL` (root `conftest.py`, `CIVIC_IGNORE_ENV_FILE`); the tests that want a real server read `TEST_DATABASE_URL` / `TEST_REDIS_URL` and skip when they are not set or reachable.

## 7. Quality gates and honest reporting
- Tests: `python -m pytest ai backend -q`. Lint touched files: `python -m ruff check <files>` (root `ruff.toml`: line length 130, py311; some older files already have findings, do not add new ones). Preflight: `python -m ai.training.src.doctor` (names only).
- Add tests for behaviour you add. Match the surrounding code (dense, typed, short docstrings).
- Report results as they are: failing tests, skipped steps and unverified claims are stated plainly. Synthetic data gives **no real-world accuracy claim**; only the team-written gold set is a yardstick, and only M3/M4 are trained so far (see handoff section 4).

## 8. End every task with a report of at most 25 lines
Include: files changed; commands run with results (exact pass/skip/fail counts); failures; what you did **not** verify.
