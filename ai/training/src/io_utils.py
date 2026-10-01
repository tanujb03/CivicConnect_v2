"""Small IO helpers for training scripts (kept dependency-free)."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path
from typing import Iterable, Iterator


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def iter_jsonl(path: Path) -> Iterator[dict]:
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha(cwd: Path | None = None) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def runtime_info() -> dict:
    import os
    info = {"python": platform.python_version(), "platform": platform.platform(),
            "kaggle": bool(os.environ.get("KAGGLE_KERNEL_RUN_TYPE"))}
    for mod in ("numpy", "sklearn", "scipy", "pydantic"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001 - informational only
            info[mod] = None
    return info
