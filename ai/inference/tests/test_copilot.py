from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai.inference.copilot.service import CopilotService
from ai.inference.copilot.tools import TOOL_MODELS, SearchCasesArgs, ToolResult, tool_specs
from ai.inference.errors import ProviderUnavailable, ToolPermissionDenied, ToolValidationError
from ai.inference.provider import PlannedToolCall
from ai.inference.providers.fake import FakeProvider
from ai.inference.schemas import ActorContext, Citation, CopilotQuery, CopilotScope, W

ACTOR = ActorContext(user_id="u-admin", role="CITY_ADMIN")
ROWS = [{"case_id": "cc-1", "title": "Garbage pile", "severity": "HIGH"}, {"case_id": "cc-2", "title": "Overflowing bin", "severity": "HIGH"}]


class FakeExecutor:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = ROWS if rows is None else rows, error, []

    def execute(self, tool, arguments, *, scope, actor):
        self.calls.append((tool, arguments, scope, actor))
        if self.error:
            raise self.error
        return ToolResult(rows=list(self.rows), citations=[Citation(type="CASE", id=r["case_id"]) for r in self.rows if "case_id" in r])


def provider(calls, answer="Found 2 high-severity sanitation cases.", cited=("cc-1", "cc-2")):
    return FakeProvider(tool_plan=calls, structured={"copilot": {"answer": answer, "cited_ids": list(cited)}})


SEARCH = PlannedToolCall("search_cases", {"category": "sanitation", "severity": ["HIGH"], "unresolved_only": True,
                                          "older_than_days": 7, "ward_label": "W18"})


def codes(r):
    return [w.split(":")[0] for w in r.warnings]


def make(prov, ex):
    return CopilotService(prov, ex)


def test_happy_path_is_grounded_in_tool_results():
    ex = FakeExecutor()
    r = make(provider([SEARCH]), ex).query(CopilotQuery(query="Show unresolved high-priority sanitation cases in W18 older than seven days"), ACTOR)
    tool, args, scope, actor = ex.calls[0]
    assert tool == "search_cases" and isinstance(args, SearchCasesArgs) and args.category == "sanitation" and args.ward_label == "W18"
    assert actor == ACTOR and r.data == ROWS and r.warnings == []
    assert {c.id for c in r.citations} == {"cc-1", "cc-2"} and r.answer.startswith("Found 2")
    assert r.tool_calls[0].tool == "search_cases" and r.tool_calls[0].row_count == 2 and r.ai_metadata.confidence_basis == "grounded_in_tool_results"


def test_unknown_tool_and_extra_arguments_are_rejected_and_never_executed():
    ex = FakeExecutor()
    plan = [PlannedToolCall("run_sql", {"sql": "SELECT * FROM users"}), PlannedToolCall("search_cases", {"category": "sanitation", "sql": "DROP TABLE cases"}),
            PlannedToolCall("search_cases", {"__raw__": "{bad"})]
    r = make(provider(plan), ex).query(CopilotQuery(query="x"), ACTOR)
    assert ex.calls == [] and codes(r).count(W.TOOL_CALL_REJECTED) == 3 and r.data == []
    assert "couldn't" in r.answer or "None of" in r.answer


def test_invalid_argument_values_are_rejected():
    ex = FakeExecutor()
    plan = [PlannedToolCall("search_cases", {"limit": 100000}), PlannedToolCall("search_cases", {"category": "no_such_category"}),
            PlannedToolCall("search_cases", {"status": ["DELETED"]}), PlannedToolCall("count_cases", {})]
    r = make(provider(plan), ex).query(CopilotQuery(query="x"), ACTOR)
    assert ex.calls == [] and codes(r).count(W.TOOL_CALL_REJECTED) == 4


def test_category_aliases_are_normalised():
    ex = FakeExecutor()
    make(provider([PlannedToolCall("search_cases", {"category": "garbage"})]), ex).query(CopilotQuery(query="x"), ACTOR)
    assert ex.calls[0][1].category == "sanitation"


def test_caller_scope_cannot_be_widened_by_the_model():
    ex = FakeExecutor()
    scope = CopilotScope(ward_id="ward-1", department_id="dept-1")
    plan = [PlannedToolCall("search_cases", {"ward_id": "ward-2", "department_id": "dept-9"}),
            PlannedToolCall("get_analytic", {"name": "overview", "ward_id": "ward-2"})]
    r = make(provider(plan), ex).query(CopilotQuery(query="x", scope=scope), ACTOR)
    for _, args, sc, _ in ex.calls:
        assert args.ward_id == "ward-1" and sc == scope
    assert ex.calls[0][1].department_id == "dept-1" and W.SCOPE_OVERRIDDEN in codes(r)


