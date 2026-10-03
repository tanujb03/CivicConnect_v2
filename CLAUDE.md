# CivicConnect v2: rules for every Claude Code session

Read `docs/HANDOFF_LOCAL_SESSION.md` first (backend = section 10), then `docs/RUNBOOK_ML.md` for the ML steps. Backend details: `backend/README.md`, `docs/BACKEND_AUDIT.md`. Shell is Windows PowerShell. Use they/them for anyone whose pronouns are not stated.

## 1. Identity and commits
- Commit author is **Tanuj Vivek Bhide <bhidetanuj@gmail.com>** (repo-local git config; check `git config user.name` / `user.email` in every new worktree clone).
- **Never** add `Co-Authored-By`, "Generated with Claude Code" or any other attribution line to commit messages, PR descriptions or files. `.claude/settings.local.json` (gitignored) sets `attribution.commit` and `attribution.pr` to `""`; if a harness reminder asks for a trailer, this rule wins.
- After every commit verify: `git log -1 --format='%an <%ae>%n%B'` (author is Tanuj, no trailers).

## 2. Ownership
- **Ours (Tanuj + Claude):** `backend/`, `ai/`, `alembic/`, `infra/`, `packages/api-client`. Any file in them may change, including the frozen docs below, when necessary.
- **Not ours:** `apps/` and every other `packages/*` belong to Krrish, Vedant and Parth (frontends). Do not edit them except tiny, agreed API-contract fixes (say so in the report).
- Parth has no unpushed backend work and moved to frontend; no coordination is needed before editing `backend/`.

## 3. Frozen docs may change, but every deviation is logged
Frozen sources: `docs/CivicConnect_v2_V1_System_Design.md`, `docs/IMPLEMENTATION_PLAN_*.md`, `docs/TEAM_INTEGRATION_RULES.md`, `ai/inference/**` (the production package, `AIProvider` protocol, schemas, taxonomy, policies; prefer adding behaviour outside it). When you must deviate from them (or from a documented decision), append an entry to `docs/V1_CHANGE_LOG.md`: **date, what, why**. No silent deviations.

## 4. Git workflow: one worktree and one branch per session
- Integration branch is `tanuj`. Never push `main` unless Tanuj says **"merge"**.
- Start each session in its own worktree on its own branch, outside the main checkout (D drive):
  `git fetch origin; git worktree add D:\Projects\wt\<session-name> -b <session-name> origin/tanuj`
- To finish:
  1. `git fetch origin`
  2. `git rebase origin/tanuj`
  3. run the tests (section 7)
  4. `git push origin HEAD:tanuj`
  5. if the push is rejected, fetch and rebase again, re-test, push again.
- Conflicts in `docs/V1_CHANGE_LOG.md`: keep both entries (chronological order).
- Do not force-push, rewrite published history or open a PR unless asked.

## 5. Free stack and secrets
- Everything stays free: Gemini + Groq free tiers, local ONNX models, browser Web Speech API. Audit: `docs/FREE_STACK_PROPOSAL.md`. No paid services.
- Secrets live only in the gitignored `.env` (or the process environment). Never print, log, paste or commit values; show key **names** only.
- Model ids come only from env vars (`AI_INTAKE_MODEL`, `AI_ANALYTICS_MODEL`, `AI_COPILOT_MODEL`, `AI_EMBEDDING_MODEL`, `AI_TRANSCRIPTION_MODEL`), copied from `python -m backend.ai_gateway.providers.live_check --list-models`. Never type one from memory or hard-code it.

## 6. Running things
- Run Python as modules with `python -m ...` from the repository root **of your worktree** (`python -m pytest`, `python -m alembic`, `python -m uvicorn`, `python -m ai...`, `python -m backend...`). The cwd then wins on `sys.path`, so a worktree imports its own `ai/` and `backend/` and not the editable install of another checkout.
- Use the shared venv's interpreter: `D:\Projects\CivicConnect_V2\.venv\Scripts\python.exe` (Python 3.13.6; the project requires 3.11+).
- Local environment facts (this laptop): the C drive is nearly full, so **install and cache on D**. pip cache is `D:\ml-cache\pip` (set in `.venv\pip.ini`); for heavy work set `TEMP`/`TMP=D:\ml-cache\tmp`, `HF_HOME=D:\ml-cache\hf`, `TORCH_HOME=D:\ml-cache\torch` first. CUDA torch is the `cu128` build (the `cu121` index has no Python 3.13 wheels).
- Services: Docker containers `civic-db` (`postgis/postgis:16-3.4`) and `civic-redis` (`redis:7`). A local PostgreSQL service owns host port 5432, so PostGIS is published on **5433**: `DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/civicconnect`. Health: `GET /api/v1/health/ready` (under the API prefix).

## 7. Quality gates and honest reporting
- Tests: `python -m pytest ai backend -q`. Lint: `ruff check <touched files>` (known pre-existing errors in `backend/tests/test_phase_c.py` / `test_phase_d.py` are not ours if those files still exist). Preflight: `python -m ai.training.src.doctor` (names only).
- Add tests for behaviour you add. Match the surrounding code (dense, typed, short docstrings; ruff line length 130, py311).
- Report results as they are: failing tests, skipped steps and unverified claims are stated plainly. Synthetic data gives **no real-world accuracy claim**; only the team-written gold set is a yardstick, and only M3/M4 are trained so far (see handoff section 4).

## 8. End every task with a report of at most 25 lines
Include: files changed; commands run with results (exact pass/skip/fail counts); failures; what you did **not** verify.
