"""AI-1 intake evaluation over the SYNTHETIC held-out set (Section 57)."""
from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from ai.evaluation import metrics as M
from ai.inference.config import load_taxonomy
from ai.inference.intake.service import IntakeService
from ai.inference.schemas import IntakeRequest


def evaluate(service: IntakeService, rows: Sequence[dict], low_conf_threshold: float | None = None) -> dict:
    t = load_taxonomy()
    thr = low_conf_threshold if low_conf_threshold is not None else service.policy.intake["low_confidence_threshold"]
    recs = []
    for r in rows:
        resp = service.analyze(IntakeRequest(text=r["text"]))
        p = resp.proposal
        recs.append({
            "gold_sub": f"{r['category']}/{r['subcategory']}", "gold_cat": r["category"], "gold_dept": r["department"],
            "gold_sev": r["gold_severity"], "pred_sub": f"{p.category}/{p.subcategory}", "pred_cat": p.category,
            "pred_dept": p.suggested_department, "pred_sev": p.severity, "conf": resp.confidence,
            "degraded": resp.ai_metadata.degraded, "source": resp.ai_metadata.source,
            "lang": r["language"], "code_mixed": r["code_mixed"], "noisy": r["noisy"], "family": r["family_id"],
        })
    n = len(recs)
    sub_ok = [x["gold_sub"] == x["pred_sub"] for x in recs]
    cat_ok = [x["gold_cat"] == x["pred_cat"] for x in recs]
    labels = t.label_ids

    def block(sel: list[dict]) -> dict:
        k = sum(x["gold_sub"] == x["pred_sub"] for x in sel)
        lo, hi = M.wilson_interval(k, len(sel))
        return {"n": len(sel), "subcategory_accuracy": round(k / len(sel), 4) if sel else None,
                "ci95": [round(lo, 3), round(hi, 3)],
                "category_accuracy": round(sum(x["gold_cat"] == x["pred_cat"] for x in sel) / len(sel), 4) if sel else None}

    groups: dict[str, dict[str, list[dict]]] = {"language": defaultdict(list), "code_mixed": defaultdict(list), "noisy": defaultdict(list)}
    for x in recs:
        groups["language"][x["lang"]].append(x)
        groups["code_mixed"][str(x["code_mixed"])].append(x)
        groups["noisy"][str(x["noisy"])].append(x)
    accepted = [x for x in recs if x["conf"] >= thr]
    k_lo, k_hi = M.wilson_interval(sum(sub_ok), n)
    return {
        "task": "intake",
        "n": n,
        "category_accuracy": round(M.accuracy([x["gold_cat"] for x in recs], [x["pred_cat"] for x in recs]), 4),
        "subcategory_accuracy": round(sum(sub_ok) / n, 4),
        "subcategory_accuracy_ci95": [round(k_lo, 3), round(k_hi, 3)],
        "subcategory_macro_f1": round(M.macro_f1([x["gold_sub"] for x in recs], [x["pred_sub"] for x in recs], labels), 4),
        "routing_accuracy_department": round(M.accuracy([x["gold_dept"] for x in recs], [x["pred_dept"] for x in recs]), 4),
        "severity_agreement": round(M.accuracy([x["gold_sev"] for x in recs], [x["pred_sev"] for x in recs]), 4),
        "severity_note": "CIRCULAR on synthetic data: gold severity is derived from the same taxonomy+keyword assumptions as the rules. Measures rule consistency only.",
        "calibration_ece_category": round(M.expected_calibration_error([x["conf"] for x in recs], cat_ok), 4),
        "low_confidence_threshold": thr,
        "coverage_at_threshold": round(len(accepted) / n, 4),
        "category_accuracy_when_accepted": round(sum(x["gold_cat"] == x["pred_cat"] for x in accepted) / len(accepted), 4) if accepted else None,
        "structured_output_validity": 1.0,  # every response is a schema-validated IntakeResponse by construction
        "degraded_rate": round(sum(x["degraded"] for x in recs) / n, 4),
        "sources": dict(M.Counter(x["source"] for x in recs)),
        "by_language": {k: block(v) for k, v in sorted(groups["language"].items())},
        "by_code_mixed": {k: block(v) for k, v in sorted(groups["code_mixed"].items())},
        "by_noisy": {k: block(v) for k, v in sorted(groups["noisy"].items())},
        "top_confusions": M.top_confusions([x["gold_sub"] for x in recs], [x["pred_sub"] for x in recs]),
        "held_out_families": len({x["family"] for x in recs}),
    }
