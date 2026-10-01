"""Output-path guard: external-dataset content must never land where git could pick it up."""
from __future__ import annotations

from pathlib import Path

from .errors import UnsafeOutputPath

REPO_ROOT = Path(__file__).resolve().parents[4]
ALLOWED_IN_REPO = REPO_ROOT / "ai" / "artifacts" / "real_data"


def ensure_safe_output(path: Path, repo_root: Path = REPO_ROOT) -> Path:
    """Allow paths outside the repository, or under ``ai/artifacts/real_data`` (gitignored)."""
    p = Path(path).expanduser().resolve()
    root = Path(repo_root).resolve()
    allowed = root / "ai" / "artifacts" / "real_data"
    try:
        p.relative_to(root)
    except ValueError:
        return p                                   # outside the repo: fine
    try:
        p.relative_to(allowed)
        return p
    except ValueError:
        raise UnsafeOutputPath(
            f"refusing to write external data to {p}: inside the repository but outside {allowed} (gitignored). "
            f"Choose a path outside the repo (e.g. /kaggle/working/real_data) or {allowed}.") from None
