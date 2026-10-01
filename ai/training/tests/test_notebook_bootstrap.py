"""Notebook 05's repository bootstrap: explicit about which code it runs, never silently stale `main`, clear failures (no network: file:// remotes)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import nbformat
import pytest

NB = Path(__file__).resolve().parents[1] / "notebooks" / "05_kaggle_real_data_profile_evaluate.ipynb"
REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED = ["ai/inference/schemas.py", "ai/training/src/data_sources/kaggle_run.py", "ai/training/notebooks/05_kaggle_real_data_profile_evaluate.ipynb"]
BRANCH = "claude/epic-fermat-3qlw5c"


def bootstrap_source() -> str:
    nb = nbformat.read(NB, as_version=4)
    return next(c.source for c in nb.cells if c.cell_type == "code" and "EXECUTING REPO" in c.source)


def git(cwd, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout.strip()


@pytest.fixture(scope="module")
def upstream(tmp_path_factory):
    """A local 'GitHub': a stale main (no notebook 05), the implementation branch, and a tag on an older implementation commit."""
    r = tmp_path_factory.mktemp("upstream")
    git(r, "init", "-q", "-b", "main")
    (r / "README.md").write_text("stale main\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "stale main")
    main_sha = git(r, "rev-parse", "HEAD")
    git(r, "checkout", "-q", "-b", BRANCH)
    for f in REQUIRED:
        (r / f).parent.mkdir(parents=True, exist_ok=True)
        (r / f).write_text("# stub\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "implementation v1")
    git(r, "tag", "impl-v1")
    v1 = git(r, "rev-parse", "HEAD")
    (r / "extra.txt").write_text("later\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "implementation v2")
    return {"url": r.as_uri(), "main": main_sha, "v1": v1, "tip": git(r, "rev-parse", "HEAD")}


def run_cell(tmp_path, env_extra, cwd=None):
    work = tmp_path / "work"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CIVIC_", "KAGGLE_"))}
    env.update({"CIVIC_WORKDIR": str(work), "PYTHONDONTWRITEBYTECODE": "1", **env_extra})
    code = bootstrap_source()
    return subprocess.run([sys.executable, "-c", code], cwd=cwd or tmp_path, env=env, capture_output=True, text=True, timeout=120)


def repo_info(proc):
    out = proc.stdout
    start = out.index("EXECUTING REPO :") + len("EXECUTING REPO :")
    return json.loads(out[start:out.index("\n}", start) + 2])


def test_default_ref_is_the_implementation_branch_never_main_and_the_commit_is_reported(tmp_path, upstream):
    p = run_cell(tmp_path, {"CIVIC_GIT_URL": upstream["url"]})
    assert p.returncode == 0, p.stderr
    info = repo_info(p)
    assert info["requested_ref"] == BRANCH and info["commit"] == upstream["tip"] != upstream["main"]
    assert info["source"].startswith("git checkout") and (Path(info["repo_path"]) / REQUIRED[1]).is_file()
    assert "Pillow" in p.stdout and "no GPU, no TPU, no API credentials" in p.stdout


@pytest.mark.parametrize("ref_key,expect_key", [("v1", "v1"), ("tip", "tip")])
def test_a_commit_sha_can_pin_the_exact_code(tmp_path, upstream, ref_key, expect_key):
    p = run_cell(tmp_path, {"CIVIC_GIT_URL": upstream["url"], "CIVIC_GIT_REF": upstream[ref_key]})
    assert p.returncode == 0, p.stderr
    assert repo_info(p)["commit"] == upstream[expect_key]


def test_a_tag_or_other_branch_ref_works(tmp_path, upstream):
    p = run_cell(tmp_path, {"CIVIC_GIT_URL": upstream["url"], "CIVIC_GIT_REF": "impl-v1"})
    assert p.returncode == 0, p.stderr
    assert repo_info(p)["commit"] == upstream["v1"] and repo_info(p)["requested_ref"] == "impl-v1"


def test_a_stale_main_is_rejected_loudly_not_used(tmp_path, upstream):
    p = run_cell(tmp_path, {"CIVIC_GIT_URL": upstream["url"], "CIVIC_GIT_REF": "main"})
    assert p.returncode != 0 and "STALE" in p.stderr and BRANCH in p.stderr and "EXECUTING REPO" not in p.stdout


def test_an_unreachable_remote_gives_actionable_options_not_a_traceback_blob(tmp_path):
    p = run_cell(tmp_path, {"CIVIC_GIT_URL": (tmp_path / "does-not-exist").as_uri()})
    assert p.returncode != 0 and "Cannot get the repo code" in p.stderr and "Internet On" in p.stderr and "CIVIC_REPO" in p.stderr


def test_local_code_is_preferred_over_cloning(tmp_path):
    p = run_cell(tmp_path, {"CIVIC_GIT_URL": (tmp_path / "must-not-be-used").as_uri()}, cwd=REPO_ROOT / "ai" / "training" / "notebooks")
    assert p.returncode == 0, p.stderr
    info = repo_info(p)
    assert info["source"].startswith("local checkout") and Path(info["repo_path"]).resolve() == REPO_ROOT.resolve()
    assert len(info["commit"]) == 40


def test_explicit_repo_path_is_verified_and_a_wrong_one_is_rejected(tmp_path):
    ok = run_cell(tmp_path, {"CIVIC_REPO": str(REPO_ROOT)})
    assert ok.returncode == 0 and repo_info(ok)["source"].startswith("CIVIC_REPO")
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "README.md").write_text("old", encoding="utf-8")
    bad = run_cell(tmp_path, {"CIVIC_REPO": str(tmp_path / "old")})
    assert bad.returncode != 0 and "STALE or wrong checkout" in bad.stderr


def test_the_bootstrap_never_installs_gpu_or_provider_packages_and_makes_no_dataset_copies():
    src = bootstrap_source()
    assert src.count("copytree") == 1 and "torch" not in src and "openai" not in src.lower() and "sentence" not in src
    assert 'for m in ("numpy", "pydantic", "httpx")' in src
    assert "kaggle datasets download" not in src and "/kaggle/input\").glob(\"**/ai/inference/schemas.py\")" in src
