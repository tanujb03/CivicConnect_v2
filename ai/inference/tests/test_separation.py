"""Production separation: inference must not depend on training, evaluation, notebooks or ML frameworks."""
import ast
import subprocess
import sys
from pathlib import Path

INFERENCE = Path(__file__).resolve().parents[1]
FORBIDDEN = {"ai.training", "ai.evaluation", "sklearn", "scipy", "torch", "pandas", "transformers", "sentence_transformers",
             "nbformat", "nbclient", "IPython", "ipykernel", "jupyter", "matplotlib", "openai"}


def production_files():
    return [p for p in INFERENCE.rglob("*.py") if "tests" not in p.parts]


def imports(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module if node.level == 0 else "." * node.level + node.module)
    return out


def test_no_production_module_imports_training_or_ml_frameworks():
    assert len(production_files()) > 20
    for f in production_files():
        for name in imports(f):
            root = name.split(".")[0]
            assert name not in FORBIDDEN and root not in FORBIDDEN, f"{f.relative_to(INFERENCE)} imports {name}"
            assert not name.startswith("ai.training") and "training" not in name.split("."), f"{f} imports {name}"


def test_no_notebooks_or_training_assets_inside_inference():
    assert not list(INFERENCE.rglob("*.ipynb"))
    assert not list(INFERENCE.rglob("kaggle*"))


def test_importing_the_service_does_not_load_heavy_dependencies():
    code = ("import sys, ai.inference.service as s; "
            "heavy = [m for m in ('sklearn','scipy','torch','pandas','transformers','ai.training','ai.evaluation') if m in sys.modules]; "
            "print(heavy); sys.exit(1 if heavy else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=INFERENCE.parents[1])
    assert r.returncode == 0, r.stdout + r.stderr


def test_packaging_ships_only_inference():
    import tomllib
    cfg = tomllib.loads((INFERENCE.parent / "pyproject.toml").read_text(encoding="utf-8"))
    pkgs = cfg["tool"]["setuptools"]["packages"]
    assert pkgs and all(p == "ai" or p.startswith("ai.inference") for p in pkgs)
    assert not any("training" in p or "evaluation" in p or "tests" in p for p in pkgs)
    declared = set(cfg["project"]["dependencies"])
    assert {d.split(">")[0] for d in declared} == {"pydantic", "numpy", "httpx"}
