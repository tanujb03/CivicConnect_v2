"""Repository-wide test setup (loaded before any test module, so before ``backend.core.config`` is imported).

Tests must not depend on the developer's ``.env`` (it carries real API keys and e.g. ``AI_GATEWAY_STORE=sql``): ``CIVIC_IGNORE_ENV_FILE`` makes
``backend.core.config.Settings`` and ``backend.ai_gateway.envfile.load_env_file()`` skip it. Tests that exercise the loader pass explicit paths.

The same goes for the per-lane variables of scripts/dev/new_worktree.ps1 (DATABASE_URL, REDIS_URL, API_PORT in the shell or in .claude/settings.local.json): the
unit tests use SQLite and mocks, so a lane's dev database and Redis DB are never touched by them. The tests that want a real server read TEST_DATABASE_URL /
TEST_REDIS_URL explicitly.
"""
import os

os.environ["CIVIC_IGNORE_ENV_FILE"] = "1"
for _name in ("DATABASE_URL", "REDIS_URL"):
    os.environ.pop(_name, None)
