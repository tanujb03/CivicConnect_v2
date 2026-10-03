"""Category suggestion for a case created WITHOUT a category (the citizen skipped it or the client could not decide).

The local text classifier answers: the fine-tuned M6 ONNX model when ``AI_TEXT_ONNX_PATH`` is set, else the B0 fallback (this is what ``AIGateway.ai.classifier`` already
is, see ``ai_gateway.deps.build_ai_service``). A suggestion is applied only when it is confident; otherwise the case stays ``other / unclassified`` for a human to triage,
with a warning. A category given by a human is NEVER touched. Either way the suggestion is stored as an ``AIAnalysis`` row (source, model, confidence, top-k, warnings)
and an INTERNAL timeline event, so the operator sees what the model thought. The case never waits on, or fails because of, this step.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ai.inference.config import AIPolicy
from ai.inference.schemas import W
from backend.models import AIAnalysis, CivicCase
from backend.services import taxonomy as tx
from backend.services.workflow import add_event

log = logging.getLogger("civicconnect.classification")
TASK_TYPE = "classification"
NO_TEXT = "NO_TEXT_TO_CLASSIFY"
CLASSIFIER_FAILED = "CLASSIFIER_FAILED"


@dataclass
class CategorySuggestion:
    category: str = "other"
    subcategory: str | None = "unclassified"
    confidence: float = 0.0                       # probability of the suggested CATEGORY
    subcategory_confidence: float = 0.0
    applied: bool = False                         # True when the case got the suggested category
    source: str = "none"                          # local_m6 | local_b0 | local_classifier | none
    model: str | None = None
    model_version: str | None = None
    label_id: str | None = None                   # the raw top label, before the confidence gate
    threshold: float = 0.55
    top_k: list[tuple[str, float]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def result_json(self) -> dict[str, Any]:
        return {"suggested": {"label_id": self.label_id, "category": self.category if self.applied else None, "applied": self.applied},
                "applied_category": self.category, "applied_subcategory": self.subcategory, "confidence": round(self.confidence, 4),
                "subcategory_confidence": round(self.subcategory_confidence, 4), "threshold": self.threshold, "top_k": [[lid, round(p, 4)] for lid, p in self.top_k],
                "warnings": self.warnings}


def get_classifier():
    """The gateway's local classifier (M6 ONNX or B0), or None. A seam: tests replace this function."""
    try:
        from backend.ai_gateway import get_gateway
        return get_gateway().ai.classifier
    except Exception as e:                                        # noqa: BLE001 (the classifier is an optional extra)
        log.warning("no local classifier available: %s", type(e).__name__)
        return None


def _threshold() -> float:
    try:
        return float(AIPolicy.load().intake.get("low_confidence_threshold", 0.55))
    except Exception:                                             # noqa: BLE001
        return 0.55


def _source_of(clf: Any) -> str:
    name = type(clf).__name__
    return "local_m6" if name == "OnnxTextClassifier" else ("local_b0" if name == "LocalTextClassifier" else "local_classifier")


def suggest(text: str | None) -> CategorySuggestion:
    """Never raises. The result already holds the final decision (``applied``) for this text."""
    s = CategorySuggestion(threshold=_threshold())
    if not (text and text.strip()):
        s.warnings.append(W.make(NO_TEXT, "no title or description to classify; the case stays other/unclassified"))
        return s
    clf = get_classifier()
    if clf is None:
        s.warnings.append(W.make(W.NO_AI_AVAILABLE, "no local text classifier available; the case stays other/unclassified"))
        return s
    s.source, s.model, s.model_version = _source_of(clf), getattr(clf, "model_name", None), str(getattr(clf, "model_version", "") or "") or None
    try:
        pred = clf.predict(text)
    except Exception as e:                                        # noqa: BLE001
        log.warning("classifier failed: %s", type(e).__name__)
        s.warnings.append(W.make(CLASSIFIER_FAILED, f"the local classifier failed ({type(e).__name__}); the case stays other/unclassified"))
        return s
    if getattr(pred, "abstained", False):
        s.warnings.append(W.make(W.LOW_CONFIDENCE, "the classifier abstained; the case stays other/unclassified"))
        return s
    s.label_id, s.confidence, s.subcategory_confidence = pred.label_id, float(pred.category_probability), float(pred.subcategory_probability)
    s.top_k = [(lid, float(p)) for lid, p in (pred.top_k or [])]
    cat = tx.taxonomy().resolve_category(pred.category)
    if cat is None or cat == "other":
        s.warnings.append(W.make(W.LOW_CONFIDENCE, f"the classifier sees no specific category ({pred.label_id}); the case stays other/unclassified"))
        return s
    if s.confidence < s.threshold:
        s.warnings.append(W.make(W.LOW_CONFIDENCE, f"category confidence {s.confidence:.2f} is below {s.threshold:.2f}; the case stays other/unclassified"))
        return s
    s.category, s.applied = cat, True
    if s.subcategory_confidence >= s.threshold and tx.taxonomy().is_valid_pair(cat, pred.subcategory):
        s.subcategory = pred.subcategory
    else:
        s.subcategory = None
        s.warnings.append(W.make(W.LOW_CONFIDENCE, f"subcategory confidence {s.subcategory_confidence:.2f} is below {s.threshold:.2f}; only the category was set"))
    return s


def record(db: Session, case: CivicCase, s: CategorySuggestion) -> AIAnalysis:
    """The suggestion as an ``AIAnalysis`` row + an INTERNAL timeline event (citizens never see either)."""
    row = AIAnalysis(case_id=case.id, actor_id="system", task_type=TASK_TYPE, model=s.model, model_version=s.model_version, source=s.source, degraded=not s.applied,
                     confidence=s.confidence if s.label_id else None, result_json=s.result_json(), extra={"warnings": s.warnings})
    db.add(row)
    db.flush()
    add_event(db, case.id, "CATEGORY_SUGGESTED", actor_id=None, actor_role="AI", visibility="INTERNAL",
              metadata={"applied": s.applied, "category": s.category, "subcategory": s.subcategory, "confidence": round(s.confidence, 4), "source": s.source,
                        "model": s.model, "warnings": s.warnings, "analysis_id": row.id})
    return row
