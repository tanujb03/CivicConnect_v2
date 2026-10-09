"""packages/api-client is generated from backend/openapi.json. This fails when the spec changed and the client was not regenerated (run scripts/dev/gen_api_client.ps1).

No Node needed: the generator records the SHA-256 of the spec (line endings normalised to LF) in packages/api-client/src/schema.sha256.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "backend" / "openapi.json"
PKG = ROOT / "packages" / "api-client"


def test_the_generated_client_matches_the_committed_openapi_spec():
    text = SPEC.read_text(encoding="utf-8").replace("\r\n", "\n")
    recorded = (PKG / "src" / "schema.sha256").read_text(encoding="utf-8").strip()
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == recorded, (
        "backend/openapi.json changed but packages/api-client was not regenerated: run scripts/dev/gen_api_client.ps1 and commit the result")


def test_every_path_of_the_spec_is_in_the_generated_types():
    types = (PKG / "src" / "schema.d.ts").read_text(encoding="utf-8")
    missing = [p for p in json.loads(SPEC.read_text(encoding="utf-8"))["paths"] if f'"{p}"' not in types]
    assert not missing, f"schema.d.ts lacks {missing[:5]}: regenerate the client"


def test_the_package_is_consumable_without_a_build_step():
    pkg = json.loads((PKG / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "@civicconnect/api-client" and pkg["main"] == "./src/index.ts" and {"gen", "typecheck", "build", "test"} <= set(pkg["scripts"])
    assert (PKG / ".gitignore").read_text(encoding="utf-8").split() == ["node_modules/", "dist/"]
