"""Run the AI evaluation harness and write provenance-labelled reports.

Tracks (see evaluation/provenance.py): ``synthetic`` (default), ``real_holdout``, ``hybrid``.

    # synthetic-only (committed eval sets)
    python -m ai.evaluation.run_eval --task intake --system local --artifact ai/artifacts/civic_text_b0/<version>
    python -m ai.evaluation.run_eval --task fusion --fusion-weights ai/artifacts/fusion_calibrator/<version>
    # real-data tracks (prepared externally with ai.training.src.data_sources.cli; never committed)
    python -m ai.evaluation.run_eval --task taxonomy_coverage --real-data /path/prepared/records.jsonl
    python -m ai.evaluation.run_eval --task fusion --track real_holdout --real-data /path/pairs/pairs.jsonl
    python -m ai.evaluation.run_eval --task fusion --track hybrid --real-data /path/pairs/pairs.jsonl
    python -m ai.evaluation.run_eval --task vision --track real_holdout --real-data /path/rdd/records.jsonl --image-root /path/RDD2022 --system provider

Every report states its dataset provenance and what may (not) be concluded. ``--system provider|hybrid`` needs
credentials; without them the run is SKIPPED (exit 2) and nothing is fabricated.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai.evaluation import eval_fusion, eval_intake, eval_real
from ai.evaluation.provenance import DESCRIPTIVE, TRACKS, TrackError, build_provenance, claims_for, validate_track
from ai.inference.config import ProviderSettings, load_taxonomy
from ai.inference.fusion.scoring import FusionWeights
from ai.inference.intake.service import IntakeService
from ai.inference.local.text_classifier import LocalTextClassifier
from ai.inference.providers.openai_provider import OpenAIProvider

HERE = Path(__file__).parent
DISCLAIMER = ("Read the provenance and claims blocks first. Synthetic results are a regression/ablation signal, NOT real-world accuracy; "
              "real-data results are scoped to the named dataset, holdout and (draft) taxonomy mapping.")


def read_jsonl(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_report(out_dir: Path, name: str, payload: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"disclaimer": DISCLAIMER, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}
    jp = out_dir / f"{name}.json"
    jp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / f"{name}.md").write_text(render_md(name, payload), encoding="utf-8")
    return jp


def _render_results(r: dict) -> list[str]:
    lines: list[str] = []
    task = r["task"]
    if task == "intake":
        lines += ["| metric | value |", "|---|---|"]
        for k in ("category_accuracy", "subcategory_accuracy", "subcategory_macro_f1", "routing_accuracy_department", "calibration_ece_category",
                  "coverage_at_threshold", "category_accuracy_when_accepted", "structured_output_validity", "degraded_rate", "severity_agreement"):
            lines.append(f"| {k} | {r.get(k)} |")
        lines += ["", f"95% CI for subcategory accuracy: {r['subcategory_accuracy_ci95']}", "", f"_{r['severity_note']}_", "",
                  "**By language**", "", "| language | n | subcategory acc | category acc |", "|---|---|---|---|"]
        lines += [f"| {k} | {v['n']} | {v['subcategory_accuracy']} | {v['category_accuracy']} |" for k, v in r["by_language"].items()]
        lines += ["", "**Code-mixed / noisy**", "", "| slice | n | subcategory acc |", "|---|---|---|"]
        lines += [f"| {g[3:]}={k} | {v['n']} | {v['subcategory_accuracy']} |" for g in ("by_code_mixed", "by_noisy") for k, v in r[g].items()]
        lines += ["", "**Top confusions**", ""] + [f"- {c['true']} → {c['pred']} ×{c['count']}" for c in r["top_confusions"]]
    elif task == "fusion":
        lines += ["```json", json.dumps({k: v for k, v in r.items() if k != "by_pair_type"}, indent=2), "```", "",
                  "| pair type | n | mean score | flagged duplicate |", "|---|---|---|---|"]
        lines += [f"| {k} | {v['n']} | {v['mean_score']} | {v['flagged_possible_duplicate']} |" for k, v in r["by_pair_type"].items()]
    else:
        lines += ["```json", json.dumps(r, indent=2, ensure_ascii=False), "```"]
    return lines


def render_md(name: str, p: dict) -> str:
    r, c, prov = p["results"], p["claims"], p["provenance"]
    lines = [f"# Evaluation report — {name}", "", f"> **{c['banner']}**", "", f"> {p['disclaimer']}", "",
             f"- Track: `{p['track']}`  |  Task: `{p['task']}`  |  System: `{p.get('system')}`  |  Created: {p['created_at']}",
             f"- Artifact: `{p.get('artifact')}`", f"- Real-world accuracy claim allowed: **{c['real_world_accuracy_claim_allowed']}**"
             + (f" ({'; '.join(c['reasons'])})" if c.get("reasons") else ""), "",
             "## Dataset provenance", "", "| source | kind | n | licence (verified?) | origin verified? | label origin | text origin | mapping |", "|---|---|---|---|---|---|---|---|"]
    for sid, v in prov["sources"].items():
        lines.append(f"| {sid} | {v['kind']} | {v['n']} | {v.get('license_id')} ({'yes' if v.get('license_verified') else 'NO'}) | "
                     f"{'yes' if v.get('origin_verified', True) else 'NO'} | {v['label_origins']} | {v['text_origins']} | {v.get('mapping_id')} {v.get('mapping_version') or ''} |")
    lines += ["", f"Files: {json.dumps(p.get('datasets', {}))}", ""]
    if "by_provenance" in r:
        lines += ["## Results (separate slices — no pooled headline)", ""]
        for kind, res in r["by_provenance"].items():
            lines += [f"### Slice: {kind}", ""] + _render_results(res) + [""]
        lines += [f"_{r['note']}_"]
    else:
        lines += ["## Results", ""] + _render_results(r)
    lines += ["", "## Limitations",
              "- Hindi/Marathi synthetic text is unreviewed by native speakers; real city data are not Indian-language narratives.",
              "- Single held-out split: wide confidence intervals; use k-fold where available.", ""]
    return "\n".join(lines)


def build_intake_system(system: str, artifact: Path | None):
    clf = LocalTextClassifier.load(artifact) if artifact else None
    provider = None
    if system in ("provider", "hybrid"):
        s = ProviderSettings.from_env()
        if s.api_key is None or not s.model_for("intake"):
            return None, clf, "requires OPENAI_API_KEY and AI_INTAKE_MODEL"
        provider = OpenAIProvider(s)
    if system == "local" and clf is None:
        return None, clf, "--artifact is required for --system local"
    return IntakeService(provider=provider, classifier=clf if system in ("local", "hybrid") else None), clf, None


def _holdout(rows: list[dict]) -> list[dict]:
    keep = [r for r in rows if r.get("split_hint") in ("holdout", "test")]
    if not keep:
        raise TrackError("no rows with split_hint holdout/test: prepare the real data with --holdout-after (311) or --holdout-countries (RDD2022)")
    return keep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", choices=["intake", "fusion", "taxonomy_coverage", "vision", "resolution_time_prior", "recurrence_hotspot", "routing_agreement",
                                       "triage_priority_prior"], required=True)
    ap.add_argument("--track", choices=TRACKS, default=None, help="default: synthetic (descriptive for taxonomy_coverage and the BMC tasks)")
    ap.add_argument("--system", choices=["local", "provider", "hybrid"], default="local")
    ap.add_argument("--artifact", type=Path, default=None, help="B0 classifier artifact dir")
    ap.add_argument("--fusion-weights", type=Path, default=None, help="weights fitted on the lexical semantic signal")
    ap.add_argument("--eval-dir", type=Path, default=HERE / "datasets")
    ap.add_argument("--real-data", type=Path, default=None, help="prepared canonical JSONL (records / pairs / image records)")
    ap.add_argument("--image-root", type=Path, default=None)
    ap.add_argument("--max-per-country", type=int, default=100)
    ap.add_argument("--out", type=Path, default=HERE / "reports")
    ap.add_argument("--name", default=None)
    a = ap.parse_args(argv)
    bmc_tasks = {"resolution_time_prior", "recurrence_hotspot", "routing_agreement", "triage_priority_prior"}
    track = DESCRIPTIVE if (a.task == "taxonomy_coverage" or a.task in bmc_tasks) else (a.track or "synthetic")

    try:
        synth_rows = real_rows = None
        datasets: dict[str, str] = {}
        if track in ("synthetic", "hybrid") and a.task in ("intake", "fusion"):
            f = a.eval_dir / ("intake_eval.v1.jsonl" if a.task == "intake" else "fusion_eval_pairs.v1.jsonl")
            synth_rows, datasets[f.name] = read_jsonl(f), _sha(f)[:16]
        if track in ("real_holdout", "hybrid", DESCRIPTIVE):
            if a.real_data is None:
                raise TrackError(f"--real-data is required for track {track!r}")
            allrows = read_jsonl(a.real_data)
            real_rows = allrows if track == DESCRIPTIVE else _holdout(allrows)
            datasets[a.real_data.name] = _sha(a.real_data)[:16]
        eval_rows = (synth_rows or []) + (real_rows or [])
        prov = build_provenance(eval_rows)
        validate_track(track, prov, task=a.task, rows=real_rows if track == "real_holdout" else None)
        claims = claims_for(track, prov)

        artifact = None
        system = a.system if a.task in ("intake", "vision") else "lexical"
        if a.task == "taxonomy_coverage":
            results = eval_real.evaluate_taxonomy_coverage(real_rows)
        elif a.task in bmc_tasks:
            fn = {"resolution_time_prior": eval_real.evaluate_resolution_time_prior, "recurrence_hotspot": eval_real.evaluate_recurrence_hotspot,
                  "routing_agreement": eval_real.evaluate_routing_agreement, "triage_priority_prior": eval_real.evaluate_triage_priority_prior}[a.task]
            results = fn(real_rows)
            system = "n/a"
            blocked = results.get("leakage", {}).get("blocking")
            if blocked:
                results["WARNING"] = "leakage audit found blocking problems: " + "; ".join(blocked)
        elif a.task == "fusion":
            w = FusionWeights.load(a.fusion_weights) if a.fusion_weights else None
            artifact = f"fusion_weights@{w.version}" if w else "uncalibrated_prior"
            ev = lambda rows: (eval_real.evaluate_real_fusion(rows, w) if rows and rows[0].get("provenance") else eval_fusion.evaluate(rows, w))  # noqa: E731
            if track == "hybrid":
                results = {"by_provenance": {"synthetic": ev(synth_rows), "real_public": ev(real_rows)},
                           "note": "Slices are never pooled: the synthetic slice is not real-world accuracy; the real slice has no semantic signal and agency-assigned labels."}
            else:
                results = ev(synth_rows if track == "synthetic" else real_rows)
        elif a.task == "intake":
            svc, clf, why = build_intake_system(a.system, a.artifact)
            if svc is None:
                print(f"SKIPPED: {why}. No report written.", file=sys.stderr)
                return 2
            artifact = f"{clf.model_name}@{clf.model_version}" if clf else None
            if track == "hybrid":
                results = {"by_provenance": {"synthetic": eval_intake.evaluate(svc, synth_rows), "real_public": eval_real.evaluate_intake_real(svc, real_rows)},
                           "note": "Slices are never pooled."}
            elif track == "synthetic":
                results = eval_intake.evaluate(svc, synth_rows)
            else:
                results = eval_real.evaluate_intake_real(svc, real_rows)
        else:  # vision
            if a.image_root is None:
                raise TrackError("--image-root (external RDD2022 root) is required for the vision task")
            svc, clf, why = build_intake_system("provider", None)
            if svc is None:
                print(f"SKIPPED: {why}. No report written.", file=sys.stderr)
                return 2
            results = eval_real.evaluate_vision(svc, real_rows, a.image_root, max_per_country=a.max_per_country)
            system = "provider"
    except TrackError as e:
        print(f"ERROR (track '{track}'): {e}", file=sys.stderr)
        return 2

    name = a.name or (f"{a.task}_{track}" + (f"_{a.system}" if a.task == "intake" else ""))
    path = write_report(a.out, name, {"track": track, "task": a.task, "system": system, "artifact": artifact, "datasets": datasets,
                                      "taxonomy_version": load_taxonomy().version, "provenance": prov, "claims": claims, "results": results})
    print(f"report: {path}\nbanner: {claims['banner']}")
    flat = results if "by_provenance" not in results else {k: v for k, v in results.items() if not isinstance(v, dict)}
    print(json.dumps({k: v for k, v in flat.items() if not isinstance(v, (dict, list))}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
