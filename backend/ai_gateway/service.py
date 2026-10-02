"""AIGateway: §51A AI endpoints on top of ``ai.inference``.

Every public method takes the authenticated ``Actor`` and enforces §51A.18 itself (so HTTP routes and queue workers share one policy),
resolves everything the adapter must not fetch, calls the adapter, persists an ``AIAnalysis`` record and returns the contract shape.
AI never decides: recommendations are stored, human decisions are separate, and a differing decision is audited as an AI override (§12-13, §46).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import ValidationError

from ai.inference.errors import InputLimitExceeded, ToolValidationError
from ai.inference.schemas import (
    ActorContext, CopilotQuery, CopilotScope, FusionCase, FusionRequest, IntakeRequest, Location, ResolutionReviewRequest, TriageRequest, W,
)
from ai.inference.service import AIService
from backend.core.exceptions import CivicConnectException

from .contracts import (
    CopilotQueryRequest, CopilotQueryResponse, FusionAnalyzeResponse, IntakeAnalyzeRequest, IntakeAnalyzeResponse,
    ResolutionReviewIn, ResolutionReviewOut, TriageAnalyzeResponse, TriageDecisionRequest, TriageDecisionResponse, TriageRecommendationOut,
)
from .ports import AIAnalysisStore, AuditSink, CaseRepository, CaseSnapshot, EvidenceResolver

log = logging.getLogger("civicconnect.ai_gateway")

STAFF_ROLES = frozenset({"operator", "department_manager", "ward_officer", "city_admin", "system_admin"})   # "Admin" column of §51A.18
CAPABILITY_ROLES: dict[str, frozenset[str]] = {
    "intake": STAFF_ROLES | {"citizen", "field_worker"},          # "Create case": citizen, field worker, admin; not overlooker
    "fusion": STAFF_ROLES,
    "triage_analyze": STAFF_ROLES,
    "triage_decision": STAFF_ROLES,                                # "Triage decision": admin only
    "copilot": STAFF_ROLES | {"overlooker"},                       # "Run grounded copilot": admin, overlooker (scoped)
    "resolution_review": STAFF_ROLES | {"field_worker"},           # internal hook; citizen-triggered reviews run as SYSTEM_ACTOR
}
OVERRIDE_ACTION = "AI_RECOMMENDATION_OVERRIDDEN"
DECISION_ACTION = "TRIAGE_DECISION_RECORDED"


@dataclass(frozen=True)
class Actor:
    user_id: str
    role: str


SYSTEM_ACTOR = Actor(user_id="system", role="system_admin")      # for queue workers / citizen-triggered hooks; never expose its output to a citizen


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIGateway:
    def __init__(self, ai: AIService, repo: CaseRepository, evidence: EvidenceResolver, analyses: AIAnalysisStore, audit: AuditSink,
                 clock: Callable[[], datetime] = _utcnow):
        self.ai, self.repo, self.evidence, self.analyses, self.audit, self.clock = ai, repo, evidence, analyses, audit, clock

    # ------------------------------------------------------------------------------------------ helpers
    @staticmethod
    def _require(actor: Actor, capability: str) -> None:
        if actor.role not in CAPABILITY_ROLES[capability]:
            raise CivicConnectException("AUTH_FORBIDDEN", "Your role may not use this capability.", 403, {"capability": capability})

    def _case(self, case_id: str) -> CaseSnapshot:
        case = self.repo.get_case(case_id)
        if case is None:
            raise CivicConnectException("CASE_NOT_FOUND", "The requested civic case does not exist.", 404)
        return case

    def _persist(self, task: str, case_id: str | None, actor: Actor, response: Any, confidence: float | None, extra: dict | None = None,
                 exclude: set[str] | None = None) -> str:
        meta = getattr(response, "ai_metadata", None)
        record = {"task_type": task, "case_id": case_id, "actor_id": actor.user_id, "confidence": confidence,
                  "model": getattr(meta, "model", None), "model_version": getattr(meta, "model_version", None),
                  "prompt_version": getattr(meta, "prompt_version", None), "schema_version": getattr(meta, "schema_version", None),
                  "source": getattr(meta, "source", None), "degraded": getattr(meta, "degraded", None),
                  "result_json": response.model_dump(mode="json", exclude=exclude), "created_at": self.clock().isoformat(), **(extra or {})}
        return self.analyses.save(record)

    @staticmethod
    def _meta(response: Any) -> dict[str, Any]:
        return response.ai_metadata.model_dump(mode="json")

    def _dept_out(self, dept_id: str | None) -> tuple[str | None, str | None]:
        """canonical id -> (code shown in the contract, canonical id)."""
        d = self.ai.taxonomy.departments.get(dept_id or "")
        return (d.code, d.id) if d else (dept_id, dept_id)

    @staticmethod
    def _input_error(e: Exception) -> CivicConnectException:
        if isinstance(e, InputLimitExceeded):
            return CivicConnectException("PAYLOAD_TOO_LARGE", str(e), 413)
        if isinstance(e, ValidationError):
            return CivicConnectException("VALIDATION_ERROR", "The request could not be analysed.", 422,
                                         {"errors": [{"loc": list(x["loc"]), "message": x["msg"]} for x in e.errors()]})
        return CivicConnectException("VALIDATION_ERROR", str(e), 422)

    # ------------------------------------------------------------------------------------------ 51A.5 intake
    def intake(self, req: IntakeAnalyzeRequest, actor: Actor) -> IntakeAnalyzeResponse:
        self._require(actor, "intake")
        evidence = []
        for eid in req.evidence_ids:
            ev = self.evidence.resolve(eid, actor.user_id)
            if ev is None:      # unknown OR not visible to this actor: indistinguishable on purpose
                raise CivicConnectException("EVIDENCE_NOT_FOUND", "Evidence not found or not available.", 404, {"evidence_id": eid})
            evidence.append(ev)
        try:
            loc = Location(**req.location.model_dump()) if req.location else None
            res = self.ai.analyze_intake(IntakeRequest(text=req.text, evidence=evidence, language_hint=req.language_hint, location=loc))
        except (ValidationError, InputLimitExceeded, ValueError) as e:
            raise self._input_error(e) from e
        p = res.proposal
        code, canon = self._dept_out(p.suggested_department)
        analysis_id = self._persist("intake", None, actor, res, res.confidence)
        return IntakeAnalyzeResponse(
            proposal={**p.model_dump(mode="json", exclude={"suggested_department", "location"}),
                      "location": p.location.model_dump(mode="json") if p.location else None,
                      "suggested_department": code, "suggested_department_id": canon},
            confidence=res.confidence, warnings=res.warnings, requires_confirmation=True,
            alternatives=[a.model_dump(mode="json") for a in res.alternatives], ai_metadata=self._meta(res), analysis_id=analysis_id)

    # ------------------------------------------------------------------------------------------ 51A.7 fusion
    @staticmethod
    def _fusion_case(c: CaseSnapshot) -> FusionCase:
        return FusionCase(case_id=c.id, category=c.category, subcategory=c.subcategory, latitude=c.latitude, longitude=c.longitude,
                          created_at=c.created_at, text=c.text, embedding=c.embedding, status=c.status)

    def fusion(self, case_id: str, actor: Actor) -> FusionAnalyzeResponse:
        self._require(actor, "fusion")
        case = self._case(case_id)
        bounds = self.ai.fusion.candidate_query_params()
        cands = self.repo.fusion_candidates(case, radius_m=bounds["radius_m"], time_window_days=bounds["time_window_days"],
                                            max_candidates=bounds["max_candidates"], same_category=bool(bounds.get("same_category_required", True)))
        try:
            res = self.ai.analyze_fusion(FusionRequest(subject=self._fusion_case(case), candidates=[self._fusion_case(c) for c in cands],
                                                       embedding_model=case.embedding_model))
        except (ValidationError, InputLimitExceeded, ValueError) as e:
            raise self._input_error(e) from e
        analysis_id = self._persist("fusion", case.id, actor, res, res.matches[0].similarity if res.matches else None,
                                    {"candidates_considered": len(cands)})
        return FusionAnalyzeResponse(matches=[m.model_dump(mode="json") for m in res.matches], recommendation=res.recommendation,
                                     warnings=res.warnings, ai_metadata=self._meta(res), analysis_id=analysis_id)

    # ------------------------------------------------------------------------------------------ 51A.8 triage
    def triage(self, case_id: str, actor: Actor) -> TriageAnalyzeResponse:
        self._require(actor, "triage_analyze")
        case = self._case(case_id)
        age_h = max(0.0, (self.clock() - case.created_at).total_seconds() / 3600.0)
        try:
            res = self.ai.analyze_triage(TriageRequest(
                case_id=case.id, category=case.category, subcategory=case.subcategory, text=case.text, support_count=case.support_count,
                case_age_hours=age_h, recurrence_count=case.recurrence_count, location_tags=case.location_tags, incident_active=case.incident_active))
        except (ValidationError, InputLimitExceeded, ValueError) as e:
            raise self._input_error(e) from e
        r = res.recommendation
        code, canon = self._dept_out(r.department)
        analysis_id = self._persist("triage", case.id, actor, res, res.confidence)
        return TriageAnalyzeResponse(
            recommendation=TriageRecommendationOut(severity=r.severity, priority=r.priority, department=code, department_id=canon,
                                                   sla_hours=r.sla_hours, sla_class=r.sla_class),
            confidence=res.confidence, reasons=res.reasons, warnings=res.warnings, priority_score=res.priority_score,
            score_breakdown=[s.model_dump(mode="json") for s in res.score_breakdown], ai_metadata=self._meta(res), analysis_id=analysis_id)

    def triage_decision(self, case_id: str, req: TriageDecisionRequest, actor: Actor) -> TriageDecisionResponse:
        self._require(actor, "triage_decision")
        case = self._case(case_id)
        dept = self.ai.taxonomy.resolve_department(req.department_id)
        if dept is None:
            raise CivicConnectException("DEPARTMENT_UNKNOWN", "Unknown department.", 422, {"department_id": req.department_id})
        decision = req.model_copy(update={"department_id": dept})
        stored = self.analyses.latest(case.id, "triage")
        rec_out: TriageRecommendationOut | None = None
        overridden: list[str] = []
        if stored:
            rj = stored["result_json"]["recommendation"]
            rec_out = TriageRecommendationOut(severity=rj["severity"], priority=rj["priority"], department=self._dept_out(rj["department"])[0],
                                              department_id=rj["department"], sla_hours=rj["sla_hours"], sla_class=rj.get("sla_class"))
            overridden = [f for f, a, b in (("severity", rj["severity"], decision.severity), ("priority", rj["priority"], decision.priority),
                                            ("department_id", rj["department"], decision.department_id), ("sla_hours", rj["sla_hours"], decision.sla_hours))
                          if a != b]
        now = self.clock()
        self.repo.save_triage_decision(case.id, {**decision.model_dump(mode="json"), "recorded_at": now.isoformat(), "overridden_fields": overridden}, actor.user_id)
        before = rec_out.model_dump(mode="json") if rec_out else None
        emitted = self.audit.emit(actor_id=actor.user_id, action=DECISION_ACTION, entity_type="CIVIC_CASE", entity_id=case.id,
                                  before=before, after=decision.model_dump(mode="json"))
        if overridden:
            emitted = self.audit.emit(actor_id=actor.user_id, action=OVERRIDE_ACTION, entity_type="CIVIC_CASE", entity_id=case.id, before=before,
                                      after={**decision.model_dump(mode="json"), "overridden_fields": overridden,
                                             "analysis_id": stored and stored.get("id")}) and emitted
        return TriageDecisionResponse(case_id=case.id, decision=decision, ai_recommendation=rec_out, overridden_fields=overridden,
                                      overridden=bool(overridden), decided_by=actor.user_id, recorded_at=now, audit_event_emitted=bool(emitted))

    # ------------------------------------------------------------------------------------------ 51A.15 copilot
    def copilot(self, req: CopilotQueryRequest, actor: Actor) -> CopilotQueryResponse:
        self._require(actor, "copilot")
        s = req.scope
        try:
            res = self.ai.copilot_query(CopilotQuery(query=req.query, scope=CopilotScope(ward_id=s.ward_id, department_id=s.department_id, from_=s.from_, until=s.until)),
                                        ActorContext(user_id=actor.user_id, role=actor.role))
        except (ValidationError, InputLimitExceeded, ToolValidationError, ValueError) as e:
            raise self._input_error(e) from e
        self._persist("copilot", None, actor, res, None, {"query_chars": len(req.query)}, exclude={"data", "answer"})
        return CopilotQueryResponse(answer=res.answer, data=res.data, citations=[c.model_dump(mode="json") for c in res.citations],
                                    warnings=res.warnings, tool_calls=[t.model_dump(mode="json") for t in res.tool_calls], ai_metadata=self._meta(res))

    # ------------------------------------------------------------------------------------------ AI-4 resolution review (internal hook)
    def review_resolution(self, case_id: str, req: ResolutionReviewIn, actor: Actor) -> ResolutionReviewOut:
        """Called when a field worker completes a work order (§51A.9) and again when the citizen verifies (§51A.10). Raises flags only: it never
        changes case state, never closes or reopens anything, and the caller must keep its output away from the citizen."""
        self._require(actor, "resolution_review")
        case = self._case(case_id)
        warnings: list[str] = []
        after = []
        for eid in req.resolution_evidence_ids:
            ev = self.evidence.resolve(eid, actor.user_id)
            if ev is None:
                raise CivicConnectException("EVIDENCE_NOT_FOUND", "Evidence not found or not available.", 404, {"evidence_id": eid})
            after.append(ev)
        before = [ev for ev in (self.evidence.resolve(eid, actor.user_id) for eid in case.evidence_ids) if ev is not None]
        if len(before) < len(case.evidence_ids):
            warnings.append(W.make("ORIGINAL_EVIDENCE_UNAVAILABLE", f"{len(case.evidence_ids) - len(before)} original evidence item(s) could not be loaded"))
        try:
            res = self.ai.review_resolution(ResolutionReviewRequest(
                case_id=case.id, category=case.category, subcategory=case.subcategory, description=case.text, original_evidence=before,
                resolution_evidence=after, field_notes=req.notes, citizen_verification=req.citizen_verification, citizen_comment=req.citizen_comment))
        except (ValidationError, InputLimitExceeded, ValueError) as e:
            raise self._input_error(e) from e
        analysis_id = self._persist("resolution", case.id, actor, res, res.confidence)
        return ResolutionReviewOut(
            consistency=res.consistency, unresolved_condition_suspected=res.unresolved_condition_suspected,
            recommend_verification_request=res.recommend_verification_request, confidence=res.confidence, reasons=res.reasons,
            warnings=[*res.warnings, *warnings], ai_metadata=self._meta(res), analysis_id=analysis_id)
