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

from ai.inference.common import provider_ready
from ai.inference.errors import InputLimitExceeded, ToolPermissionDenied, ToolValidationError
from ai.inference.schemas import (
    ActorContext, CopilotQuery, CopilotScope, FusionCase, FusionRequest, IntakeRequest, Location, ResolutionReviewRequest, TriageRequest, W,
)
from ai.inference.service import AIService
from backend.core.exceptions import CivicConnectException

from .contracts import (
    AnalyticsExplainRequest, AnalyticsExplainResponse, CopilotQueryRequest, CopilotQueryResponse, FusionAnalyzeResponse, IntakeAnalyzeRequest, IntakeAnalyzeResponse,
    ResolutionReviewIn, ResolutionReviewOut, TriageAnalyzeResponse, TriageDecisionRequest, TriageDecisionResponse, TriageRecommendationOut,
)
from .ports import AIAnalysisStore, AnalyticsFactSource, AuditSink, CaseRepository, CaseSnapshot, EvidenceResolver, ImageAnalyzer
from . import localization, transcription
from .vision import summarize

log = logging.getLogger("civicconnect.ai_gateway")

STAFF_ROLES = frozenset({"operator", "department_manager", "ward_officer", "city_admin", "system_admin"})   # "Admin" column of §51A.18
CAPABILITY_ROLES: dict[str, frozenset[str]] = {
    "intake": STAFF_ROLES | {"citizen", "field_worker"},          # "Create case": citizen, field worker, admin; not overlooker
    "fusion": STAFF_ROLES,
    "triage_analyze": STAFF_ROLES,
    "triage_decision": STAFF_ROLES,                                # "Triage decision": admin only
    "copilot": STAFF_ROLES | {"overlooker"},                       # "Run grounded copilot": admin, overlooker (scoped)
    "analytics_explain": STAFF_ROLES | {"overlooker"},             # "View city analytics": admin, overlooker (aggregates only)
    "resolution_review": STAFF_ROLES | {"field_worker"},           # internal hook; citizen-triggered reviews run as SYSTEM_ACTOR
    "transcribe": STAFF_ROLES,                                     # queue jobs only (SYSTEM_ACTOR); no HTTP route
    "embed": STAFF_ROLES,                                          # queue jobs only (SYSTEM_ACTOR); no HTTP route
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
                 clock: Callable[[], datetime] = _utcnow, facts: AnalyticsFactSource | None = None, vision: ImageAnalyzer | None = None, embedder=None):
        self.ai, self.repo, self.evidence, self.analyses, self.audit, self.clock = ai, repo, evidence, analyses, audit, clock
        self.facts = facts
        self.vision = vision
        self.embedder = embedder              # OnnxEmbedder (M7): local multilingual embeddings for duplicate detection

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
        speech_warnings: list[str] = []         # AUDIO: speech-to-text first (Groq Whisper via the provider), so the transcript + language are stored and the adapter reuses the text
        speech = transcription.transcribe_audio(self.ai.provider, evidence, req.language_hint, speech_warnings, save=self._save_transcript)
        try:
            loc = Location(**req.location.model_dump()) if req.location else None
            res = self.ai.analyze_intake(IntakeRequest(text=req.text, evidence=transcription.usable_for_adapter(evidence), language_hint=req.language_hint, location=loc))
        except (ValidationError, InputLimitExceeded, ValueError) as e:
            raise self._input_error(e) from e
        proposal = res.proposal.model_dump(mode="json", exclude={"suggested_department", "location"})
        proposal["location"] = res.proposal.location.model_dump(mode="json") if res.proposal.location else None
        warnings = [*res.warnings, *speech_warnings]
        confidence, meta = res.confidence, self._meta(res)
        proposal["evidence_refs"] = list(dict.fromkeys([*proposal.get("evidence_refs", []), *(e.evidence_id for e in evidence)]))
        dept = res.proposal.suggested_department
        analyses = self._analyze_images(evidence, warnings)
        best = summarize(analyses)
        if best:
            no_ai = res.ai_metadata.source == "none"
            weak = proposal["category"] == "other" or res.confidence < float(self.ai.policy.intake.get("low_confidence_threshold", 0.55))
            if no_ai or weak:       # nothing else answered with confidence: the local image model PROPOSES (the citizen still confirms)
                proposal.update(category=best["category"], subcategory=best["subcategory"], title=f"{best['label'].capitalize()} in photo")
                proposal["severity"] = self._rule_severity(best["category"], best["subcategory"])
                dept = self.ai.taxonomy.department_for(best["category"], best["subcategory"])
                confidence = round(min(0.8, best["confidence"]), 4)
                proposal["reasons"] = [*proposal.get("reasons", []), f"Local road-damage model: {best['label']} detected ({best['confidence']:.2f})"][:8]
                warnings.append(W.make("LOCAL_VISION_USED", f"{best['label']} detected in the photo by the local model; no stronger AI answer was available"))
                meta = {**meta, "local_vision": {"used_for_proposal": True, "model": analyses[0].model}}
            elif best["confidence"] >= 0.7 and proposal["category"] != best["category"]:
                warnings.append(W.make("VISION_DISAGREES", f"local image model sees {best['label']} (roads) but the proposal says {proposal['category']}: please check the photo"))
        code, canon = self._dept_out(dept)
        proposal.update(suggested_department=code, suggested_department_id=canon)
        local = localization.localize_proposal(self.ai.provider, language=proposal.get("language"), title=proposal["title"], description=proposal["description"],
                                               original_text="\n".join(x for x in (req.text, proposal.get("transcript")) if x), warnings=warnings,
                                               provider_answered=str(res.ai_metadata.source).startswith("provider") and "local_vision" not in meta)
        if local:                                                                    # presentation only: the canonical English fields above are untouched
            proposal.update({k: local[k] for k in ("title_local", "summary_local", "local_language")})
        images = [a.as_dict() for a in analyses]
        extra: dict[str, Any] = {"image_analysis": images} if images else {}
        if speech:
            extra["transcription"] = transcription.summarize(speech)                 # transcript(s), detected language, model, status per clip
            extra["detected_language"] = extra["transcription"]["detected_language"]
        if local:
            extra["localization"] = local
        analysis_id = self._persist("intake", None, actor, res, confidence, extra or None)
        return IntakeAnalyzeResponse(proposal=proposal, confidence=confidence, warnings=warnings, requires_confirmation=True,
                                     alternatives=[a.model_dump(mode="json") for a in res.alternatives], ai_metadata=meta, analysis_id=analysis_id, image_analysis=images)

    def _save_transcript(self, evidence_id: str, text: str, language: str | None) -> None:
        save = getattr(self.evidence, "save_transcript", None)                 # optional port
        if save is not None:
            save(evidence_id, text, language)

    # ------------------------------------------------------------------------------------------ audio transcription job (civic:ai_jobs)
    def transcribe_case(self, case_id: str, actor: Actor) -> dict[str, Any]:
        """Worker entry: transcribe the case's report audio that has no transcript yet. Stores the transcript on the evidence and ONE ``transcription`` AIAnalysis (transcripts,
        detected language, warnings). A missing/unavailable provider degrades to a visible warning on that analysis; nothing here raises for provider reasons."""
        self._require(actor, "transcribe")
        case = self._case(case_id)
        pending = getattr(self.evidence, "pending_audio", None)
        ids = pending(case.id) if pending is not None else []
        if not ids:
            return {"status": "nothing_to_do", "warnings": []}
        evidence = [ev for ev in (self.evidence.resolve(i, actor.user_id) for i in ids) if ev is not None]
        warnings: list[str] = []
        if len(evidence) < len(ids):
            warnings.append(W.make(W.AUDIO_NOT_TRANSCRIBED, f"{len(ids) - len(evidence)} audio clip(s) could not be loaded"))
        records = transcription.transcribe_audio(self.ai.provider, evidence, None, warnings, save=self._save_transcript)
        summary = transcription.summarize(records)
        ok = [r for r in records if r["status"] == "ok"]
        analysis_id = self.analyses.save({"task_type": "transcription", "case_id": case.id, "actor_id": actor.user_id, "confidence": None, "model": next((r["model"] for r in ok), None),
                                          "source": "provider" if ok else "none", "degraded": bool(warnings), "created_at": self.clock().isoformat(),
                                          "result_json": {**summary, "warnings": warnings}, "detected_language": summary["detected_language"], "warnings": warnings})
        return {"status": "ok" if ok else "unavailable", "transcribed": len(ok), "warnings": warnings, "detected_language": summary["detected_language"], "analysis_id": analysis_id}

    def _analyze_images(self, evidence: list, warnings: list[str]) -> list:
        out = []
        if self.vision is None:
            return out
        for ev in evidence:
            try:
                a = self.vision.analyze(ev)
            except Exception as e:        # the local model is an optional extra: its failure must never fail an intake
                warnings.append(W.make("IMAGE_MODEL_FAILED", f"local image model failed on {ev.evidence_id}: {type(e).__name__}"))
                log.warning("local vision failed: %s", type(e).__name__)
                continue
            if a is not None:
                out.append(a)
        return out

    def _rule_severity(self, category: str, subcategory: str | None) -> str:
        from ai.inference.triage.rules import rule_severity
        return rule_severity(self.ai.taxonomy, self.ai.triage.rules, category, subcategory, None).severity

    # ------------------------------------------------------------------------------------------ 51A.7 fusion
    @staticmethod
    def _fusion_case(c: CaseSnapshot) -> FusionCase:
        return FusionCase(case_id=c.id, category=c.category, subcategory=c.subcategory, latitude=c.latitude, longitude=c.longitude,
                          created_at=c.created_at, text=c.text, embedding=c.embedding, status=c.status)

    def _embed_cases(self, subject: FusionCase, candidates: list[FusionCase], stored_model: str | None) -> str | None:
        """Make every vector the adapter compares come from ONE model, and return that model's tag. The repository already dropped candidate vectors that do not match the
        subject's stored model / dimension. Subject with a stored vector: that model is kept and the local embedder only fills gaps if it IS that model. Subject without one:
        the local embedder embeds subject and candidates together. A failure leaves vectors empty: the adapter then falls back to the lexical signal visibly."""
        if subject.embedding is not None:
            if self.embedder is None or self.embedder.tag != stored_model:
                return stored_model
            todo = [c for c in candidates if c.embedding is None and c.text]
        else:
            todo = [c for c in (subject, *candidates) if c.text]
        if not todo:
            return self.embedder.tag if subject.embedding is not None else stored_model
        try:
            vecs = self.embedder.embed([c.text for c in todo])
        except Exception as e:
            log.warning("local embedder failed: %s", type(e).__name__)
            return stored_model if subject.embedding is not None else None
        for c, v in zip(todo, vecs):
            c.embedding = v
        return self.embedder.tag

    # ------------------------------------------------------------------------------------------ embeddings (civic:ai_jobs "embed")
    def _embed_text(self, text: str, warnings: list[str]) -> tuple[list[float] | None, str | None, str]:
        """(vector, model tag, source): the local M7 when configured, else the provider's embedder, else nothing (with a warning). Never raises."""
        if self.embedder is not None:
            try:
                return [float(x) for x in self.embedder.embed([text])[0]], self.embedder.tag, "local_m7"
            except Exception as e:                                      # noqa: BLE001
                log.warning("local embedder failed: %s", type(e).__name__)
                warnings.append(W.make("LOCAL_EMBEDDER_FAILED", f"the local embedder failed ({type(e).__name__}); trying the provider"))
        provider = self.ai.provider
        if provider_ready(provider, "embedding"):
            try:
                res = provider.embed([text])
                if res.vectors and res.vectors[0]:
                    return [float(x) for x in res.vectors[0]], f"provider:{res.model}", "provider"
                warnings.append(W.make(W.PROVIDER_OUTPUT_INVALID, "the embedding provider returned no vector"))
            except Exception as e:                                      # noqa: BLE001
                log.warning("embedding provider failed: %s", type(e).__name__)
                warnings.append(W.make(W.PROVIDER_UNAVAILABLE, f"the embedding provider failed ({type(e).__name__})"))
        else:
            warnings.append(W.make("NO_EMBEDDER", "no local embedder (AI_EMBED_ONNX_PATH) and no embedding provider configured; the case was not embedded"))
        return None, None, "none"

    def embed_case(self, case_id: str, actor: Actor) -> dict[str, Any]:
        """Worker entry: embed the case text and store the vector (JSON everywhere + the pgvector columns where they exist, via ``repo.save_embedding``). Nothing is stored and a
        warning is recorded on the ``embedding`` AIAnalysis when no embedder is available; this never raises for provider/model reasons."""
        self._require(actor, "embed")
        case = self._case(case_id)
        warnings: list[str] = []
        text = (case.text or "").strip()
        vector, model, source = (None, None, "none")
        if text:
            vector, model, source = self._embed_text(text, warnings)
        else:
            warnings.append(W.make("EMBEDDING_SKIPPED", "the case has no text to embed"))
        stored: dict | None = None
        if vector is not None:
            save = getattr(self.repo, "save_embedding", None)
            if save is None:
                warnings.append(W.make("EMBEDDING_NOT_STORED", "this store cannot persist embeddings"))
            else:
                try:
                    stored = save(case.id, vector, model)
                except Exception as e:                                  # noqa: BLE001
                    log.warning("storing the embedding of %s failed: %s", case.id, type(e).__name__)
                    warnings.append(W.make("EMBEDDING_NOT_STORED", f"storing the embedding failed ({type(e).__name__})"))
        info = {"stored": stored is not None, "dim": len(vector) if vector else 0, "model": model, "pgvector": bool(stored and stored.get("pgvector")), "warnings": warnings}
        analysis_id = self.analyses.save({"task_type": "embedding", "case_id": case.id, "actor_id": actor.user_id, "confidence": None, "model": model, "source": source,
                                          "degraded": bool(warnings), "created_at": self.clock().isoformat(), "result_json": info, "warnings": warnings})
        return {**info, "source": source, "analysis_id": analysis_id}

    def fusion(self, case_id: str, actor: Actor) -> FusionAnalyzeResponse:
        self._require(actor, "fusion")
        case = self._case(case_id)
        bounds = self.ai.fusion.candidate_query_params()
        cands = self.repo.fusion_candidates(case, radius_m=bounds["radius_m"], time_window_days=bounds["time_window_days"],
                                            max_candidates=bounds["max_candidates"], same_category=bool(bounds.get("same_category_required", True)))
        subject, candidates, emb_model = self._fusion_case(case), [self._fusion_case(c) for c in cands], case.embedding_model
        if self.embedder is not None:
            emb_model = self._embed_cases(subject, candidates, case.embedding_model)
        try:
            res = self.ai.analyze_fusion(FusionRequest(subject=subject, candidates=candidates, embedding_model=emb_model))
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

    # ------------------------------------------------------------------------------------------ AI-5 analytics explanation (additive endpoint)
    def explain_analytics(self, req: AnalyticsExplainRequest, actor: Actor) -> AnalyticsExplainResponse:
        """Deterministic facts (role-scoped) -> ``ai.explain_analytics``, which accepts model prose only if every number and fact id is grounded."""
        self._require(actor, "analytics_explain")
        if self.facts is None:
            raise CivicConnectException("ANALYTICS_UNAVAILABLE", "No analytics fact source is configured.", 503)
        try:
            facts = self.facts.facts(actor_id=actor.user_id, role=actor.role, ward_id=req.scope.ward_id, department_id=req.scope.department_id)
        except ToolPermissionDenied as e:
            raise CivicConnectException("AUTH_FORBIDDEN", "That analytics scope is not available to your role.", 403) from e
        try:
            res = self.ai.explain_analytics(facts)
        except (ValidationError, ValueError) as e:
            raise self._input_error(e) from e
        analysis_id = self._persist("analytics_explain", None, actor, res, None, {"fact_count": len(facts.facts)})
        return AnalyticsExplainResponse(
            summary=res.summary, highlights=[h.model_dump(mode="json") for h in res.highlights], citations=[c.model_dump(mode="json") for c in res.citations],
            facts=[f.model_dump(mode="json") for f in facts.facts], grounded=res.grounded, warnings=res.warnings, ai_metadata=self._meta(res), analysis_id=analysis_id)
