"""Claude Code safety hook for the CivicConnect backend session (stdlib only).

Usage (wired in the gitignored ``.claude/settings.local.json``): ``python guard.py <mode>`` with the hook JSON on stdin.
Modes: ``bash`` (PreToolUse Bash), ``edit`` (PreToolUse Edit|Write|NotebookEdit), ``read`` (PreToolUse Read|Grep), ``post`` (PostToolUse Edit|Write).
Exit code 2 with a reason on stderr blocks the call; anything else lets it through. It is a safety net for the plan rules, not a replacement for them.
Role gate: env ``CC_ROLE=backend`` blocks ``apps/``; ``CC_ROLE=frontend`` blocks the backend-owned folders; unset allows everything.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

AUTHOR_EMAIL = "bhidetanuj@gmail.com"
BAD_COMMIT_TEXT = re.compile(r"co-authored-by|generated with|claude\.ai/code", re.I)
ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2]).resolve()
BACKEND_OWNED = ("backend", "alembic", "ai", "infra", "packages/api-client")

# --- bash -------------------------------------------------------------------------------------------------------------------------------------------------------
GIT = r"\bgit(?:\s+(?:-c\s+\S+|-C\s+\S+|--[\w-]+(?:=\S+)?))*\s+"
COMMIT_RE = re.compile(GIT + r"commit\b")
DESTRUCTIVE = [
    (re.compile(GIT + r"push\b[^\n;&|]*(?:\s--force\b|\s-f\b|\s--force-with-lease|\s\+\S)"), "force push is not allowed (plan rule 5)"),
    (re.compile(GIT + r"push\b[^\n;&|]*(?:\s|:|/)(?:main|master)\b(?!-)"), "pushing main is not allowed unless Tanuj says 'merge' (plan rule 5)"),
    (re.compile(GIT + r"reset\b[^\n;&|]*--hard"), "git reset --hard is not allowed"),
    (re.compile(GIT + r"clean\b[^\n;&|]*\s-\w*f"), "git clean -f is not allowed"),
    (re.compile(r"\bdocker[\s-]+compose\b[^\n;&|]*\bdown\b[^\n;&|]*(?:\s-\w*v\b|--volumes)"), "docker compose down -v would delete the data volumes"),
    (re.compile(r"\bdocker\s+volume\s+(?:rm|remove|prune)\b"), "removing docker volumes is not allowed"),
]
ENV_NAME = r"(?<![\w.-])\.env(?:\.(?!example(?![\w.-]))[\w.-]+)?(?![\w.-])"
READERS = r"\b(?:cat|type|more|less|head|tail|sed|awk|grep|egrep|rg|findstr|bat|strings|xxd|od|tee|cp|copy|Get-Content|gc|Select-String|sls|Out-String|ReadAllText|read_text|open)\b"
SHOW_ENV = re.compile(r"\b(?:printenv|Get-ChildItem\s+env:|dir\s+env:|gci\s+env:)", re.I)


def _git_email() -> str:
    try:
        return subprocess.run(["git", "config", "user.email"], capture_output=True, text=True, cwd=ROOT, timeout=10).stdout.strip()
    except Exception:
        return ""


def check_bash(cmd: str) -> str | None:
    if COMMIT_RE.search(cmd):
        text = cmd
        for m in re.finditer(r"(?:-F|--file)[=\s]+(\S+)", cmd):                       # message read from a file
            try:
                text += "\n" + (ROOT / m.group(1).strip("'\"")).read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        if BAD_COMMIT_TEXT.search(text):
            return "commit message must not contain Co-Authored-By, 'Generated with' or claude.ai/code (plan rule 1)"
        if _git_email() != AUTHOR_EMAIL:
            return f"git config user.email must be {AUTHOR_EMAIL} before committing (plan rule 1)"
    for rx, why in DESTRUCTIVE:
        if rx.search(cmd):
            return why
    if (re.search(ENV_NAME, cmd) and re.search(READERS, cmd, re.I)) or SHOW_ENV.search(cmd):
        return "printing .env contents or the process environment is not allowed (plan rule 2); use scripts/dev/env_names.py for names only"
    return None


# --- paths ------------------------------------------------------------------------------------------------------------------------------------------------------
def _rel(path: str) -> str | None:
    try:
        p = Path(path)
        p = p if p.is_absolute() else ROOT / p
        return p.resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError):
        return None                                                                      # outside the project: not our business


def check_edit(path: str) -> str | None:
    role = os.environ.get("CC_ROLE", "").strip().lower()
    rel = _rel(path)
    if not role or rel is None:
        return None
    if role == "backend" and (rel == "apps" or rel.startswith("apps/")):
        return "CC_ROLE=backend may not edit apps/ (the frontend session owns it); write a note in docs/FRONTEND_REQUESTS.md instead"
    if role == "frontend" and any(rel == d or rel.startswith(d + "/") for d in BACKEND_OWNED):
        return "CC_ROLE=frontend may not edit backend-owned folders; add an entry to docs/FRONTEND_REQUESTS.md instead"
    return None


def check_read(path: str) -> str | None:
    name = Path(path).name
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return "reading .env files is blocked (plan rule 2); ask Tanuj, or use scripts/dev/env_names.py for names only"
    return None


# --- post-edit lint ---------------------------------------------------------------------------------------------------------------------------------------------
def post_lint(path: str) -> None:
    rel = _rel(path)
    if not rel or not rel.endswith(".py") or rel.split("/")[0] not in ("backend", "ai", "scripts"):
        return
    exe = ROOT / ".venv" / "Scripts" / "python.exe"
    py = str(exe) if exe.exists() else sys.executable
    try:
        r = subprocess.run([py, "-m", "ruff", "check", rel], capture_output=True, text=True, cwd=ROOT, timeout=60)
    except Exception as exc:                                                              # lint is a convenience, never a blocker
        print(f"ruff not run: {exc}", file=sys.stderr)
        return
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0 and out:
        print(f"ruff findings in {rel}:\n{out}", file=sys.stderr)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": f"ruff findings in {rel} (fix new ones, do not add findings):\n{out[:2000]}"}}))


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))                    # tolerate a BOM (Windows PowerShell pipes add one)
    except Exception:
        return 0
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path") or ti.get("path") or ""
    reason = None
    if mode == "bash":
        reason = check_bash(ti.get("command", ""))
    elif mode == "edit" and path:
        reason = check_edit(path)
    elif mode == "read" and path:
        reason = check_read(path)
    elif mode == "post" and path:
        post_lint(path)
    if reason:
        print(f"BLOCKED by .claude/hooks/guard.py: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
