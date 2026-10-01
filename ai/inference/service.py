"""``AIService`` — the single entry point the FastAPI backend should call.

Usage (backend)::

    ai = AIService.from_env(tool_executor=MyCopilotExecutor(...))
    resp = ai.analyze_intake(IntakeRequest(...))          # -> IntakeResponse

All methods are synchronous and CPU/network bound; call them from a worker or
``run_in_threadpool``. Provider failures never raise: they degrade to documented
fallbacks and are reported through ``warnings`` and ``ai_metadata``. Only invalid
*input* raises (``pydantic.ValidationError`` / ``InputLimitExceeded`` /
``ToolValidationError``) so the API layer can return a 4xx.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Mapping

from .analytics.service import AnalyticsExplainer
from .config import AIPolicy, ProviderSettings, Taxonomy, load_fusion_policy, load_taxonomy
from .copilot.service import CopilotService
from .copilot.tools import ToolExecutor
from .errors import AIError
from .fusion.scoring import FusionWeights
from .fusion.service import FusionService
from .intake.service import IntakeService
from .local.text_classifier import LocalTextClassifier
from .provider import AIProvider
from .providers.openai_provider import OpenAIProvider
from .resolution.service import ResolutionService
from .schemas import (
    ActorContext,
    AnalyticsExplanation,
    AnalyticsFactSet,
    CopilotQuery,
    CopilotResponse,
    FusionRequest,
    FusionResponse,
    IntakeRequest,
    IntakeResponse,
    ResolutionReviewRequest,
    ResolutionReviewResponse,
    TriageRequest,
    TriageResponse,
)
from .triage.service import TriageService

log = logging.getLogger("civicconnect.ai")


class AIService:
    def __init__(self, provider: AIProvider | None = None, classifier: LocalTextClassifier | None = None,
                 fusion_weights: FusionWeights | None = None, tool_executor: ToolExecutor | None = None,
                 taxonomy: Taxonomy | None = None, policy: AIPolicy | None = None,
                 embedding_weights: FusionWeights | None = None):
        self.taxonomy = taxonomy or load_taxonomy()
        self.policy = policy or AIPolicy.load()
        self.provider = provider
        self.classifier = classifier
        self.intake = IntakeService(provider, classifier, self.taxonomy, self.policy)
        self.fusion = FusionService(provider, fusion_weights, load_fusion_policy(), self.taxonomy, embedding_weights)
        self.triage = TriageService(provider, self.taxonomy, self.policy)
        self.resolution = ResolutionService(provider, self.taxonomy, self.policy)
        self.analytics = AnalyticsExplainer(provider)
        self.copilot = CopilotService(provider, tool_executor, self.taxonomy, self.policy)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, tool_executor: ToolExecutor | None = None) -> "AIService":
        env = dict(os.environ if env is None else env)
        settings = ProviderSettings.from_env(env)
        provider: AIProvider | None = None
        if settings.provider == "openai":
            try:
                provider = OpenAIProvider(settings)
            except AIError as e:
                log.warning("AI provider not available: %s", e)
        classifier = None
        if env.get("AI_LOCAL_CLASSIFIER_PATH"):
            try:
                classifier = LocalTextClassifier.load(env["AI_LOCAL_CLASSIFIER_PATH"])
            except AIError as e:
                log.error("local classifier failed to load (%s); running without fallback model", e)
        weights = emb_weights = None
        for var, kind in (("AI_FUSION_WEIGHTS_PATH", "lexical"), ("AI_FUSION_EMBEDDING_WEIGHTS_PATH", "embedding")):
            if env.get(var):
                try:
                    w = FusionWeights.load(env[var])
                    if kind == "embedding":
                        emb_weights = w
                    else:
                        weights = w
                except AIError as e:
                    log.error("%s failed to load (%s); using uncalibrated prior", var, e)
        return cls(provider, classifier, weights, tool_executor, embedding_weights=emb_weights)

    # ---- capability entry points ------------------------------------------- #
    def analyze_intake(self, req: IntakeRequest) -> IntakeResponse:
        return self.intake.analyze(req)

    def analyze_fusion(self, req: FusionRequest) -> FusionResponse:
        return self.fusion.analyze(req)

    def analyze_triage(self, req: TriageRequest) -> TriageResponse:
        return self.triage.analyze(req)

    def review_resolution(self, req: ResolutionReviewRequest) -> ResolutionReviewResponse:
        return self.resolution.review(req)

    def explain_analytics(self, facts: AnalyticsFactSet) -> AnalyticsExplanation:
        return self.analytics.explain(facts)

    def copilot_query(self, q: CopilotQuery, actor: ActorContext) -> CopilotResponse:
        return self.copilot.query(q, actor)

    # ---- introspection (admin/readiness diagnostics; contains no secrets) ----- #
    def status(self) -> dict[str, Any]:
        return {
            "taxonomy": {"version": self.taxonomy.version, "status": self.taxonomy.status},
            "provider": {"name": self.provider.name if self.provider else None,
                         "models": {t: self.provider.model_for(t) for t in
                                    ("intake", "triage", "resolution", "analytics", "copilot", "embedding", "transcription")}
                         if self.provider else {}},
            "local_classifier": ({"name": self.classifier.model_name, "version": self.classifier.model_version}
                                 if self.classifier else None),
            "fusion_weights": {"lexical": {"status": self.fusion.weights.status, "version": self.fusion.weights.version},
                               "embedding": {"status": self.fusion.embedding_weights.status,
                                             "version": self.fusion.embedding_weights.version}},
            "copilot_executor_configured": self.copilot.executor is not None,
        }
