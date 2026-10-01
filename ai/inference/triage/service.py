"""AI-3 Triage: AI-assisted severity recommendation + deterministic priority/SLA."""
from __future__ import annotations

from pydantic import BaseModel, ValidationError

from .. import prompts
from ..common import clip01, log_event, metadata, provider_ready
from ..config import AIPolicy, Taxonomy, load_taxonomy, load_triage_rules
from ..errors import AIError
from ..provider import AIProvider, InputPart
from ..schemas import TriageRecommendation, TriageRequest, TriageResponse, W
from .rules import compute_priority, rule_severity


class _AISeverity(BaseModel):
    severity: str
    confidence: float
    reasons: list[str] = []


class TriageService:
    def __init__(self, provider: AIProvider | None = None, taxonomy: Taxonomy | None = None,
                 policy: AIPolicy | None = None, rules: dict | None = None):
        self.provider = provider
        self.taxonomy = taxonomy or load_taxonomy()
        self.policy = policy or AIPolicy.load()
        self.rules = rules or load_triage_rules()

    def analyze(self, req: TriageRequest) -> TriageResponse:
        t = self.taxonomy
        warnings: list[str] = []
        base = rule_severity(t, self.rules, req.category, req.subcategory, req.text)
        severity, source = base.severity, "rules"
        reasons = list(base.reasons)
        confidence = float(self.rules["rules_only_confidence"])
        basis = "rules_only_nominal"
        model = fallback = None
        latency = None
        meta_source = "rules"

        if provider_ready(self.provider, "triage"):
            try:
                res = self.provider.structured_completion(  # type: ignore[union-attr]
                    task="triage", instructions=prompts.triage_instructions(t),
                    parts=[InputPart.of_text(self._case_text(req, base.severity))],
                    schema_name="triage_severity", json_schema=prompts.triage_schema(t),
                )
                ai = _AISeverity(**res.data)
                if ai.severity not in t.severity_rank:
                    raise ValueError("unknown severity")
                model, latency, meta_source = res.model, res.latency_ms, "provider+rules"
                ai_conf = clip01(ai.confidence)
                diff = abs(t.severity_rank[ai.severity] - t.severity_rank[base.severity])
                sub = t.subcategories.get(req.subcategory or "")
                lowers_safety = bool(sub and sub.safety_critical
                                     and t.severity_rank[ai.severity] < t.severity_rank[base.severity])
                if ai_conf < float(self.policy.triage["min_ai_confidence"]):
                    warnings.append(W.make(W.LOW_CONFIDENCE, f"AI severity confidence {ai_conf:.2f} below threshold; using rules"))
                elif diff > int(self.policy.triage["max_severity_divergence"]) or lowers_safety:
                    warnings.append(W.make(W.AI_SEVERITY_DIVERGES,
                                           f"AI suggested {ai.severity} vs rules {base.severity}; kept rules, needs human review"))
                else:
                    severity, source, confidence, basis = ai.severity, "ai", ai_conf, "model_self_reported"
                    reasons.extend(f"AI: {r}" for r in ai.reasons[:4])
                    if ai.severity != base.severity:
                        reasons.append(f"AI adjusted severity {base.severity} -> {ai.severity}")
            except (AIError, ValidationError, ValueError, TypeError) as e:
                fallback = f"{type(e).__name__}: {e}"[:200]
                warnings.append(W.make(W.PROVIDER_UNAVAILABLE, "AI severity unavailable; using deterministic rules"))
        else:
            warnings.append(W.make(W.RULES_ONLY, "no AI provider configured for triage"))
            fallback = "provider_not_configured" if self.provider is None else "triage_model_not_configured"

        pr = compute_priority(
            t, self.rules, severity=severity, support_count=req.support_count,
            case_age_hours=req.case_age_hours, recurrence_count=req.recurrence_count,
            location_tags=set(req.location_tags) | base.tags, incident_active=req.incident_active,
        )
        reasons.append(f"Priority score {pr.score} -> {pr.priority}; SLA {pr.sla_class} ({pr.sla_hours}h)")
        log_event("triage", "ok" if fallback is None else "degraded", severity_source=source)
        return TriageResponse(
            recommendation=TriageRecommendation(
                severity=severity, priority=pr.priority,  # type: ignore[arg-type]
                department=t.department_for(req.category, req.subcategory),
                sla_hours=pr.sla_hours, sla_class=pr.sla_class),  # type: ignore[arg-type]
            confidence=confidence, reasons=reasons, warnings=warnings,
            priority_score=pr.score, score_breakdown=pr.breakdown, severity_source=source,  # type: ignore[arg-type]
            ai_metadata=metadata("triage", meta_source, taxonomy_version=t.version, provider=self.provider,  # type: ignore[arg-type]
                                 model=model, prompt_version=prompts.TRIAGE_PROMPT_VERSION,
                                 confidence_basis=basis, fallback_reason=fallback if source == "rules" and fallback else None,
                                 latency_ms=latency, input_refs=[req.case_id] if req.case_id else []),
        )

    @staticmethod
    def _case_text(req: TriageRequest, rule_sev: str) -> str:
        return (f"Category: {req.category}\nSubcategory: {req.subcategory}\n"
                f"Supporting citizens: {req.support_count}\nRecurrences: {req.recurrence_count}\n"
                f"Baseline severity from rules: {rule_sev}\nDescription:\n{(req.text or '')[:2000]}")
