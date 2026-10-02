"""Live check of the free AI backends — run it on YOUR machine (or in a session whose network allows the vendors).

    python -m backend.ai_gateway.providers.live_check --list-models          # which model ids does each key offer?
    python -m backend.ai_gateway.providers.live_check                         # structured output, vision, tool calling, embeddings (+ transcription with --audio clip.wav)
    python -m backend.ai_gateway.providers.live_check --audio sample.webm --image photo.jpg

Reads ``.env`` (repository root) and the environment; prints model ids, pass/fail and latency; NEVER prints a key. Exit code 0 only if every attempted check passed.
"""
from __future__ import annotations

import argparse
import io
import math
import sys
import time
from pathlib import Path

from ai.inference.copilot.tools import tool_specs
from ai.inference.errors import AIError
from ai.inference.provider import InputPart
from ai.inference.schemas import EvidenceInput
from backend.ai_gateway.envfile import load_env_file
from backend.ai_gateway.providers.factory import build_backends_from_env, build_provider_from_env

CAT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["category", "language"],
              "properties": {"category": {"type": "string", "enum": ["roads", "water_supply", "sanitation", "street_lighting", "other"]}, "language": {"type": "string"}}}
TEXTS = {"hi": "सड़क पर बड़ा गड्ढा हो गया है, गाड़ियाँ फिसल रही हैं", "mr": "रस्त्यावर मोठा खड्डा पडला आहे, दुचाकी घसरत आहेत", "hi-Latn": "paani ki pipe leak ho rahi hai aur road par paani beh raha hai"}
EXPECT = {"hi": "roads", "mr": "roads", "hi-Latn": "water_supply"}


def _png(color=(120, 120, 120)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, "PNG")
    return buf.getvalue()


def _cos(a, b) -> float:
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0)


def _row(results: list, backend: str, check: str, model: str | None, ok: bool, ms: int, note: str) -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {backend:10s} {check:14s} {str(model or '-')[:34]:34s} {ms:6d} ms  {note}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--audio", type=Path, help="a short voice clip (wav/mp3/webm/m4a), Hindi or Marathi, for the transcription check")
    ap.add_argument("--image", type=Path, help="a photo for the vision check (default: a tiny gray square: plumbing only)")
    a = ap.parse_args(argv)
    names = load_env_file()
    print(f"loaded {len(names)} variable(s) from .env: {', '.join(names) or '-'}")
    backends = build_backends_from_env()
    if not backends:
        print("No backend has a key: set GEMINI_API_KEY and/or GROQ_API_KEY (see .env.example).")
        return 2
    if a.list_models:
        for n, b in backends.items():
            try:
                ids = b.list_models()
                print(f"\n== {n}: {len(ids)} model ids\n  " + "\n  ".join(ids[:120]))
            except AIError as e:
                print(f"\n== {n}: could not list models ({e})")
        print("\nPick ids for AI_INTAKE_MODEL / AI_ANALYTICS_MODEL / AI_TRANSCRIPTION_MODEL (and AI_EMBEDDING_MODEL) and put them in .env.")
        return 0
    prov = build_provider_from_env()
    if prov is None:
        print("Keys found but no model ids configured: run with --list-models, then set AI_*_MODEL in .env.")
        return 2
    results: list[bool] = []
    print()

    def timed(fn):
        t = time.monotonic()
        try:
            return fn(), int((time.monotonic() - t) * 1000), None
        except AIError as e:
            return None, int((time.monotonic() - t) * 1000), f"{type(e).__name__}: {e}"

    if prov.model_for("intake"):
        for lang, text in TEXTS.items():
            r, ms, err = timed(lambda: prov.structured_completion(task="intake", instructions="Classify the civic complaint. Reply with JSON only.", parts=[InputPart.of_text(text)],
                                                                  schema_name="check", json_schema=CAT_SCHEMA))
            ok = r is not None and r.data.get("category") == EXPECT[lang]
            _row(results, prov.routes["intake"].name, f"structured/{lang}", prov.model_for("intake"), ok, ms, err or f"got {r.data}")
        img = a.image.read_bytes() if a.image else _png()
        ev = EvidenceInput(evidence_id="chk", media_type="IMAGE", mime_type="image/jpeg" if a.image else "image/png", data=img)
        r, ms, err = timed(lambda: prov.structured_completion(task="intake", instructions="Describe the main subject of the photo as a civic category. JSON only.",
                                                              parts=[InputPart.of_text("What civic issue does this photo show, if any?"), InputPart.of_image(ev)], schema_name="check", json_schema=CAT_SCHEMA))
        _row(results, prov.routes["intake"].name, "vision", prov.model_for("intake"), r is not None, ms, err or f"got {r.data}")
    else:
        print("SKIP  intake: AI_INTAKE_MODEL not set")
    if prov.model_for("copilot"):
        r, ms, err = timed(lambda: prov.plan_tools(instructions="Use the tools to answer the question. Do not answer directly.", query="show unresolved high severity sanitation cases", tools=tool_specs()))
        _row(results, prov.routes["copilot"].name, "tool-calling", prov.model_for("copilot"), bool(r and r.calls), ms, err or f"calls={[c.name for c in r.calls]}")
    else:
        print("SKIP  copilot: AI_ANALYTICS_MODEL / AI_COPILOT_MODEL not set")
    if prov.model_for("embedding"):
        r, ms, err = timed(lambda: prov.embed(["there is a big pothole near the school", "स्कूल के पास सड़क पर बड़ा गड्ढा है", "the street light is not working"]))
        ok = bool(r) and _cos(r.vectors[0], r.vectors[1]) > _cos(r.vectors[0], r.vectors[2])
        _row(results, prov.routes["embedding"].name, "embeddings", prov.model_for("embedding"), ok, ms, err or f"dim={r.dimension} en~hi={_cos(r.vectors[0], r.vectors[1]):.2f} en~other={_cos(r.vectors[0], r.vectors[2]):.2f}")
    else:
        print("SKIP  embeddings: AI_EMBEDDING_MODEL not set (optional: the local ONNX embedder is preferred)")
    if prov.model_for("transcription") and a.audio:
        ev = EvidenceInput(evidence_id="clip", media_type="AUDIO", mime_type={".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}.get(a.audio.suffix.lower(), "audio/webm"), data=a.audio.read_bytes())
        r, ms, err = timed(lambda: prov.transcribe(ev))
        _row(results, prov.routes["transcription"].name, "transcription", prov.model_for("transcription"), r is not None, ms, err or f"text={r.text[:80]!r} lang={r.language}")
    elif prov.model_for("transcription"):
        print("SKIP  transcription: pass --audio <clip> (record 5 s of Marathi/Hindi on your phone)")
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
