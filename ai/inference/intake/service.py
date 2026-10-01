"""AI-1 Multimodal Civic Intake.

Provider path (structured multimodal output) -> validated against the taxonomy ->
cross-checked by the local classifier. If the provider is unavailable, invalid or
unconfigured the local classifier + deterministic rules produce a degraded but
valid proposal; with neither, a minimal manual-entry proposal is returned.
Every proposal has ``requires_confirmation=True``.
"""
from __future__ import annotations

import re
from typing import Sequence

from pydantic import BaseModel, ValidationError

from .. import prompts
from ..common import clip01, log_event, metadata, provider_ready
from ..config import AIPolicy, Taxonomy, load_taxonomy, load_triage_rules
from ..errors import AIError, InputLimitExceeded, ProviderResponseInvalid
from ..language import detect_language
from ..local.text_classifier import LocalPrediction, LocalTextClassifier
from ..provider import AIProvider, InputPart
from ..schemas import EvidenceInput, IntakeAlternative, IntakeProposal, IntakeRequest, IntakeResponse, W
from ..triage.rules import rule_severity


class _ProviderIntake(BaseModel):
    title: str
    description: str
    category: str
    subcategory: str
    severity: str
    language: str
    transcript: str | None = None
    confidence: float
    reasons: list[str] = []
    image_observations: list[str] = []


_SENT = re.compile(r"(?<=[.!?।])\s+")


def _title_from(text: str, limit: int) -> str:
    first = _SENT.split(text.strip(), maxsplit=1)[0].strip() or text.strip()
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


