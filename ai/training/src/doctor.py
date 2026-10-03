"""Preflight for the ML run-book: what is installed, which keys / model ids / artifacts are configured, whether a GPU is usable. Prints names only, never secret values.

    python -m ai.training.src.doctor            # informational (exit 0)
    python -m ai.training.src.doctor --strict   # exit 1 when something the cloud features need is missing
"""
from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CORE = {"numpy": "numpy", "scipy": "scipy", "sklearn": "scikit-learn", "pydantic": "pydantic", "httpx": "httpx", "fastapi": "fastapi"}
SERVING = {"onnxruntime": "onnxruntime", "tokenizers": "tokenizers", "PIL": "pillow"}
TRAINING = {"torch": "torch  (CUDA build: see https://pytorch.org/get-started/locally)", "transformers": "transformers", "onnx": "onnx", "ultralytics": "ultralytics", "nbformat": "nbformat ipykernel jupyter"}
KEYS = ("GEMINI_API_KEY", "GROQ_API_KEY")
MODELS = {"AI_INTAKE_MODEL": "intake / triage / resolution (Gemini Flash: vision + JSON schema)", "AI_ANALYTICS_MODEL": "analytics + copilot + corpus generation (cheap Gemini text model)",
          "AI_TRANSCRIPTION_MODEL": "speech to text (Groq Whisper)"}
ARTIFACTS = {"AI_TEXT_ONNX_PATH": "M6 classifier", "AI_EMBED_ONNX_PATH": "M7 embedder", "AI_VISION_ONNX_PATH": "M5 road-damage detector", "AI_LOCAL_CLASSIFIER_PATH": "B0 fallback",
             "AI_FUSION_WEIGHTS_PATH": "fusion (lexical)", "AI_FUSION_EMBEDDING_WEIGHTS_PATH": "fusion (embeddings)"}


def _have(mod: str) -> str | None:
    try:
        m = importlib.import_module(mod)
        return str(getattr(m, "__version__", "ok"))
    except Exception:       # missing or broken install: both mean "not usable"
        return None


def run(env: dict, repo: Path = REPO) -> tuple[list[tuple[str, str, str]], bool]:
    """Returns ([(status, item, detail)], all_cloud_requirements_met). status: OK | MISSING | WARN | INFO."""
    out: list[tuple[str, str, str]] = []
    ok = True
    v = sys.version_info
    out.append(("OK" if v >= (3, 11) else "MISSING", "python", f"{v.major}.{v.minor}.{v.micro}" + ("" if v >= (3, 11) else "  (3.11+ needed)")))
    for group, mods, need in (("core", CORE, True), ("serving", SERVING, False), ("training", TRAINING, False)):
        for mod, pip in mods.items():
            ver = _have(mod)
            out.append(("OK" if ver else ("MISSING" if need else "WARN"), f"{group}: {mod}", ver or f"pip install {pip}"))
            ok &= bool(ver) or not need
    torch = _have("torch")
    if torch:
        import torch as t
        if t.cuda.is_available():
            p = t.cuda.get_device_properties(0)
            out.append(("OK", "gpu", f"{p.name}, {p.total_memory / 2**30:.1f} GB (cuda {t.version.cuda})"))
        else:
            out.append(("WARN", "gpu", "torch has no CUDA: training would run on CPU (install the CUDA build of torch, or use Kaggle)"))
    env_file = next((p for p in (Path.cwd() / ".env", repo / ".env") if p.is_file()), None)
    out.append(("OK" if env_file else "MISSING", ".env", str(env_file) if env_file else "copy .env.example to .env in the repository root"))
    ok &= env_file is not None
    for k in KEYS:
        out.append(("OK" if env.get(k) else "MISSING", k, "set" if env.get(k) else "empty"))
    ok &= any(env.get(k) for k in KEYS)
    for k, why in MODELS.items():
        out.append(("OK" if env.get(k) else "MISSING", k, "set" if env.get(k) else f"empty ({why}); run live_check --list-models"))
    for k, what in ARTIFACTS.items():
        val = env.get(k)
        if not val:
            out.append(("INFO", k, f"not set ({what})"))
            continue
        pth = Path(val) if Path(val).is_absolute() else repo / val
        out.append(("OK" if pth.exists() else "MISSING", k, f"{what}: {val}" + ("" if pth.exists() else "  (path does not exist)")))
    free = shutil.disk_usage(repo).free / 2**30
    out.append(("OK" if free > 15 else "WARN", "disk", f"{free:.0f} GB free on the repo drive"))
    return out, ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.path.insert(0, str(REPO))
        from backend.ai_gateway.envfile import load_env_file
        load_env_file()
    except Exception as e:      # the doctor must still report when the backend cannot be imported
        print(f"(could not load .env automatically: {type(e).__name__}: {e})")
    rows, ok = run(dict(os.environ))
    for status, item, detail in rows:
        print(f"{status:8s} {item:36s} {detail}")
    print("\nnext: " + ("ready for the cloud-backed steps." if ok else "fix the MISSING lines above (see docs/RUNBOOK_ML.md), then re-run."))
    return 1 if (a.strict and not ok) else 0


if __name__ == "__main__":
    sys.exit(main())
