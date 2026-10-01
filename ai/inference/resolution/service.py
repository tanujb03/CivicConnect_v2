"""AI-4 Resolution intelligence — FLAG ONLY.

Compares original vs resolution evidence and field notes, and considers the
citizen's verification. It can raise flags (inconsistent / possibly unresolved /
recommend verification). It can never close a case: the response carries a
constant ``autonomous_closure_allowed = False`` and AI output can only *add*
flags to the deterministic baseline, never remove them.
"""
from __future__ import annotations

from pydantic import BaseModel, ValidationError

from .. import prompts
from ..common import clip01, log_event, metadata, provider_ready
from ..config import AIPolicy, Taxonomy, load_taxonomy
from ..errors import AIError
from ..provider import AIProvider, InputPart
from ..schemas import ResolutionReviewRequest, ResolutionReviewResponse, W

_NEGATIVE = {"STILL_OCCURRING", "NO"}


class _AIResolution(BaseModel):
    consistency: str
    unresolved_condition_suspected: bool
    confidence: float
    reasons: list[str] = []


class ResolutionService:
    def __init__(self, provider: AIProvider | None = None, taxonomy: Taxonomy | None = None,
                 policy: AIPolicy | None = None):
        self.provider = provider
        self.taxonomy = taxonomy or load_taxonomy()
        self.policy = policy or AIPolicy.load()

    def review(self, req: ResolutionReviewRequest) -> ResolutionReviewResponse:
        warnings: list[str] = []
        reasons: list[str] = []
        before = [e for e in req.original_evidence if e.media_type == "IMAGE"]
        after = [e for e in req.resolution_evidence if e.media_type == "IMAGE"]
        refs = [e.evidence_id for e in (*req.original_evidence, *req.resolution_evidence)]

        # ---- deterministic baseline -------------------------------------- #
        consistency = "INSUFFICIENT_EVIDENCE"
        unresolved = False
        if not after:
            reasons.append("No resolution photo was submitted")
        if not (req.field_notes or "").strip():
            reasons.append("No field notes were provided")
        if req.citizen_verification in _NEGATIVE:
            unresolved = True
            consistency = "INCONSISTENT"
            reasons.append(f"Citizen verification reports '{req.citizen_verification}'")
        elif req.citizen_verification == "PARTIAL":
            unresolved = True
            reasons.append("Citizen verification reports the issue is only partially resolved")
        recommend = req.citizen_verification != "YES"

        confidence, basis, model, latency, source, fallback = 0.5, "rules_only_nominal", None, None, "rules", None

        # ---- optional multimodal comparison (flags only) ------------------- #
        if provider_ready(self.provider, "resolution") and after:
            try:
                parts = [InputPart.of_text(
                    f"Case category: {req.category}/{req.subcategory}\nIssue description: {(req.description or '')[:1500]}\n"
                    f"Field notes: {(req.field_notes or '')[:1500]}\nCitizen verification: {req.citizen_verification}\n"
                    f"The first {len(before)} image(s) are ORIGINAL evidence; the next {len(after)} are RESOLUTION evidence.")]
                parts += [InputPart.of_image(e) for e in (*before, *after)]
                res = self.provider.structured_completion(  # type: ignore[union-attr]
                    task="resolution", instructions=prompts.RESOLUTION_INSTRUCTIONS, parts=parts,
                    schema_name="resolution_review", json_schema=prompts.RESOLUTION_SCHEMA)
                ai = _AIResolution(**res.data)
                if ai.consistency not in ("CONSISTENT", "INCONSISTENT", "INSUFFICIENT_EVIDENCE"):
                    raise ValueError("unknown consistency value")
                ai_conf = clip01(ai.confidence)
                model, latency, source = res.model, res.latency_ms, "provider+rules"
                reasons.extend(f"AI: {r}" for r in ai.reasons[:4])
                if ai_conf < float(self.policy.resolution["min_ai_confidence"]):
                    warnings.append(W.make(W.LOW_CONFIDENCE, f"AI confidence {ai_conf:.2f} below threshold; flags only"))
                    consistency = consistency if consistency == "INCONSISTENT" else "INSUFFICIENT_EVIDENCE"
                else:
                    # monotonic merge: AI can add flags, never clear deterministic ones
                    if consistency != "INCONSISTENT":
                        consistency = ai.consistency
                    unresolved = unresolved or ai.unresolved_condition_suspected
                    confidence, basis = ai_conf, "model_self_reported"
            except (AIError, ValidationError, ValueError, TypeError) as e:
                fallback = f"{type(e).__name__}: {e}"[:200]
                warnings.append(W.make(W.PROVIDER_UNAVAILABLE, "AI evidence comparison unavailable; deterministic flags only"))
        else:
            fallback = "provider_not_configured" if self.provider is None else "no_resolution_images_or_model"
            if after:
                warnings.append(W.make(W.IMAGE_NOT_ANALYZED, "resolution evidence present but not analysed by AI"))

        if consistency == "INCONSISTENT":
            unresolved = True
        if consistency != "CONSISTENT" and req.citizen_verification != "YES":
            recommend = True
        log_event("resolution", "ok" if fallback is None else "degraded", consistency=consistency)
        return ResolutionReviewResponse(
            consistency=consistency, unresolved_condition_suspected=unresolved,  # type: ignore[arg-type]
            recommend_verification_request=recommend, confidence=confidence, reasons=reasons, warnings=warnings,
            ai_metadata=metadata("resolution", source, taxonomy_version=self.taxonomy.version,  # type: ignore[arg-type]
                                 provider=self.provider, model=model, prompt_version=prompts.RESOLUTION_PROMPT_VERSION,
                                 confidence_basis=basis, fallback_reason=fallback, latency_ms=latency, input_refs=refs),
        )
