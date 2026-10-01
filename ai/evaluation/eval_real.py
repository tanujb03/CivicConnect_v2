"""Evaluations that only make sense on REAL public data (see training/src/data_sources cards).

* taxonomy coverage  -- how real civic demand lands in taxonomy v1 (and which labels have no real examples)
* real fusion        -- agency-linked duplicate pairs: geo/time/category behaviour on real data
* vision             -- provider vision path on RDD2022 road-damage images (needs a configured provider)
* real intake        -- text classification, ONLY when genuine citizen narrative exists (guarded)
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Sequence

from ai.evaluation import eval_fusion, eval_intake
from ai.evaluation import metrics as M
from ai.evaluation.provenance import TrackError
from ai.inference.config import load_taxonomy
from ai.inference.fusion.scoring import FusionWeights
from ai.inference.intake.service import IntakeService
from ai.inference.schemas import EvidenceInput, IntakeRequest


def evaluate_taxonomy_coverage(records: Sequence[dict]) -> dict:
    t = load_taxonomy()
    status = Counter(r["mapping_status"] for r in records)
    labels = Counter(f"{r['category']}/{r['subcategory']}" for r in records if r.get("subcategory"))
    cats = Counter(r["category"] for r in records if r.get("category"))
    n = max(len(records), 1)
    unmapped = Counter(f"{r.get('source_category')} | {r.get('source_subcategory')}" for r in records if r["mapping_status"] == "unmapped")
    out_scope = Counter(f"{r.get('source_category')}" for r in records if r["mapping_status"] == "out_of_scope")
    return {
        "task": "taxonomy_coverage", "n": len(records),
        "mapping_status_share": {k: round(v / n, 4) for k, v in sorted(status.items())},
        "mapped_to_subcategory_share": round(status.get("exact", 0) / n, 4),
        "mapped_any_share": round((status.get("exact", 0) + status.get("category_only", 0)) / n, 4),
        "category_distribution": dict(cats.most_common()),
        "subcategory_distribution": dict(labels.most_common()),
        "taxonomy_subcategories_with_no_real_examples": sorted(set(t.label_ids) - set(labels)),
        "top_unmapped_source_labels": unmapped.most_common(25),
        "top_out_of_scope_source_labels": out_scope.most_common(15),
        "interpretation": ("Describes demand coverage of OUR taxonomy under a DRAFT mapping. It is not a model-accuracy metric. Subcategories "
                           "with no real examples are where synthetic augmentation (or partner data) is needed."),
    }


def evaluate_real_fusion(pairs: Sequence[dict], weights: FusionWeights | None = None) -> dict:
    res = eval_fusion.evaluate(list(pairs), weights)
    pos = [p for p in pairs if p["label"] == 1]
    res["real_data_notes"] = {
        "positives": len(pos), "negatives": len(pairs) - len(pos),
        "positives_with_differing_category": sum(p["a"]["category"] != p["b"]["category"] for p in pos),
        "semantic_signal": "not evaluated: real 311 rows carry no narrative text (semantic fixed at 0)",
        "label_noise": "negatives are unlinked nearby same-type requests and may include real duplicates the agency never linked",
    }
    res.pop("caveat", None)
    res["caveat"] = ("REAL agency-linked duplicates; geo/time/category signals only. Single city; labels are agency-assigned, not independently verified.")
    return res


def evaluate_intake_real(service: IntakeService, records: Sequence[dict]) -> dict:
    if any(r.get("text_origin") != "citizen_narrative" for r in records):
        raise TrackError("no usable real narrative text (text_origin != citizen_narrative): refusing to score a classifier on category text")
    rows = [{"text": r["text"], "category": r["category"], "subcategory": r["subcategory"], "department": r.get("department"),
             "language": r.get("language")} for r in records if r.get("mapping_status") == "exact"]
    return eval_intake.evaluate(service, rows)


def evaluate_vision(service: IntakeService, records: Sequence[dict], image_root: Path, *, max_per_country: int = 100, seed: int = 0,
                    max_image_bytes: int | None = None) -> dict:
    """Run the provider's multimodal intake on RDD2022 images and compare with the mapped annotations.

    Requires a provider (a text classifier cannot see images). Per-country sampling is stratified and seeded.
    Gold: ``roads/pothole`` in image_labels => pothole present; any road label => road damage present."""
    if service.provider is None:
        raise TrackError("vision evaluation needs a configured provider (OPENAI_API_KEY + AI_INTAKE_MODEL); none available")
    rng = random.Random(seed)
    by_country: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("has_annotation"):
            by_country[r.get("country") or "unknown"].append(r)
    limit = max_image_bytes or service.policy.intake["max_image_bytes"]
    rows, skipped = [], Counter()
    for country, recs in sorted(by_country.items()):
        recs = sorted(recs, key=lambda r: r["record_id"])
        rng.shuffle(recs)
        for r in recs[:max_per_country]:
            p = Path(image_root) / r["image_relpath"]
            if not p.is_file():
                skipped["missing_image"] += 1
                continue
            data = p.read_bytes()
            if len(data) > limit:
                skipped["too_large"] += 1
                continue
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            resp = service.analyze(IntakeRequest(evidence=[EvidenceInput(evidence_id=r["record_id"], media_type="IMAGE", data=data, mime_type=mime)]))
            rows.append({"country": country, "gold_pothole": "roads/pothole" in r["image_labels"], "gold_road": any(l.startswith("roads") for l in r["image_labels"]),
                         "pred_pothole": resp.proposal.category == "roads" and resp.proposal.subcategory == "pothole",
                         "pred_road": resp.proposal.category == "roads", "degraded": resp.ai_metadata.degraded})
    if not rows:
        raise TrackError("no images could be evaluated")
    degraded = sum(x["degraded"] for x in rows) / len(rows)

    def block(sel):
        pot = M.precision_recall_at([float(x["pred_pothole"]) for x in sel], [int(x["gold_pothole"]) for x in sel], 0.5)
        return {"n": len(sel), "pothole_precision": round(pot["precision"], 4), "pothole_recall": round(pot["recall"], 4),
                "pothole_f1": round(pot["f1"], 4), "road_damage_recall": round(sum(x["pred_road"] for x in sel if x["gold_road"]) / max(sum(x["gold_road"] for x in sel), 1), 4),
                "gold_pothole_rate": round(sum(x["gold_pothole"] for x in sel) / len(sel), 4)}

    return {"task": "vision", "n": len(rows), "overall": block(rows), "by_country": {c: block([x for x in rows if x["country"] == c]) for c in sorted({x["country"] for x in rows})},
            "degraded_rate": round(degraded, 4), "skipped": dict(skipped), "max_per_country": max_per_country,
            "validity": "INVALID: provider degraded on >10% of images" if degraded > 0.1 else "ok",
            "caveat": ("Road-survey images, not citizen close-ups; cracks have no taxonomy subcategory so only pothole (D40) is scored at subcategory level; "
                       "random image sampling within a country can leak near-identical road sequences between prompt-tuning and test use.")}
