"""Repository-wide test setup (loaded before any test module, so before ``backend.core.config`` is imported).

Tests must not depend on the developer's ``.env`` (it carries real API keys and e.g. ``AI_GATEWAY_STORE=sql``): ``CIVIC_IGNORE_ENV_FILE`` makes
``backend.core.config.Settings`` and ``backend.ai_gateway.envfile.load_env_file()`` skip it. Tests that exercise the loader pass explicit paths.
"""
import os

os.environ["CIVIC_IGNORE_ENV_FILE"] = "1"
