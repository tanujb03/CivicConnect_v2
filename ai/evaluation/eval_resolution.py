"""AI-4 resolution-intelligence evaluation on the SYNTHETIC planted scenarios (``datasets/resolution_v1``).

    python -m ai.evaluation.eval_resolution [--scenarios <dir>] [--out ai/evaluation/reports] [--name resolution_baseline]

What this measures — and what it cannot:
  * the DETERMINISTIC baseline (no provider): which planted-unresolved cases it flags, how many verification requests it creates, whether missing
    evidence is reported as INSUFFICIENT_EVIDENCE, and that ``autonomous_closure_allowed`` is never true;
  * MONOTONICITY: with an adversarially optimistic scripted "AI" (always CONSISTENT, 0.99) no baseline flag is ever cleared;
  * HOW MUCH OF THE PROBLEM IS OUTSIDE THE BASELINE: unresolved cases revealed only by field-note text or only by the photos (``detectable_by``).
  NOT measured: the multimodal provider comparison. No real or synthetic before/after images exist, so a model's ability to see "still broken" is untested.
All numbers are SYNTHETIC; the planted truth is invented, so they check pipeline behaviour, not real-world accuracy.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from ai.evaluation.provenance import build_provenance, claims_for, validate_track
from ai.evaluation.run_eval import HERE, write_report
from ai.inference.config import load_taxonomy
from ai.inference.providers.fake import FakeProvider
from ai.inference.resolution.service import ResolutionService
from ai.inference.schemas import EvidenceInput, ResolutionReviewRequest

DEFAULT_DIR = HERE / "datasets" / "resolution_v1"
_PLACEHOLDER = b"synthetic-placeholder-not-an-image"


def load(path: Path = DEFAULT_DIR) -> list[dict]:
    return [json.loads(x) for x in (path / "scenarios.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def to_request(s: dict) -> ResolutionReviewRequest:
    def img(i):
        return EvidenceInput(evidence_id=i, media_type="IMAGE", mime_type="image/jpeg", data=_PLACEHOLDER)
    return ResolutionReviewRequest(
        case_id=s["case_id"], category=s["category"], subcategory=s["subcategory"], description=s["description"],
        original_evidence=[img(f"{s['id']}-before")] if s["has_original_photo"] else [],
        resolution_evidence=[img(f"{s['id']}-after")] if s["has_resolution_photo"] else [],
        field_notes=s["field_notes"] or None, citizen_verification=s["citizen_verification"])


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def evaluate(rows: list[dict]) -> dict:
    base = ResolutionService(None)
    optimistic = ResolutionService(FakeProvider(structured={"resolution": {"consistency": "CONSISTENT", "unresolved_condition_suspected": False,
                                                                           "confidence": 0.99, "reasons": ["looks fixed"]}}))
    out = []
    for s in rows:
        req = to_request(s)
        b, o = base.review(req), optimistic.review(req)
        out.append((s, b, o))
    unresolved = [(s, b) for s, b, _ in out if s["truly_unresolved"]]
    fixed = [(s, b) for s, b, _ in out if not s["truly_unresolved"]]
    by_detect = {}
    for kind in ("citizen_signal", "notes_text", "images_only"):
        grp = [b for s, b in unresolved if s["detectable_by"] == kind]
        by_detect[kind] = {"n": len(grp), "flagged_unresolved": _rate(sum(b.unresolved_condition_suspected for b in grp), len(grp)),
                           "verification_requested": _rate(sum(b.recommend_verification_request for b in grp), len(grp))}
    no_after = [b for s, b, _ in out if not s["has_resolution_photo"]]
    violations = sum(1 for _, b, o in out if (b.unresolved_condition_suspected and not o.unresolved_condition_suspected)
                     or (b.recommend_verification_request and not o.recommend_verification_request)
                     or (b.consistency == "INCONSISTENT" and o.consistency != "INCONSISTENT"))
    res = {
        "task": "resolution", "n": len(rows), "n_truly_unresolved": len(unresolved), "mode": "deterministic baseline (no provider)",
        "unresolved_flag_recall": _rate(sum(b.unresolved_condition_suspected for _, b in unresolved), len(unresolved)),
        "unresolved_flag_false_positive_rate": _rate(sum(b.unresolved_condition_suspected for _, b in fixed), len(fixed)),
        "verification_request_recall_of_unresolved": _rate(sum(b.recommend_verification_request for _, b in unresolved), len(unresolved)),
        "verification_request_rate_when_truly_fixed": _rate(sum(b.recommend_verification_request for _, b in fixed), len(fixed)),
        "verification_request_rate_when_truly_fixed_and_citizen_confirmed": _rate(
            sum(b.recommend_verification_request for s, b in fixed if s["citizen_verification"] == "YES"), sum(s["citizen_verification"] == "YES" for s, _ in fixed)),
        "insufficient_evidence_correct_when_no_resolution_photo": _rate(sum(b.consistency == "INSUFFICIENT_EVIDENCE" for b in no_after), len(no_after)),
        "autonomous_closure_allowed_any": any(b.autonomous_closure_allowed for _, b, _ in out),
        "monotonic_violations_with_optimistic_ai": violations,
        "unresolved_by_detectable_signal": by_detect,
        "outside_deterministic_baseline": {
            "share_of_unresolved_only_in_field_notes": _rate(by_detect["notes_text"]["n"], len(unresolved)),
            "share_of_unresolved_only_visible_in_photos": _rate(by_detect["images_only"]["n"], len(unresolved)),
            "meaning": "The baseline never reads note text or pixels. These cases are caught only by the citizen-verification step (every unconfirmed case gets a request) "
                       "or by the multimodal provider path, which is NOT evaluated here (no before/after images exist)."},
        "archetypes": dict(sorted(Counter(s["archetype"] for s, _, _ in out).items())),
        "not_evaluated": ["multimodal provider comparison (needs real before/after images + a configured model)", "field-note understanding by a language model"],
    }
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenarios", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--out", type=Path, default=HERE / "reports")
    ap.add_argument("--name", default="resolution_baseline")
    a = ap.parse_args(argv)
    rows = load(a.scenarios)
    prov = build_provenance([{"synthetic": True}] * len(rows))
    validate_track("synthetic", prov)
    claims = claims_for("synthetic", prov)
    p = write_report(a.out, a.name, {"track": "synthetic", "task": "resolution", "system": "rules", "artifact": None, "datasets": {a.scenarios.name: "resolution-scenarios/1"},
                                     "taxonomy_version": load_taxonomy().version, "provenance": prov, "claims": claims, "results": evaluate(rows)})
    print("report:", p, "\nbanner:", claims["banner"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
