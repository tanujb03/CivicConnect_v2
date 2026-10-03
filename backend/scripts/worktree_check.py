"""Prove that this process imports ``backend`` and ``ai`` (and uses ``alembic``) from the CURRENT checkout, not from another one.

``pip install -e ai`` points at the main checkout, so in a git worktree a plain ``python script.py`` or a bare ``pytest`` could silently import the main checkout's
code. ``python -m <module>`` puts the current directory first on ``sys.path``, which is why every lane command uses ``python -m``.

    python -m backend.scripts.worktree_check          # exit 0 when everything resolves inside the current directory, 1 otherwise
"""
from __future__ import annotations

import importlib
import importlib.metadata
import json
import sys
from pathlib import Path

CHECKED_MODULES = ("backend", "backend.main", "ai", "ai.inference", "ai.training.src.doctor")


def module_locations(root: Path) -> list[tuple[str, Path, bool]]:
    """``(module, file, inside_root)`` for every checked module."""
    root = root.resolve()
    out = []
    for name in CHECKED_MODULES:
        mod = importlib.import_module(name)
        places = [mod.__file__] if getattr(mod, "__file__", None) else list(mod.__path__)       # namespace packages (no __init__.py) only have __path__
        for place in places:
            file = Path(place).resolve()
            out.append((name, file, root in file.parents))
    return out


def editable_install_target() -> str | None:
    """Where ``pip install -e ai`` points (the checkout that would win if the current directory were not first on sys.path)."""
    try:
        text = importlib.metadata.distribution("civicconnect-ai").read_text("direct_url.json")
        return json.loads(text)["url"] if text else None
    except (importlib.metadata.PackageNotFoundError, KeyError, ValueError):
        return None


def main() -> int:
    root = Path.cwd().resolve()
    rows = module_locations(root)
    print(f"checkout (cwd): {root}")
    for name, file, inside in rows:
        print(f"  {'OK ' if inside else 'BAD'} {name:<24} {file}")
    alembic_env = (root / "alembic" / "env.py").resolve()
    print(f"  {'OK ' if alembic_env.is_file() else 'BAD'} alembic migrations        {alembic_env}")
    target = editable_install_target()
    print(f"editable install of ai points at: {target or '(not installed)'}  (ignored while the cwd is first on sys.path: {sys.path[0] in ('', str(root))})")
    return 0 if all(inside for _, _, inside in rows) and alembic_env.is_file() else 1


if __name__ == "__main__":
    raise SystemExit(main())
