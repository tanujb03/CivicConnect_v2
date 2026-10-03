"""Lane isolation: every checkout (main or a git worktree) must test and run ITS OWN code, never the editable install of another checkout."""
from pathlib import Path

from backend.scripts.worktree_check import module_locations

REPO = Path(__file__).resolve().parents[2]


def test_backend_and_ai_are_imported_from_the_checkout_that_runs_the_tests():
    rows = module_locations(REPO)
    assert rows and all(inside for _, _, inside in rows), [(n, str(f)) for n, f, inside in rows if not inside]
