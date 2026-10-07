"""Minimal ``.env`` loader for the AI keys and model ids (no python-dotenv dependency).

Looks for ``.env`` in the current directory and then in the repository root; every ``KEY=VALUE`` line that is NOT already in the process environment is exported, so real
environment variables (Kaggle secrets, CI, the cloud session settings) always win over the file. Values are never logged.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        elif val.startswith("#"):          # `KEY=   # comment` means an empty value
            val = ""
        elif " #" in val:
            val = val.split(" #", 1)[0].rstrip()
        if key:
            out[key] = val
    return out


def load_env_file(paths: list[Path] | None = None, environ: dict | None = None) -> list[str]:
    """Export missing variables from the first ``.env`` found; returns the names it set (never the values). With ``CIVIC_IGNORE_ENV_FILE`` set (tests) the default
    search is disabled; explicit ``paths`` are still read."""
    env = os.environ if environ is None else environ
    if paths is None and os.environ.get("CIVIC_IGNORE_ENV_FILE"):
        return []
    for p in paths or [Path.cwd() / ".env", REPO_ROOT / ".env"]:
        if p.is_file():
            set_names = []
            for k, v in parse(p.read_text(encoding="utf-8-sig")).items():
                if k not in env and v != "":
                    env[k] = v
                    set_names.append(k)
            return set_names
    return []
