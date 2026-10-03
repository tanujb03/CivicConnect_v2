"""Kaggle notebooks: structural checks always; end-to-end execution (nbclient) is marked ``slow``."""
import ast
import re
from pathlib import Path

import nbformat
import pytest

NB_DIR = Path(__file__).resolve().parents[1] / "notebooks"
NOTEBOOKS = sorted(NB_DIR.glob("*.ipynb"))
SECRET_PATTERNS = [re.compile(p) for p in (r"sk-[A-Za-z0-9]{10,}", r"api[_-]?key\s*=\s*['\"][^'\"]{8,}", r"Bearer\s+[A-Za-z0-9._-]{20,}", r"ghp_[A-Za-z0-9]{20,}")]


def test_all_notebooks_exist():
    assert [p.name for p in NOTEBOOKS] == ["01_b0_text_classifier_kaggle.ipynb", "02_b1_encoder_experiment_kaggle.ipynb", "03_fusion_calibration_kaggle.ipynb",
                                           "04_real_data_prepare_evaluate_kaggle.ipynb", "05_kaggle_real_data_profile_evaluate.ipynb",
                                           "06_road_damage_detector_kaggle.ipynb", "07_text_models_m6_m7_kaggle.ipynb"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_is_valid_has_no_outputs_and_no_secrets(path):
    nb = nbformat.read(path, as_version=4)
    nbformat.validate(nb)
    text = path.read_text(encoding="utf-8")
    assert all(c.get("outputs", []) == [] for c in nb.cells if c.cell_type == "code"), "commit notebooks without outputs"
    assert not any(p.search(text) for p in SECRET_PATTERNS), "possible secret in notebook"
    assert "SYNTHETIC" in nb.cells[0].source or "REAL PUBLIC DATA" in nb.cells[0].source


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_code_compiles_and_only_calls_repo_modules(path):
    nb = nbformat.read(path, as_version=4)
    for cell in nb.cells:
        if cell.cell_type == "code":
            ast.parse(cell.source)                          # no magics/shell lines: plain Python only
    joined = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    assert "from ai.training" in joined or "ai.evaluation" in joined


def test_real_data_notebook_has_an_explicit_terms_gate_and_never_bundles_records():
    nb = nbformat.read(NB_DIR / "04_real_data_prepare_evaluate_kaggle.ipynb", as_version=4)
    code = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    assert "ACCEPT_TERMS = False" in code and "ACK_UNVERIFIED_LICENSE = False" in code and "raise SystemExit" in code
    assert "endswith((\"records.jsonl\"" in code and "Internet On" in nb.cells[0].source and "aggregate statistics only" in nb.cells[0].source


def test_kaggle_in_place_notebook_never_downloads_copies_or_calls_a_provider_by_default():
    nb = nbformat.read(NB_DIR / "05_kaggle_real_data_profile_evaluate.ipynb", as_version=4)
    code = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    head = nb.cells[0].source
    assert "REAL PUBLIC DATA" in head and "SYNTHETIC third-party" in head and "in place" in head and "aggregate reports only" in head
    assert "RUN_PROVIDER_EVAL = False" in code
    assert "OWNER_ACCEPTANCE" in code and "accepted as verified on 2026-10-02" in code and "BharatPotHole stays UNVERIFIED" in code and "ACK_UNVERIFIED_LICENSE = True" in code        # recorded owner acceptance, not silent defaults
    assert '"owner_acceptance": OWNER_ACCEPTANCE' in code and "not CC BY-NC-SA 4.0" in code and "not CC BY-NC-SA 4.0" in head
    for link in ("https://www.kaggle.com/competitions/mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024/data", "https://www.kaggle.com/competitions/mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024/rules",
                 "https://data.mendeley.com/datasets/tj2m7zz4rg/2", "https://www.kaggle.com/datasets/aliabdelmenam/rdd-2022", "https://data.mendeley.com/datasets/5ty2wb6gvg/1",
                 "https://www.kaggle.com/datasets/surbhisaswatimohanty/bharatpothole"):
        assert link in head, link
    assert 'DATASETS = ["bmc_mumbai", "mumbai_nashik_road_surface", "rdd2022", "rdd2020", "bharatpothole"]' in code
    assert "CIVIC_GIT_URL" in code and "CIVIC_GIT_REF" in code and "tanuj" in code and "EXECUTING REPO" in code and "**REPO_INFO" in code
    assert "never an implicit `main`" in nb.cells[1].source and "STALE" in code
    assert "kr.run_all(" in code and "kr.plan(" in code and "kr.bundle(" in code
    for forbidden in ("kaggle datasets download", "kaggle competitions download", "figshare", "socrata", "urlretrieve", "requests.get", "wget", "curl"):
        assert forbidden not in code.lower(), forbidden
    assert code.count("copytree") == 1 and "/kaggle/input" in code         # only the (small) repo code is copied, never a dataset
    for ds in ("bmc_mumbai", "mumbai_nashik_road_surface", "rdd2022", "rdd2020", "bharatpothole"):
        assert ds in code and ds in head
    assert "CIVIC_KAGGLE_FIXTURE" in code                                       # CI-only hook on an invented tree


def test_notebooks_keep_logic_out_of_notebooks():
    """Thin notebooks: every notebook delegates to ai.training / ai.evaluation instead of re-implementing them."""
    for path in NOTEBOOKS:
        nb = nbformat.read(path, as_version=4)
        code_lines = sum(len(c.source.splitlines()) for c in nb.cells if c.cell_type == "code")
        limit = 200 if path.name.startswith(("05_", "06_", "07_")) else 160            # 05/06 carry the explicit repo bootstrap + dependency check (it cannot import the repo before it exists)
        assert code_lines < limit, f"{path.name} has {code_lines} code lines; move logic into ai/training"
        assert "LogisticRegression" not in "".join(c.source for c in nb.cells), "model code belongs in ai/training"


def test_production_code_does_not_import_notebooks_or_training():
    inference = Path(__file__).resolve().parents[2] / "inference"
    assert not any("ipynb" in p.read_text(encoding="utf-8") for p in inference.rglob("*.py") if "tests" not in p.parts)


@pytest.mark.slow
@pytest.mark.parametrize("name,env", [
    ("01_b0_text_classifier_kaggle.ipynb", {"CIVIC_SKIP_CV": "1"}),
    ("03_fusion_calibration_kaggle.ipynb", {}),
    ("02_b1_encoder_experiment_kaggle.ipynb", {"CIVIC_B1_FAKE": "1"}),
    ("04_real_data_prepare_evaluate_kaggle.ipynb", {"CIVIC_REAL_FIXTURE": "1"}),
    ("05_kaggle_real_data_profile_evaluate.ipynb", {"CIVIC_KAGGLE_FIXTURE": "1"}),
])
def test_notebook_executes_end_to_end_locally(name, env, tmp_path, monkeypatch):
    """Runs the notebook top to bottom (no Kaggle, no GPU, no network). Notebook 02 uses the CI-only fake encoder."""
    from nbclient import NotebookClient
    if name.startswith("05"):
        pytest.importorskip("PIL", reason="the invented Kaggle tree uses real tiny JPEGs")
    for k, v in {**env, "CIVIC_WORKDIR": str(tmp_path / "work")}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    nb = nbformat.read(NB_DIR / name, as_version=4)
    NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(NB_DIR)}}).execute()
    out = "\n".join(o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []))
    assert "Traceback" not in out
    work = tmp_path / "work"
    if name.startswith("01"):
        assert "parity (numpy vs sklearn)" in out and "bundle:" in out and list(work.glob("civic_b0_handoff_*.zip"))
    if name.startswith("03"):
        assert "SKIPPED provider-embedding calibration" in out and (work / "civic_fusion_weights.zip").exists()
    if name.startswith("02"):
        assert "B1 (" in out and (work / "civic_b1_report.zip").exists()
    if name.startswith("04"):
        import zipfile
        z = zipfile.ZipFile(work / "civic_real_chicago311_aggregates.zip")
        names = z.namelist()
        assert "aggregates only" in out and any(n.endswith("PREPARE_MANIFEST.json") for n in names) and any("fusion_real_holdout.json" in n for n in names)
        assert not any(n.endswith(("records.jsonl", "pairs.jsonl", "raw.jsonl")) for n in names)       # records are never bundled
        assert "licence verified: False" in out.replace("license", "licence")
    if name.startswith("05"):
        import json
        import zipfile
        out_dir = work / "civic_real"
        summary = json.loads((out_dir / "SUMMARY.json").read_text(encoding="utf-8"))
        assert {k: v["status"] for k, v in summary["datasets"].items()} == {"bmc_mumbai": "OK", "mumbai_nashik_road_surface": "OK", "rdd2022": "OK", "rdd2020": "OK", "bharatpothole": "OK"}
        assert all(v["real_world_claim_allowed"] is False for v in summary["datasets"].values())
        names = zipfile.ZipFile(work / "civic_real_aggregates.zip").namelist()
        assert "SUMMARY.md" in names and not any(n.endswith(("records.jsonl", ".jpg", ".csv")) for n in names)
        assert "bundle (aggregates only)" in out and "FOUND    bmc_mumbai" in out and "third_party_synthetic" in out


def test_notebooks_01_to_04_clone_the_project_repo_by_default_on_kaggle():
    """Regression: notebook 02 stopped with 'Cannot find the repo' on a fresh Kaggle session because cloning needed an env var nobody sets."""
    import glob

    import nbformat
    for f in sorted(glob.glob(str(Path(__file__).resolve().parents[1] / "notebooks" / "0[1234]_*.ipynb"))):
        nb = nbformat.read(f, as_version=4)
        src = next(c.source for c in nb.cells if c.cell_type == "code" and "CIVIC_GIT_URL" in c.source)
        assert 'os.environ.get("CIVIC_GIT_URL", "https://github.com/tanujb03/CivicConnect_v2")' in src, f
        assert '"--branch", os.environ.get("CIVIC_GIT_REF", "tanuj")' in src and "turn Internet ON" in src, f