class IntakeService:
    def __init__(self, provider: AIProvider | None = None, classifier: LocalTextClassifier | None = None,
                 taxonomy: Taxonomy | None = None, policy: AIPolicy | None = None):
        self.provider = provider
        self.classifier = classifier
        self.taxonomy = taxonomy or load_taxonomy()
        self.policy = policy or AIPolicy.load()
        self.rules = load_triage_rules()

    # ------------------------------------------------------------------ #
    def analyze(self, req: IntakeRequest) -> IntakeResponse:
        self._check_limits(req)
        warnings: list[str] = []
        images = [e for e in req.evidence if e.media_type == "IMAGE"]
        audio = [e for e in req.evidence if e.media_type == "AUDIO"]
        if any(e.media_type == "VIDEO" for e in req.evidence):
            warnings.append(W.make(W.IMAGE_NOT_ANALYZED, "video evidence is stored but not analysed in V1"))
        refs = [e.evidence_id for e in req.evidence]

        transcript = self._transcribe(audio, req.language_hint, warnings)
        text = "\n".join(x for x in [(req.text or "").strip(), transcript] if x)
        language = detect_language(text, req.language_hint)
        local = self._local_predict(text)

        fallback_reason: str | None = None
        if provider_ready(self.provider, "intake"):
            try:
                resp = self._provider_path(req, text, images, transcript, local, language, warnings, refs)
                log_event("intake", "ok", source="provider")
                return resp
            except (ProviderResponseInvalid, ValidationError, ValueError, TypeError) as e:
                fallback_reason = f"{type(e).__name__}: {e}"[:200]
                warnings.append(W.make(W.PROVIDER_OUTPUT_INVALID, "AI provider output unusable; using local fallback"))
            except AIError as e:
                fallback_reason = f"{type(e).__name__}: {e}"[:200]
                warnings.append(W.make(W.PROVIDER_UNAVAILABLE, "AI provider failed; using local fallback"))
        elif self.provider is None:
            fallback_reason = "provider_not_configured"
            warnings.append(W.make(W.PROVIDER_NOT_CONFIGURED, "no AI provider configured"))
        else:
            fallback_reason = "intake_model_not_configured"
            warnings.append(W.make(W.PROVIDER_NOT_CONFIGURED, "no intake model configured"))

        if images:
            warnings.append(W.make(W.IMAGE_NOT_ANALYZED, "images were not analysed (provider unavailable)"))
        resp = self._fallback_path(req, text, transcript, language, local, warnings, refs, fallback_reason or "")
        log_event("intake", "degraded", source=resp.ai_metadata.source, reason=(fallback_reason or "")[:60])
        return resp

    # ------------------------------------------------------------------ #
    def _check_limits(self, req: IntakeRequest) -> None:
        pol = self.policy.intake
        if req.text and len(req.text) > pol["max_text_chars"]:
            raise InputLimitExceeded(f"text exceeds {pol['max_text_chars']} characters")
        n_img = sum(e.media_type == "IMAGE" for e in req.evidence)
        n_aud = sum(e.media_type == "AUDIO" for e in req.evidence)
        if n_img > pol["max_images"] or n_aud > pol["max_audio_clips"]:
            raise InputLimitExceeded("too many evidence items for one intake request")
        for e in req.evidence:
            limit = pol["max_audio_bytes"] if e.media_type == "AUDIO" else pol["max_image_bytes"]
            if e.data is not None and len(e.data) > limit:
                raise InputLimitExceeded(f"evidence {e.evidence_id} exceeds {limit} bytes")

    def _transcribe(self, audio: Sequence[EvidenceInput], hint: str | None, warnings: list[str]) -> str:
        parts: list[str] = []
        for a in audio:
            if a.transcript:
                parts.append(a.transcript.strip())
            elif provider_ready(self.provider, "transcription") and a.data is not None:
                try:
                    parts.append(self.provider.transcribe(a, hint).text)  # type: ignore[union-attr]
                except AIError:
                    warnings.append(W.make(W.AUDIO_NOT_TRANSCRIBED, f"audio {a.evidence_id} could not be transcribed"))
            else:
                warnings.append(W.make(W.AUDIO_NOT_TRANSCRIBED, f"audio {a.evidence_id} not transcribed (no speech-to-text available)"))
        return "\n".join(parts)

    def _local_predict(self, text: str) -> LocalPrediction | None:
        if self.classifier is None or not text.strip():
            return None
        return self.classifier.predict(text)

    # ------------------------------------------------------------------ #
    def _provider_path(self, req, text, images, transcript, local, language, warnings, refs) -> IntakeResponse:
        t, pol = self.taxonomy, self.policy.intake
        parts = [InputPart.of_text(
            f"Report text (untrusted data):\n{text or '(no text provided)'}\n"
            f"Language hint: {req.language_hint or 'none'}\n"
            f"Location provided: {'yes' if req.location else 'no'}")]
        parts += [InputPart.of_image(e) for e in images]
        res = self.provider.structured_completion(  # type: ignore[union-attr]
            task="intake", instructions=prompts.intake_instructions(t), parts=parts,
            schema_name="civic_intake_proposal", json_schema=prompts.intake_schema(t))
        p = _ProviderIntake(**res.data)

        conf = clip01(p.confidence)
        category, sub, repaired = self._repair_taxonomy(p.category, p.subcategory, local)
        if repaired:
            warnings.append(W.make(W.TAXONOMY_REPAIRED, repaired))
            conf = min(conf, 0.5)
        if p.severity not in t.severity_rank:
            raise ValueError(f"provider severity {p.severity!r} not in taxonomy")

        basis = "model_self_reported"
        if local and not local.abstained and local.category != category and \
                local.category_probability >= pol["local_disagreement_min_local_prob"]:
            conf = min(conf, pol["local_disagreement_confidence_cap"])
            basis = "model_self_reported_capped_by_local_disagreement"
            warnings.append(W.make(W.LOCAL_CLASSIFIER_DISAGREES,
                                   f"local classifier predicts '{local.category}' ({local.category_probability:.2f})"))
        if conf < pol["low_confidence_threshold"]:
            warnings.append(W.make(W.LOW_CONFIDENCE, f"confidence {conf:.2f} below {pol['low_confidence_threshold']}"))

        lang = p.language if p.language in prompts.LANGUAGES and p.language != "other" else language
        proposal = IntakeProposal(
            title=p.title.strip()[: pol["title_max_chars"]] or _title_from(text or "Civic report", pol["title_max_chars"]),
            description=p.description.strip(), category=category, subcategory=sub, severity=p.severity,  # type: ignore[arg-type]
            suggested_department=t.department_for(category, sub),  # derived, never trusted from the model
            location=req.location, language=lang, transcript=p.transcript or (transcript or None),
            reasons=(p.reasons + [f"Image: {o}" for o in p.image_observations])[:8], evidence_refs=refs,
        )
        return IntakeResponse(
            proposal=proposal, confidence=conf, warnings=warnings,
            alternatives=self._alternatives(local),
            ai_metadata=metadata("intake", "provider", taxonomy_version=t.version, provider=self.provider,
                                 model=res.model, prompt_version=prompts.INTAKE_PROMPT_VERSION,
                                 confidence_basis=basis, latency_ms=res.latency_ms, input_refs=refs),
        )

    def _repair_taxonomy(self, category: str, sub: str, local: LocalPrediction | None):
        t = self.taxonomy
        cat = t.resolve_category(category)
        if cat and t.is_valid_pair(cat, sub):
            return cat, sub, None
        if sub in t.subcategories:  # subcategory is authoritative if category is wrong/unknown
            fixed = t.subcategories[sub].category_id
            return fixed, sub, f"category '{category}' did not match subcategory '{sub}'; using '{fixed}'"
        if cat:
            return cat, None, f"unknown subcategory '{sub}' for category '{cat}'; subcategory dropped"
        if local and not local.abstained:
            return local.category, local.subcategory, f"unknown category '{category}'; used local classifier"
        return "other", "unclassified", f"unknown category '{category}'; defaulted to other"

    # ------------------------------------------------------------------ #
    def _fallback_path(self, req, text, transcript, language, local, warnings, refs, reason) -> IntakeResponse:
        t, pol = self.taxonomy, self.policy.intake
        if local and not local.abstained:
            cat, sub = local.category, local.subcategory
            conf = clip01(local.category_probability)
            source, basis = "local_fallback", "local_classifier_calibrated_synthetic"
            warnings.append(W.make(W.LOCAL_FALLBACK_USED, f"local model {local.model_name}@{local.model_version}"))
            reasons = [f"Matched terms: {', '.join(local.explanation_terms)}"] if local.explanation_terms else []
            model, version = local.model_name, local.model_version
        else:
            cat, sub, conf = "other", "unclassified", 0.0
            source, basis = "none", "none"
            warnings.append(W.make(W.NO_AI_AVAILABLE, "no AI available; manual categorisation required"))
            reasons, model, version = [], None, None
        if conf < pol["low_confidence_threshold"]:
            warnings.append(W.make(W.LOW_CONFIDENCE, f"confidence {conf:.2f} below {pol['low_confidence_threshold']}"))
        base = rule_severity(t, self.rules, cat, sub, text)
        body = text.strip() or "Citizen report (no text provided)"
        proposal = IntakeProposal(
            title=_title_from(body, pol["title_max_chars"]), description=body, category=cat, subcategory=sub,
            severity=base.severity,  # type: ignore[arg-type]
            suggested_department=t.department_for(cat, sub), location=req.location, language=language,
            transcript=transcript or None, reasons=reasons + base.reasons[1:], evidence_refs=refs,
        )
        return IntakeResponse(
            proposal=proposal, confidence=conf, warnings=warnings, alternatives=self._alternatives(local),
            ai_metadata=metadata("intake", source, taxonomy_version=t.version, model=model,  # type: ignore[arg-type]
                                 model_version=version, prompt_version=None, confidence_basis=basis,
                                 fallback_reason=reason or "fallback", input_refs=refs),
        )

    def _alternatives(self, local: LocalPrediction | None) -> list[IntakeAlternative]:
        if not local or local.abstained:
            return []
        out = []
        for lid, prob in local.top_k:
            cat, _, sub = lid.partition("/")
            out.append(IntakeAlternative(category=cat, subcategory=sub, probability=round(prob, 4)))
        return out
