"""AI-6 Grounded Admin Copilot orchestrator.

    admin question -> (model) tool plan -> validate -> enforce scope -> backend
    ToolExecutor (RBAC, parameterised SQL) -> results -> (model) explanation ->
    grounding check -> answer + citations

The model never receives database credentials or a SQL interface. Its answer is
accepted only if cited ids and every number come from the executed tool results.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .. import prompts
from ..common import log_event, metadata, provider_ready
from ..config import AIPolicy, Taxonomy, load_taxonomy
from ..errors import AIError, ToolPermissionDenied, ToolValidationError
from ..grounding import allowed_numbers, ungrounded_numbers
from ..provider import AIProvider, InputPart
from ..schemas import ActorContext, Citation, CopilotQuery, CopilotResponse, CopilotScope, ExecutedToolCall, W
from .tools import TOOL_MODELS, ToolExecutor, ToolResult, tool_specs


class CopilotService:
    def __init__(self, provider: AIProvider | None, executor: ToolExecutor | None,
                 taxonomy: Taxonomy | None = None, policy: AIPolicy | None = None):
        self.provider = provider
        self.executor = executor
        self.taxonomy = taxonomy or load_taxonomy()
        self.policy = policy or AIPolicy.load()

    # ------------------------------------------------------------------ #
    def query(self, q: CopilotQuery, actor: ActorContext) -> CopilotResponse:
        pol = self.policy.copilot
        if len(q.query) > pol["max_query_chars"]:
            raise ToolValidationError(f"query exceeds {pol['max_query_chars']} characters")
        warnings: list[str] = []
        if not provider_ready(self.provider, "copilot") or self.executor is None:
            return self._unavailable("copilot provider/executor not configured", warnings)

        try:
            plan = self.provider.plan_tools(  # type: ignore[union-attr]
                instructions=prompts.COPILOT_PLAN_INSTRUCTIONS, query=q.query, tools=tool_specs())
        except AIError as e:
            return self._unavailable(f"{type(e).__name__}", warnings)

        executed: list[ExecutedToolCall] = []
        results: list[tuple[str, ToolResult]] = []
        for call in plan.calls[: pol["max_tool_calls"]]:
            try:
                args = self._validate(call.name, call.arguments)
                args = self._enforce_scope(args, q.scope, warnings)
            except (ToolValidationError, ValidationError) as e:
                warnings.append(W.make(W.TOOL_CALL_REJECTED, f"{call.name!r}: {type(e).__name__}"))
                continue
            try:
                res = self.executor.execute(call.name, args, scope=q.scope, actor=actor)
            except ToolPermissionDenied:
                warnings.append(W.make(W.TOOL_EXECUTION_FAILED, f"{call.name}: not permitted for this user/scope"))
                continue
            except Exception as e:  # executor is backend code; never leak its message to the client
                warnings.append(W.make(W.TOOL_EXECUTION_FAILED, f"{call.name}: {type(e).__name__}"))
                continue
            rows = res.rows[: pol["max_rows"]]
            truncated = res.truncated or len(res.rows) > len(rows)
            if truncated:
                warnings.append(W.make(W.RESULT_TRUNCATED, f"{call.name} results limited to {pol['max_rows']} rows"))
            executed.append(ExecutedToolCall(tool=call.name, arguments=json.loads(args.model_dump_json(exclude_none=True)),
                                             row_count=len(rows), truncated=truncated))
            results.append((call.name, ToolResult(rows=rows, citations=res.citations, truncated=truncated)))

        if not results:
            msg = ("I couldn't map that question to the data tools available to you."
                   if not plan.calls else "None of the requested data lookups could be completed.")
            return CopilotResponse(answer=msg, data=[], citations=[], warnings=warnings, tool_calls=executed,
                                   ai_metadata=self._meta("provider", plan.model, plan.latency_ms, "no_tool_results"))

        data = [row for _, r in results for row in r.rows][: pol["max_rows"]]
        all_cites: dict[tuple[str, str], Citation] = {(c.type, c.id): c for _, r in results for c in r.citations}
        answer, cites, expl_model, latency = self._explain(q, results, data, all_cites, executed, warnings)
        log_event("copilot", "ok", tools=len(executed), rows=len(data))
        return CopilotResponse(answer=answer, data=data, citations=cites, warnings=warnings, tool_calls=executed,
                               ai_metadata=self._meta("provider", expl_model or plan.model,
                                                      (plan.latency_ms or 0) + (latency or 0), None))

    # ------------------------------------------------------------------ #
    def _validate(self, name: str, arguments: dict[str, Any]):
        model = TOOL_MODELS.get(name)
        if model is None:
            raise ToolValidationError(f"unknown tool {name!r}")
        args = model(**arguments)
        t = self.taxonomy
        if getattr(args, "category", None):
            cat = t.resolve_category(args.category)
            if cat is None:
                raise ToolValidationError("unknown category")
            args.category = cat
        sub = getattr(args, "subcategory", None)
        if sub and sub not in t.subcategories:
            raise ToolValidationError("unknown subcategory")
        return args

    @staticmethod
    def _enforce_scope(args, scope: CopilotScope, warnings: list[str]):
        """Caller scope always wins: the model cannot widen ward/department/date range."""
        overridden = False
        if scope.ward_id is not None and hasattr(args, "ward_id"):
            if (args.ward_id not in (None, scope.ward_id)) or getattr(args, "ward_label", None):
                overridden = True
            args.ward_id = scope.ward_id
            if hasattr(args, "ward_label"):
                args.ward_label = None
        if scope.department_id is not None and hasattr(args, "department_id"):
            if args.department_id not in (None, scope.department_id):
                overridden = True
            args.department_id = scope.department_id
        if hasattr(args, "created_from") and scope.from_ is not None:
            if args.created_from is None or args.created_from < scope.from_:
                args.created_from = scope.from_
        if hasattr(args, "created_until") and scope.until is not None:
            if args.created_until is None or args.created_until > scope.until:
                args.created_until = scope.until
        if overridden:
            warnings.append(W.make(W.SCOPE_OVERRIDDEN, "requested filters outside your scope were replaced by your scope"))
        return args

    def _explain(self, q, results, data, all_cites, executed, warnings):
        allowed_ids = {c.id for c in all_cites.values()}
        cites = list(all_cites.values())[: self.policy.copilot["max_rows"]]
        det = self._deterministic_answer(executed, data)
        payload = json.dumps([{"tool": n, "rows": r.rows} for n, r in results], default=str, ensure_ascii=False)
        try:
            res = self.provider.structured_completion(  # type: ignore[union-attr]
                task="copilot", instructions=prompts.COPILOT_EXPLAIN_INSTRUCTIONS,
                parts=[InputPart.of_text(f"Question: {q.query}\nTool results (JSON):\n{payload[:60000]}")],
                schema_name="copilot_answer", json_schema=prompts.COPILOT_EXPLAIN_SCHEMA)
            answer = str(res.data.get("answer", "")).strip()
            cited = [str(i) for i in res.data.get("cited_ids", [])]
        except (AIError, ValueError, TypeError):
            warnings.append(W.make(W.PROVIDER_UNAVAILABLE, "explanation unavailable; showing a deterministic summary"))
            return det, cites, None, None
        allowed = allowed_numbers([payload, q.query, json.dumps([e.model_dump() for e in executed], default=str),
                                   len(data)] + [e.row_count for e in executed])
        bad = ungrounded_numbers(answer, allowed)
        if not answer or bad:
            warnings.append(W.make(W.EXPLANATION_UNGROUNDED_FALLBACK, "model answer contained figures not in the data; showing a deterministic summary"))
            return det, cites, res.model, res.latency_ms
        valid = [i for i in cited if i in allowed_ids]
        if len(valid) != len(cited):
            warnings.append(W.make(W.CITATION_DROPPED, "ignored citations not present in the results"))
        if valid:
            cites = [c for c in cites if c.id in set(valid)]
        return answer, cites, res.model, res.latency_ms

    @staticmethod
    def _deterministic_answer(executed: list[ExecutedToolCall], data: list[dict]) -> str:
        parts = [f"{e.tool}: {e.row_count} record(s)" for e in executed]
        return "Results retrieved — " + "; ".join(parts) + ". See the table for details."

    def _unavailable(self, reason: str, warnings: list[str]) -> CopilotResponse:
        warnings.append(W.make(W.COPILOT_UNAVAILABLE, "the AI copilot is currently unavailable"))
        return CopilotResponse(answer="The AI copilot is currently unavailable. Please use the case filters instead.",
                               data=[], citations=[], warnings=warnings,
                               ai_metadata=self._meta("none", None, None, reason))

    def _meta(self, source, model, latency, fallback):
        return metadata("copilot", source, taxonomy_version=self.taxonomy.version, provider=self.provider,
                        model=model, prompt_version=prompts.COPILOT_PLAN_PROMPT_VERSION + "+" + prompts.COPILOT_EXPLAIN_PROMPT_VERSION,
                        confidence_basis="grounded_in_tool_results", fallback_reason=fallback, latency_ms=latency)
