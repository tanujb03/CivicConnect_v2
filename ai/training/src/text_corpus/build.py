"""Merge the generated shards (+ optional template data and the team's gold set) into train / val / test files for the text models (M6, M7).

    python -m ai.training.src.text_corpus.build --shards D:/civic_corpus/shards --out D:/civic_corpus/corpus [--templates ai/artifacts/datasets/synthetic_v1] [--gold gold.csv]

Splits are GROUP-safe: every item of one generation request (same label, language and style) lands on the same side, so near-paraphrases from one request never straddle train and
test. Template rows only ever go to train/val (the original template test families stay the untouched ``intake_eval.v1`` set). The gold set (never seen in
training) is written to ``gold.jsonl`` and used only for evaluation; every gold row carries its provenance (``human`` only when explicitly marked, else ``llm_authored_*`` or ``unspecified``,
see ``ai.evaluation.gold``) and the manifest counts rows by provenance. Everything here is SYNTHETIC or team-authored: none of it is real citizen data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ai.evaluation.gold import count_by_provenance, is_synthetic, label_origin, read_provenance
from ai.inference.config import load_taxonomy
from ai.training.src.data_sources.splits import hash_fraction

from .spec import LANGUAGES
from .validate import clean_items, dedupe_key

GOLD_HEADER = ["text", "label_id", "language", "notes", "provenance"]       # old 4-column CSVs still load (provenance then comes from an llm_authored_* marker in notes, else "unspecified")


def _row(i: int, text: str, lang: str, label_id: str, **extra) -> dict:
    cat, _, sub = label_id.partition("/")
    return {"id": f"{extra.pop('prefix', 'c')}-{i:06d}", "text": text, "language": lang, "category": cat, "subcategory": sub, "label_id": label_id, **extra}


def load_shards(shards: Path) -> tuple[list[dict], dict]:
    rows, stats = [], {"shards": 0, "items_in": 0, "items_kept": 0, "rejected": Counter(), "models": Counter(), "backends": Counter()}
    seen: set[str] = set()
    t = load_taxonomy()
    for f in sorted(shards.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        c = d["cell"]
        label = f"{c['category']}/{c['subcategory']}"
        if not t.is_valid_pair(c["category"], c["subcategory"]) or c["language"] not in LANGUAGES:
            stats["rejected"]["bad_cell"] += 1
            continue
        kept, rej = clean_items(d.get("items", []), c["language"], seen)
        stats["shards"] += 1
        stats["items_in"] += len(d.get("items", []))
        stats["items_kept"] += len(kept)
        stats["rejected"].update(rej)
        stats["models"][d.get("model", "?")] += 1
        stats["backends"][d.get("backend", "?")] += 1
        rows += [{"text": x, "language": c["language"], "label_id": label, "style": c["style"], "group": c["cell_id"], "source": "llm", "backend": d.get("backend"), "model": d.get("model")} for x in kept]
    return rows, stats


def load_templates(dir_: Path, per_label_lang: int, seed: int) -> list[dict]:
    out = []
    for name in ("train.jsonl", "val.jsonl"):
        p = dir_ / name
        if not p.exists():
            continue
        by: dict[tuple, list[dict]] = defaultdict(list)
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                by[(r["category"], r["subcategory"], r["language"])].append(r)
        for (cat, sub, lang), rs in sorted(by.items()):
            rs = sorted(rs, key=lambda r: hash_fraction(r["id"], seed))[:per_label_lang]
            out += [{"text": r["text"], "language": lang, "label_id": f"{cat}/{sub}", "style": "template", "group": f"tpl:{r['family_id']}", "source": "template", "backend": None, "model": None} for r in rs]
    return out


def gold_template(path: Path) -> None:
    """A CSV the team fills in: realistic complaints in their own words, one label each. Keep the example rows' format, delete the examples."""
    t = load_taxonomy()
    labels = "\n".join(f"#   {lid}  =  {s.label.get('en')}" for lid, s in sorted(((f'{s.category_id}/{sid}', s) for sid, s in t.subcategories.items())))
    header = (f"# GOLD TEST SET. Write complaints the way real people would, in YOUR words (not copied from a model). 4-8 per label per language is plenty; more is better.\n"
              f"# Columns: {','.join(GOLD_HEADER)}.  language is one of: en, hi, mr, hi-Latn.  provenance: write `human` for lines YOU wrote; rows left blank are reported as 'unspecified', never as human.  label_id is one of:\n{labels}\n"
              f"# Delete these comment lines and the EXAMPLE rows when done.\n")
    rows = [["EXAMPLE: there is a huge pothole outside the school gate and two bikes have already fallen", "roads/pothole", "en", "example - delete", "human"],
            ["रस्त्यावर मोठा खड्डा पडला आहे, शाळेसमोर", "roads/pothole", "mr", "example - delete", "human"]]
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(header)
        csv.writer(f).writerows([GOLD_HEADER, *rows])


