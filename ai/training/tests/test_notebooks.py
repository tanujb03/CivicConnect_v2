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
                                           "04_real_data_prepare_evaluate_kaggle.ipynb"]


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


def test_notebooks_keep_logic_out_of_notebooks():
    """Thin notebooks: every notebook delegates to ai.training / ai.evaluation instead of re-implementing them."""
    for path in NOTEBOOKS:
        nb = nbformat.read(path, as_version=4)
        code_lines = sum(len(c.source.splitlines()) for c in nb.cells if c.cell_type == "code")
        assert code_lines < 160, f"{path.name} has {code_lines} code lines; move logic into ai/training"
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
])
def test_notebook_executes_end_to_end_locally(name, env, tmp_path, monkeypatch):
    """Runs the notebook top to bottom (no Kaggle, no GPU, no network). Notebook 02 uses the CI-only fake encoder."""
    from nbclient import NotebookClient
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
