"""Generate the LLM-written training corpus (resumable, quota-aware).

    python -m ai.training.src.text_corpus.generate --out D:/civic_corpus/shards                       # all 27 labels x 4 languages x 9 styles x 12 items
    python -m ai.training.src.text_corpus.generate --out ... --limit 40                                # try 40 requests first
    python -m ai.training.src.text_corpus.generate --out ... --backends en=groq,hi-Latn=groq,hi=gemini,mr=gemini

Needs a configured backend (``.env``: GEMINI_API_KEY and/or GROQ_API_KEY + AI_ANALYTICS_MODEL). One JSON shard per request is written to ``--out``; re-running skips shards that
exist, so a free-tier quota stop is just "run again tomorrow". Generated text is SYNTHETIC and is validated (script, length, PII-looking strings, duplicates) later by ``build``.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable, Mapping

from ai.inference.errors import AIError, ProviderNotConfigured
from ai.inference.provider import InputPart

from .spec import LANGUAGES, SCHEMA, STYLES, Cell, build_cells, prompt_for


def generate_shards(cells: list[Cell], providers: Mapping[str, object], out_dir: Path, *, task: str = "analytics", limit: int | None = None, max_consecutive_failures: int = 6,
                    log: Callable[[str], None] = print) -> dict:
    """``providers`` maps language -> provider (any object with ``structured_completion``). Returns counters; stops early when the backend keeps failing (usually quota)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    done = skipped = failed = 0
    streak = 0
    for c in cells:
        shard = out_dir / f"{c.cell_id}.json"
        if shard.exists():
            skipped += 1
            continue
        if limit is not None and done >= limit:
            break
        prov = providers.get(c.language)
        if prov is None:
            failed += 1
            continue
        system, user = prompt_for(c)
        try:
            res = prov.structured_completion(task=task, instructions=system, parts=[InputPart.of_text(user)], schema_name="complaints", json_schema=SCHEMA)  # type: ignore[attr-defined]
            items = [i.get("text") for i in res.data.get("items", []) if isinstance(i, dict)]
        except ProviderNotConfigured:
            raise
        except AIError as e:
            failed += 1
            streak += 1
            log(f"FAILED {c.label_id} {c.language} {c.style}: {type(e).__name__}: {e}")
            if streak >= max_consecutive_failures:
                log(f"stopping after {streak} consecutive failures (free-tier quota or outage?). Run again later: finished shards are kept.")
                break
            continue
        streak = 0
        shard.write_text(json.dumps({"cell": {"cell_id": c.cell_id, "category": c.category, "subcategory": c.subcategory, "language": c.language, "style": c.style, "k": c.k},
                                     "backend": getattr(prov, "name", "?"), "model": res.model, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items": items},
                                    ensure_ascii=False) + "\n", encoding="utf-8")
        done += 1
        if done % 10 == 0:
            log(f"{done} requests written ({skipped} already present, {failed} failed)")
    return {"written": done, "skipped_existing": skipped, "failed": failed, "total_cells": len(cells)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--k", type=int, default=12, help="complaints per request")
    ap.add_argument("--languages", default=",".join(LANGUAGES))
    ap.add_argument("--styles", default=",".join(STYLES))
    ap.add_argument("--limit", type=int, default=None, help="stop after this many NEW requests")
    ap.add_argument("--backends", default="", help="language=backend overrides, e.g. en=groq,hi-Latn=groq (default: the first keyed backend for every language)")
    ap.add_argument("--task", default="analytics", help="which model id to use: the AI_<TASK>_MODEL of this task (default: the cheap text model)")
    a = ap.parse_args(argv)
    try:
        from backend.ai_gateway.envfile import load_env_file
        from backend.ai_gateway.providers.factory import build_backends_from_env
    except ImportError as e:
        print(f"run this from the repository root with the backend dependencies installed: {e}")
        return 2
    load_env_file()
    backends = build_backends_from_env()
    if not backends:
        print("no backend has a key: put GEMINI_API_KEY (and/or GROQ_API_KEY) and AI_ANALYTICS_MODEL in .env")
        return 2
    first = next(iter(backends.values()))
    langs = [x for x in a.languages.split(",") if x]
    prov = {lang: first for lang in langs}
    for pair in filter(None, a.backends.split(",")):
        lang, _, name = pair.partition("=")
        if lang in prov and name in backends:
            prov[lang] = backends[name]
        else:
            print(f"ignored --backends entry {pair!r} (unknown language or backend without a key)")
    cells = build_cells(languages=langs, styles=[x for x in a.styles.split(",") if x], k=a.k)
    print(f"{len(cells)} requests planned; backends: { {l: getattr(p, 'name', '?') for l, p in prov.items()} }")
    try:
        stats = generate_shards(cells, prov, a.out, task=a.task, limit=a.limit)
    except ProviderNotConfigured as e:
        print(f"{e}\nSet the model id in .env (see: python -m backend.ai_gateway.providers.live_check --list-models).")
        return 2
    print(stats)
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
