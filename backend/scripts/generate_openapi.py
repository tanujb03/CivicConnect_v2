"""Writes backend/openapi.json (the shared contract the generated API client is built from).   python -m backend.scripts.generate_openapi"""
import json
from pathlib import Path

from backend.main import app


def generate_openapi_spec() -> Path:
    out = Path(__file__).resolve().parents[1] / "openapi.json"
    out.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")      # LF on every OS (.gitattributes)
    print(f"OpenAPI spec successfully written to {out}")
    return out


if __name__ == "__main__":
    generate_openapi_spec()
