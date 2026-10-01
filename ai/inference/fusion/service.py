"""AI-2 Case Fusion / duplicate analysis.

Pipeline (Section 20/37): deterministic candidate bounds (same category, radius,
time window) -> signals (semantic / geospatial / temporal / category) ->
calibrated combined score -> recommendation. Embeddings are used when
available; otherwise a lexical signal is used and the response says so.
No LLM is invoked per candidate.
"""
from __future__ import annotations

from typing import Sequence

from ..common import log_event, metadata, provider_ready
from ..config import Taxonomy, load_fusion_policy, load_taxonomy
from ..errors import AIError
from ..provider import AIProvider, EmbeddingResult
from ..schemas import FusionCase, FusionMatch, FusionRequest, FusionResponse, FusionSignals, W
from .scoring import FusionWeights
from .similarity import category_signal, cosine, geospatial_signal, haversine_m, lexical_similarity, temporal_signal

_MAX_EMBED_TEXTS = 60


class FusionService:
    def __init__(self, provider: AIProvider | None = None, weights: FusionWeights | None = None,
                 policy: dict | None = None, taxonomy: Taxonomy | None = None,
                 embedding_weights: FusionWeights | None = None):
        """``weights`` score pairs using the lexical semantic signal; ``embedding_weights`` score pairs
        using embedding cosine. Weights fitted on one signal are never applied to the other."""
        self.provider = provider
        self.policy = policy or load_fusion_policy()
        prior = FusionWeights.from_prior(self.policy)
        self.weights = weights or prior
        self.embedding_weights = embedding_weights or prior
        self.taxonomy = taxonomy or load_taxonomy()

    # ---- bounds for backend SQL (PostGIS / pgvector) ----------------------- #
    def candidate_query_params(self) -> dict:
        return dict(self.policy["candidate_generation"])

    def in_policy(self, subject: FusionCase, cand: FusionCase) -> tuple[bool, float, float]:
        cg = self.policy["candidate_generation"]
        d = haversine_m(subject.latitude, subject.longitude, cand.latitude, cand.longitude)
        age_h = abs((subject.created_at - cand.created_at).total_seconds()) / 3600.0
        ok = (cand.case_id != subject.case_id and d <= cg["radius_m"]
              and age_h <= 24 * cg["time_window_days"]
              and (not cg["same_category_required"] or cand.category == subject.category))
        return ok, d, age_h

    def generate_candidates(self, subject: FusionCase, pool: Sequence[FusionCase]) -> list[FusionCase]:
        """Deterministic in-memory equivalent of the SQL candidate query (tests, seeding, offline eval)."""
        out = [(self.in_policy(subject, c), c) for c in pool]
        picked = sorted(((d, c) for (ok, d, _), c in out if ok), key=lambda x: (x[0], x[1].case_id))
        return [c for _, c in picked[: self.policy["candidate_generation"]["max_candidates"]]]

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingResult:
        """For case creation: backend stores the vectors in pgvector with ``model`` + dimension."""
        if not provider_ready(self.provider, "embedding"):
            raise AIError("embedding model not configured")
        return self.provider.embed(texts)  # type: ignore[union-attr]

    # ---- analysis ----------------------------------------------------------- #
    def analyze(self, req: FusionRequest) -> FusionResponse:
        warnings: list[str] = []
        cg, th = self.policy["candidate_generation"], self.policy["thresholds"]
        subject = req.subject
        gated: list[tuple[FusionCase, float, float]] = []
        dropped = 0
        for c in req.candidates[: cg["max_candidates"] * 4]:
            ok, d, age_h = self.in_policy(subject, c)
            if ok:
                gated.append((c, d, age_h))
            else:
                dropped += 1
        gated = gated[: cg["max_candidates"]]
        if dropped:
            warnings.append(W.make(W.FUSION_CANDIDATE_OUT_OF_POLICY, f"{dropped} candidate(s) outside radius/time/category bounds ignored"))

        subj_emb, cand_emb, emb_model, latency = self._embeddings(req, gated, warnings)
        used_embeddings = False
        matches: list[FusionMatch] = []
        for c, d, age_h in gated:
            e_s, e_c = subj_emb, cand_emb.get(c.case_id)
            if e_s is not None and e_c is not None and len(e_s) == len(e_c):
                sem, src = cosine(e_s, e_c), "embedding"
                used_embeddings = True
            else:
                sem, src = lexical_similarity(subject.text, c.text), "lexical"
            geo = geospatial_signal(d, cg["radius_m"])
            tmp = temporal_signal(age_h, cg["time_window_days"])
            cat = category_signal(subject.category, subject.subcategory, c.category, c.subcategory)
            score = (self.embedding_weights if src == "embedding" else self.weights).score(sem, geo, tmp, cat)
            avail = ["semantic", "geospatial", "temporal", "category"]
            matches.append(FusionMatch(
                case_id=c.case_id, similarity=round(score, 4),
                signals=FusionSignals(semantic=round(sem, 4), geospatial=round(geo, 4), temporal=round(tmp, 4),
                                      visual=0.0, category=cat, signals_available=avail),
                distance_m=round(d, 1), age_hours=round(age_h, 1), semantic_source=src))  # type: ignore[arg-type]
        matches.sort(key=lambda m: (-m.similarity, m.distance_m, m.case_id))
        matches = [m for m in matches if m.similarity >= th["related"]][: self.policy["max_matches"]]

        used = {m.semantic_source for m in matches} or {"lexical"}
        uncal = [n for n, w in (("lexical", self.weights), ("embedding", self.embedding_weights))
                 if n in used and w.status != "calibrated_synthetic"]
        if uncal:
            warnings.append(W.make(W.FUSION_UNCALIBRATED_PRIOR,
                                   f"combined score uses uncalibrated prior weights for the {'/'.join(uncal)} semantic signal"))
        if gated and not used_embeddings and subject.text:
            warnings.append(W.make(W.FUSION_LEXICAL_ONLY, "semantic signal is lexical (mono-lingual); cross-language duplicates may be missed"))

        top = matches[0].similarity if matches else 0.0
        rec = "POSSIBLE_DUPLICATE" if top >= th["possible_duplicate"] else "RELATED" if top >= th["related"] else "NO_MATCH"
        degraded = not used_embeddings and bool(gated)
        log_event("fusion", "degraded" if degraded else "ok", candidates=len(gated), matches=len(matches))
        return FusionResponse(
            matches=matches, recommendation=rec, warnings=warnings,  # type: ignore[arg-type]
            ai_metadata=metadata(
                "fusion", "provider+rules" if used_embeddings else "rules", provider=self.provider if used_embeddings else None,
                taxonomy_version=self.taxonomy.version, model=emb_model if used_embeddings else None,
                model_version=(self.embedding_weights if used_embeddings else self.weights).version, prompt_version=self.policy["policy_version"],
                confidence_basis=(f"lexical_weights:{self.weights.status}"
                                  + (f";embedding_weights:{self.embedding_weights.status}" if used_embeddings else "")),
                fallback_reason="lexical_semantic_only" if degraded else None, latency_ms=latency,
                input_refs=[subject.case_id] + [c.case_id for c, _, _ in gated]),
        )

    def _embeddings(self, req: FusionRequest, gated, warnings: list[str]):
        subject = req.subject
        subj = subject.embedding
        cands = {c.case_id: c.embedding for c, _, _ in gated if c.embedding is not None}
        model, latency = req.embedding_model, None
        missing = [c for c, _, _ in gated if c.embedding is None and c.text]
        need_subject = subj is None and bool(subject.text)
        if (need_subject or missing) and gated and provider_ready(self.provider, "embedding"):
            texts = ([subject.text] if need_subject else []) + [c.text for c in missing]  # type: ignore[misc]
            if len(texts) <= _MAX_EMBED_TEXTS:
                try:
                    res = self.provider.embed(texts)  # type: ignore[union-attr]
                    model, latency = res.model, res.latency_ms
                    vecs = iter(res.vectors)
                    if need_subject:
                        subj = next(vecs)
                    for c in missing:
                        cands[c.case_id] = next(vecs)
                except (AIError, StopIteration) as e:
                    warnings.append(W.make(W.PROVIDER_UNAVAILABLE, f"embedding failed ({type(e).__name__}); using lexical signal"))
        return subj, cands, model, latency
