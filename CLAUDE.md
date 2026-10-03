# CivicConnect v2: notes for Claude Code

Working on the **AI/ML track** (owner: Tanuj). **Read `docs/HANDOFF_LOCAL_SESSION.md` first**, then follow `docs/RUNBOOK_ML.md`.

- Branch `tanuj`; never push to `main` unless the owner says "merge".
- Frozen (never edit): `docs/CivicConnect_v2_V1_System_Design.md`, `docs/IMPLEMENTATION_PLAN_*.md`, `docs/TEAM_INTEGRATION_RULES.md`, `ai/inference/**`. Frontends (`apps/`, `packages/`) are out of scope.
- Everything must stay free (Gemini + Groq free tiers, local ONNX models). Secrets live only in the gitignored `.env`; never print or commit values.
- Model ids come only from env vars, copied from `python -m backend.ai_gateway.providers.live_check --list-models`.
- Tests: `python -m pytest ai backend -q`. Lint: `ruff check <touched files>`. Preflight: `python -m ai.training.src.doctor`.
- Report results honestly: synthetic data gives no real-world accuracy claim.