def test_ward_label_is_dropped_when_scope_fixes_the_ward():
    ex = FakeExecutor()
    make(provider([SEARCH]), ex).query(CopilotQuery(query="x", scope=CopilotScope(ward_id="ward-1")), ACTOR)
    assert ex.calls[0][1].ward_id == "ward-1" and ex.calls[0][1].ward_label is None


def test_date_scope_clamps_the_model_request():
    ex = FakeExecutor()
    lo, hi = datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 30, tzinfo=timezone.utc)
    plan = [PlannedToolCall("search_cases", {"created_from": "2025-01-01T00:00:00Z", "created_until": "2027-01-01T00:00:00Z"})]
    make(provider(plan), ex).query(CopilotQuery(query="x", scope=CopilotScope.model_validate({"from": lo, "until": hi})), ACTOR)
    a = ex.calls[0][1]
    assert a.created_from == lo and a.created_until == hi


def test_row_and_tool_call_limits(policy):
    rows = [{"case_id": f"cc-{i}"} for i in range(120)]
    ex = FakeExecutor(rows=rows)
    plan = [PlannedToolCall("search_cases", {"category": "sanitation"})] * 6
    r = make(provider(plan, answer="Retrieved the cases.", cited=()), ex).query(CopilotQuery(query="x"), ACTOR)
    assert len(ex.calls) == policy.copilot["max_tool_calls"] and len(r.data) <= policy.copilot["max_rows"]
    assert W.RESULT_TRUNCATED in codes(r) and all(t.row_count <= policy.copilot["max_rows"] for t in r.tool_calls)


def test_executor_errors_are_contained_and_not_leaked():
    r = make(provider([SEARCH]), FakeExecutor(error=RuntimeError("psycopg connection string postgres://user:pw@db/civic"))).query(CopilotQuery(query="x"), ACTOR)
    assert W.TOOL_EXECUTION_FAILED in codes(r) and "postgres://" not in r.model_dump_json() and r.data == []


def test_permission_denied_is_reported_not_raised():
    r = make(provider([SEARCH]), FakeExecutor(error=ToolPermissionDenied("nope"))).query(CopilotQuery(query="x"), ACTOR)
    assert any("not permitted" in w for w in r.warnings) and r.data == []


def test_ungrounded_numbers_in_the_answer_are_replaced():
    r = make(provider([SEARCH], answer="There are 57 such cases."), FakeExecutor()).query(CopilotQuery(query="x"), ACTOR)
    assert W.EXPLANATION_UNGROUNDED_FALLBACK in codes(r) and "57" not in r.answer and r.data == ROWS


def test_numbers_from_results_and_the_question_are_allowed():
    r = make(provider([SEARCH], answer="2 cases matched your 7 day filter."), FakeExecutor()).query(CopilotQuery(query="older than 7 days"), ACTOR)
    assert W.EXPLANATION_UNGROUNDED_FALLBACK not in codes(r)


def test_citations_not_in_results_are_dropped():
    r = make(provider([SEARCH], cited=("cc-1", "cc-999")), FakeExecutor()).query(CopilotQuery(query="x"), ACTOR)
    assert [c.id for c in r.citations] == ["cc-1"] and W.CITATION_DROPPED in codes(r)


def test_explanation_failure_falls_back_to_a_deterministic_summary():
    p = FakeProvider(tool_plan=[SEARCH], structured={"copilot": ProviderUnavailable("down")})
    r = make(p, FakeExecutor()).query(CopilotQuery(query="x"), ACTOR)
    assert r.answer.startswith("Results retrieved") and r.data == ROWS and r.citations


def test_planning_failure_or_missing_pieces_means_visible_unavailability():
    for prv, ex in ((FakeProvider(tool_plan=ProviderUnavailable("down")), FakeExecutor()), (provider([SEARCH]), None), (None, FakeExecutor())):
        r = make(prv, ex).query(CopilotQuery(query="x"), ACTOR)
        assert W.COPILOT_UNAVAILABLE in codes(r) and r.data == [] and "unavailable" in r.answer.lower()


def test_overlong_query_is_invalid_input(policy):
    with pytest.raises(ToolValidationError):
        make(provider([]), FakeExecutor()).query(CopilotQuery(query="x" * (policy.copilot["max_query_chars"] + 1)), ACTOR)


def test_no_tool_exposes_sql_credentials_or_raw_access():
    banned = {"sql", "query", "table", "column", "database", "dsn", "password", "credentials", "connection", "raw", "where", "order_by"}
    for spec in tool_specs():
        props = set(spec.parameters.get("properties", {}))
        assert not props & banned, (spec.name, props & banned)
        assert spec.parameters.get("additionalProperties") is False
    assert set(TOOL_MODELS) == {s.name for s in tool_specs()}
    for model in TOOL_MODELS.values():
        with pytest.raises(ValidationError):
            model(sql="select 1", **({"group_by": "status"} if model.__name__ == "CountCasesArgs" else {"name": "overview"} if model.__name__ == "GetAnalyticArgs" else {}))
