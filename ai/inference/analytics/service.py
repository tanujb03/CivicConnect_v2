"""AI-5 Analytics explanation layer.

The backend aggregates facts deterministically (SQL/statistics). This layer only
*explains* them. A model's prose is accepted only if every number it contains
appears in the supplied facts and every cited fact id exists; otherwise a
deterministic template explanation is returned (never an ungrounded one).
"""
from __future__ import annotations

from pydantic import BaseModel, ValidationError

from .. import prompts
from ..common import log_event, metadata, provider_ready
from ..errors import AIError
from ..grounding import allowed_numbers, ungrounded_numbers
from ..provider import AIProvider, InputPart
from ..schemas import AnalyticsExplanation, AnalyticsFact, AnalyticsFactSet, AnalyticsHighlight, Citation, W


class _AIHighlight(BaseModel):
    text: str
    fact_ids: list[str]


class _AIExplanation(BaseModel):
    summary: str
    highlights: list[_AIHighlight]


def _fmt(f: AnalyticsFact) -> str:
    unit = f" {f.unit}" if f.unit else ""
    period = f" ({f.period})" if f.period else ""
    return f"{f.metric}: {f.value}{unit}{period}"


class AnalyticsExplainer:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider

    def explain(self, facts: AnalyticsFactSet) -> AnalyticsExplanation:
        by_id = {f.id: f for f in facts.facts}
        if len(by_id) != len(facts.facts):
            raise ValueError("fact ids must be unique")
        warnings: list[str] = []
        fallback: str | None = None
        if provider_ready(self.provider, "analytics"):
            try:
                body = "\n".join(f"[{f.id}] {_fmt(f)}" for f in facts.facts)
                res = self.provider.structured_completion(  # type: ignore[union-attr]
                    task="analytics", instructions=prompts.ANALYTICS_INSTRUCTIONS,
                    parts=[InputPart.of_text(f"Scope: {facts.scope_label}\nFacts:\n{body}")],
                    schema_name="analytics_explanation", json_schema=prompts.ANALYTICS_SCHEMA)
                ai = _AIExplanation(**res.data)
                problem = self._validate(ai, facts, by_id)
                if problem is None:
                    return self._build(ai.summary, [(h.text, h.fact_ids) for h in ai.highlights], by_id, True,
                                       warnings, "provider", res.model, res.latency_ms, None)
                fallback = problem
                warnings.append(W.make(W.EXPLANATION_UNGROUNDED_FALLBACK, problem))
            except (AIError, ValidationError, ValueError, TypeError) as e:
                fallback = f"{type(e).__name__}: {e}"[:200]
                warnings.append(W.make(W.PROVIDER_UNAVAILABLE, "AI explanation unavailable; using deterministic template"))
        else:
            fallback = "provider_not_configured"
        summary = f"{facts.scope_label}: " + "; ".join(_fmt(f) for f in facts.facts[:6]) + "."
        highlights = [(_fmt(f), [f.id]) for f in facts.facts[:8]]
        log_event("analytics_explain", "degraded", reason=(fallback or "")[:60])
        return self._build(summary, highlights, by_id, True, warnings, "rules", None, None, fallback)

    @staticmethod
    def _validate(ai: _AIExplanation, facts: AnalyticsFactSet, by_id: dict[str, AnalyticsFact]) -> str | None:
        allowed = allowed_numbers([facts.scope_label] + [x for f in facts.facts for x in (f.value, f.period, f.unit, f.metric)])
        text = ai.summary + " " + " ".join(h.text for h in ai.highlights)
        bad = ungrounded_numbers(text, allowed)
        if bad:
            return f"numbers not present in facts: {sorted(bad)[:5]}"
        for h in ai.highlights:
            if not h.fact_ids or any(i not in by_id for i in h.fact_ids):
                return "highlight cites unknown or missing fact ids"
        return None

    def _build(self, summary, highlights, by_id, grounded, warnings, source, model, latency, fallback):
        cites: dict[tuple[str, str], Citation] = {}
        for _, ids in highlights:
            for i in ids:
                f = by_id[i]
                if f.ref_id:
                    cites[(f.ref_type, f.ref_id)] = Citation(type=f.ref_type, id=f.ref_id)
        return AnalyticsExplanation(
            summary=summary, highlights=[AnalyticsHighlight(text=t, fact_ids=ids) for t, ids in highlights],
            citations=list(cites.values()), grounded=grounded, warnings=warnings,
            ai_metadata=metadata("analytics_explain", source, provider=self.provider, model=model,  # type: ignore[arg-type]
                                 prompt_version=prompts.ANALYTICS_PROMPT_VERSION,
                                 confidence_basis="numbers_verified_against_facts", fallback_reason=fallback,
                                 latency_ms=latency, input_refs=list(by_id)),
        )