def load_gold(path: Path) -> tuple[list[dict], dict]:
    t = load_taxonomy()
    valid = {f"{s.category_id}/{sid}" for sid, s in t.subcategories.items()}
    text = "\n".join(ln for ln in path.read_text(encoding="utf-8-sig").splitlines() if not ln.lstrip().startswith("#"))
    rows, bad, seen = [], Counter(), set()
    for r in csv.DictReader(text.splitlines()):
        tx, lab, lang = (r.get("text") or "").strip(), (r.get("label_id") or "").strip(), (r.get("language") or "").strip()
        if not tx or tx.upper().startswith("EXAMPLE") or "example - delete" in (r.get("notes") or "").lower():
            bad["example_or_empty"] += 1
        elif lab not in valid:
            bad["unknown_label"] += 1
        elif lang not in LANGUAGES:
            bad["unknown_language"] += 1
        elif dedupe_key(tx) in seen:
            bad["duplicate"] += 1
        else:
            seen.add(dedupe_key(tx))
            prov, how = read_provenance(r.get("provenance"), r.get("notes"))
            rows.append({"text": tx, "language": lang, "label_id": lab, "style": "gold", "group": "gold", "source": "gold", "backend": None, "model": None, "provenance": prov, "provenance_source": how})
    return rows, dict(bad)


def split(rows: list[dict], seed: int, val: float, test: float) -> dict[str, list[dict]]:
    """Group-safe AND stratified: within every (label, language) the generation requests are ordered by a hash and the first ~``test`` / next ~``val`` of them go to test / val
    (at least one each when there are >= 5 requests), so every label stays represented in train. Template rows never enter test."""
    out: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    llm_groups: dict[tuple, set[str]] = defaultdict(set)
    for r in rows:
        if r["source"] == "llm":
            llm_groups[(r["label_id"], r["language"])].add(r["group"])
    side: dict[str, str] = {}
    for groups in llm_groups.values():
        ordered = sorted(groups, key=lambda g: (hash_fraction(g, seed), g))
        n = len(ordered)
        n_test = max(1, round(test * n)) if n >= 5 else 0
        n_val = max(1, round(val * n)) if n >= 5 else 0
        for i, g in enumerate(ordered):
            side[g] = "test" if i < n_test else "val" if i < n_test + n_val else "train"
    for r in rows:
        if r["source"] == "template":
            out["val" if hash_fraction(r["group"], seed) < val else "train"].append(r)
        else:
            out[side[r["group"]]].append(r)
    return out


def build(shards: Path, out: Path, *, templates: Path | None = None, templates_per_label_lang: int = 12, gold: Path | None = None, seed: int = 42, val: float = 0.1, test: float = 0.1) -> dict:
    rows, stats = load_shards(shards)
    if templates:
        rows += load_templates(templates, templates_per_label_lang, seed)
    parts = split(rows, seed, val, test)
    out.mkdir(parents=True, exist_ok=True)
    files, counts = {}, {}
    for name, rs in parts.items():
        rs = [{**_row(i, r["text"], r["language"], r["label_id"], prefix=name), **{k: r[k] for k in ("style", "group", "source", "backend", "model")},
               "synthetic": True, "label_origin": "llm_generated" if r["source"] == "llm" else "synthetic_template"} for i, r in enumerate(rs)]
        body = "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rs) + "\n"
        (out / f"{name}.jsonl").write_text(body, encoding="utf-8")
        files[f"{name}.jsonl"] = hashlib.sha256(body.encode()).hexdigest()
        counts[name] = {"rows": len(rs), "by_language": dict(Counter(r["language"] for r in rs)), "by_source": dict(Counter(r["source"] for r in rs)), "labels": len({r["label_id"] for r in rs})}
    gold_info = None
    if gold:
        g, bad = load_gold(gold)
        body = "\n".join(json.dumps({**_row(i, r["text"], r["language"], r["label_id"], prefix="gold"), "style": "gold", "source": "gold", "provenance": r["provenance"], "provenance_source": r["provenance_source"],
                                     "synthetic": is_synthetic(r["provenance"]), "label_origin": label_origin(r["provenance"])}, ensure_ascii=False, separators=(",", ":")) for i, r in enumerate(g)) + "\n"
        (out / "gold.jsonl").write_text(body, encoding="utf-8")
        files["gold.jsonl"] = hashlib.sha256(body.encode()).hexdigest()
        gold_info = {"rows": len(g), "by_language": dict(Counter(r["language"] for r in g)), "rejected": bad, "labels": len({r["label_id"] for r in g}), **count_by_provenance(g)}
    manifest = {"dataset": "civic_text_corpus", "version": "1", "synthetic": True, "notice": "LLM-written and template text; NOT real citizen reports. gold.jsonl (if present) is evaluation-only text whose rows each carry a provenance (see gold.by_provenance): only rows marked human are team-written.",
                "seed": seed, "fractions": {"val": val, "test": test}, "splits": counts, "generation": {k: (dict(v) if isinstance(v, Counter) else v) for k, v in stats.items()}, "gold": gold_info, "files": files,
                "leakage_rule": "all items of one generation request share a group and stay on one side; templates never enter test; gold is evaluation-only"}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shards", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--templates", type=Path, default=None)
    ap.add_argument("--gold", type=Path, default=None)
    ap.add_argument("--gold-template", type=Path, default=None, help="write an empty gold-set CSV template here and exit")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)
    if a.gold_template:
        gold_template(a.gold_template)
        print("wrote", a.gold_template)
        return 0
    if not (a.shards and a.out):
        ap.error("--shards and --out are required")
    m = build(a.shards, a.out, templates=a.templates, gold=a.gold, seed=a.seed)
    print(json.dumps({k: m[k] for k in ("splits", "gold")}, ensure_ascii=False, indent=1), "\nrejected:", m["generation"]["rejected"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
