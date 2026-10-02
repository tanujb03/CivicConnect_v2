"""§51A AI endpoints through the real FastAPI app: contract shapes, §51A.18 roles, error envelope, degraded mode, override audit, copilot RBAC.

Runs against the synthetic demo city (design §58) with a scripted ``FakeProvider`` (no network, no real model outputs).
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from ai.inference.provider import PlannedToolCall  # noqa: E402
from ai.inference.providers.fake import FakeProvider  # noqa: E402
from ai.inference.schemas import EvidenceInput  # noqa: E402
from ai.inference.service import AIService  # noqa: E402
from ai.inference.tests.conftest import INTAKE_OK  # noqa: E402
from backend.ai_gateway import AIGateway, configure_gateway  # noqa: E402
from backend.ai_gateway.memory import (  # noqa: E402
    DEMO_DIR, DEMO_NOW, DemoCityRepository, DemoCityToolExecutor, MemoryAnalysisStore, MemoryAuditSink, MemoryEvidenceResolver,
)
from backend.core.security import create_access_token  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
TRUTH = json.loads((DEMO_DIR / "ground_truth.json").read_text())
PAIR = TRUTH["possible_duplicate_pairs"][0]


def token(role, sub="u-test"):
    return {"Authorization": f"Bearer {create_access_token(sub, role)}"}


class Env:
    def __init__(self, provider):
        self.repo = DemoCityRepository()
        self.evidence, self.analyses, self.audit = MemoryEvidenceResolver(), MemoryAnalysisStore(), MemoryAuditSink()
        self.ai = AIService(provider=provider, tool_executor=DemoCityToolExecutor(self.repo))
        self.gateway = AIGateway(self.ai, self.repo, self.evidence, self.analyses, self.audit, clock=lambda: DEMO_NOW)


def install(provider=None):
    env = Env(provider)
    configure_gateway(env.gateway)
    return env


@pytest.fixture(autouse=True)
def _reset():
    yield
    configure_gateway(None)


def intake_provider():
    return FakeProvider(structured={"intake": INTAKE_OK})


# --------------------------------------------------------------------------------------------- intake (51A.5)
class TestIntake:
    def test_contract_shape_and_confirmation_flag(self):
        env = install(intake_provider())
        r = client.post("/api/v1/cases/intake/analyze", headers=token("citizen"), json={"text": "pothole near the school", "language_hint": "en",
                        "location": {"latitude": 19.07, "longitude": 72.87}})
        assert r.status_code == 200, r.text
        b = r.json()
        assert set(b) >= {"proposal", "confidence", "warnings", "requires_confirmation"} and b["requires_confirmation"] is True
        assert set(b["proposal"]) >= {"title", "description", "category", "severity", "location", "language"}
        assert b["proposal"]["category"] == "roads" and b["proposal"]["location"]["latitude"] == 19.07
        # department: contract-style code + canonical id additive
        assert b["proposal"]["suggested_department"] == "ROADS" and b["proposal"]["suggested_department_id"] == "road_maintenance"
        assert env.analyses.records[0]["task_type"] == "intake" and env.analyses.records[0]["id"] == b["analysis_id"]

    def test_evidence_ids_are_accepted_and_resolved(self):
        """Regression: the old route rejected the contract's `evidence_ids` with 422 extra_forbidden."""
        env = install(intake_provider())
        env.evidence.register(EvidenceInput(evidence_id="ev-1", media_type="AUDIO", transcript="paani ka pipe phat gaya hai"), owner_id="u-test")
        r = client.post("/api/v1/cases/intake/analyze", headers=token("citizen"), json={"evidence_ids": ["ev-1"]})
        assert r.status_code == 200, r.text
        assert r.json()["proposal"]["evidence_refs"] == ["ev-1"]

    def test_unknown_or_foreign_evidence_is_404_with_envelope(self):
        env = install(intake_provider())
        env.evidence.register(EvidenceInput(evidence_id="ev-x", media_type="AUDIO", transcript="hello"), owner_id="someone-else")
        for eid in ("nope", "ev-x"):
            r = client.post("/api/v1/cases/intake/analyze", headers={**token("citizen"), "X-Request-ID": "req-1"}, json={"evidence_ids": [eid]})
            assert r.status_code == 404
            e = r.json()["error"]
            assert e["code"] == "EVIDENCE_NOT_FOUND" and e["request_id"] == "req-1" and r.headers["X-Request-ID"] == "req-1"

    def test_roles(self):
        install(intake_provider())
        body = {"text": "pothole"}
        assert client.post("/api/v1/cases/intake/analyze", json=body).status_code == 401
        r = client.post("/api/v1/cases/intake/analyze", headers=token("overlooker"), json=body)
        assert r.status_code == 403 and r.json()["error"]["code"] == "AUTH_FORBIDDEN"
        for role in ("citizen", "field_worker", "operator", "city_admin"):
            assert client.post("/api/v1/cases/intake/analyze", headers=token(role), json=body).status_code == 200, role

    def test_empty_request_is_a_422_envelope(self):
        install(intake_provider())
        r = client.post("/api/v1/cases/intake/analyze", headers=token("citizen"), json={})
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_without_any_ai_it_still_answers_in_visible_degraded_mode(self):
        install(None)
        r = client.post("/api/v1/cases/intake/analyze", headers=token("citizen"), json={"text": "pothole near the school"})
        assert r.status_code == 200
        b = r.json()
        assert b["requires_confirmation"] is True and b["ai_metadata"]["degraded"] is True
        assert any(w.startswith(("NO_AI_AVAILABLE", "LOCAL_FALLBACK_USED")) for w in b["warnings"])


# --------------------------------------------------------------------------------------------- fusion (51A.7)
class TestFusion:
    def test_planted_duplicate_is_found_with_contract_shape(self):
        env = install(None)
        r = client.post(f"/api/v1/cases/{PAIR['case_a']}/fusion/analyze", headers=token("operator"))
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["recommendation"] in {"POSSIBLE_DUPLICATE", "RELATED", "NO_MATCH"}
        ids = [m["case_id"] for m in b["matches"]]
        assert PAIR["case_b"] in ids and PAIR["case_a"] not in ids
        m = next(m for m in b["matches"] if m["case_id"] == PAIR["case_b"])
        assert set(m["signals"]) >= {"semantic", "geospatial", "temporal", "visual"} and 0 <= m["similarity"] <= 1
        assert env.analyses.latest(PAIR["case_a"], "fusion") is not None

    def test_errors_and_roles(self):
        install(None)
        assert client.post("/api/v1/cases/does-not-exist/fusion/analyze", headers=token("operator")).json()["error"]["code"] == "CASE_NOT_FOUND"
        for role in ("citizen", "field_worker", "overlooker"):
            r = client.post(f"/api/v1/cases/{PAIR['case_a']}/fusion/analyze", headers=token(role))
            assert r.status_code == 403, role


# --------------------------------------------------------------------------------------------- triage (51A.8)
class TestTriage:
    CASE = PAIR["case_a"]

    def analyze(self, role="operator"):
        return client.post(f"/api/v1/cases/{self.CASE}/triage/analyze", headers=token(role))

    def test_contract_shape_uses_department_code(self):
        env = install(None)
        r = self.analyze()
        assert r.status_code == 200, r.text
        b = r.json()
        rec = b["recommendation"]
        assert set(rec) >= {"severity", "priority", "department", "sla_hours"} and isinstance(rec["sla_hours"], int)
        assert rec["department"].isupper() and rec["department_id"].islower()      # "WATER" / "water_supply"
        assert b["reasons"] and isinstance(b["warnings"], list) and any(w.startswith("RULES_ONLY") for w in b["warnings"])
        assert env.analyses.latest(self.CASE, "triage")["id"] == b["analysis_id"]

    def test_roles(self):
        install(None)
        for role in ("citizen", "field_worker", "overlooker"):
            assert self.analyze(role).status_code == 403, role

    def decide(self, **over):
        rec = self.analyze().json()["recommendation"]
        body = {"severity": rec["severity"], "priority": rec["priority"], "department_id": rec["department_id"], "sla_hours": rec["sla_hours"],
                "reason": "agree", **over}
        return rec, client.post(f"/api/v1/cases/{self.CASE}/triage/decision", headers=token("city_admin", "u-admin"), json=body)

    def test_agreeing_decision_is_recorded_without_override(self):
        env = install(None)
        _, r = self.decide()
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["overridden"] is False and b["overridden_fields"] == [] and b["decided_by"] == "u-admin" and b["audit_event_emitted"] is True
        assert [e["action"] for e in env.audit.events] == ["TRIAGE_DECISION_RECORDED"]
        assert env.repo.decisions[self.CASE][0]["decided_by"] == "u-admin"

    def test_differing_decision_is_an_audited_ai_override(self):
        env = install(None)
        rec, r = self.decide(severity="CRITICAL" if self.analyze().json()["recommendation"]["severity"] != "CRITICAL" else "LOW",
                             sla_hours=1, department_id="WATER", reason="Burst main on site")     # code alias accepted
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["overridden"] is True and {"severity", "sla_hours"} <= set(b["overridden_fields"])
        assert b["decision"]["department_id"] == "water_supply"                                    # canonicalised
        actions = [e["action"] for e in env.audit.events]
        assert actions == ["TRIAGE_DECISION_RECORDED", "AI_RECOMMENDATION_OVERRIDDEN"]
        ov = env.audit.events[-1]
        assert ov["actor_id"] == "u-admin" and ov["entity_id"] == self.CASE and ov["before"]["severity"] == rec["severity"] and ov["after"]["sla_hours"] == 1
        assert b["ai_recommendation"]["severity"] == rec["severity"]

    def test_decision_without_prior_analysis_has_no_recommendation_and_no_override(self):
        env = install(None)
        r = client.post(f"/api/v1/cases/{self.CASE}/triage/decision", headers=token("operator"),
                        json={"severity": "HIGH", "priority": "HIGH", "department_id": "road_maintenance", "sla_hours": 24})
        assert r.status_code == 200 and r.json()["ai_recommendation"] is None and r.json()["overridden"] is False
        assert [e["action"] for e in env.audit.events] == ["TRIAGE_DECISION_RECORDED"]

    def test_validation_and_roles(self):
        install(None)
        url = f"/api/v1/cases/{self.CASE}/triage/decision"
        ok = {"severity": "HIGH", "priority": "HIGH", "department_id": "road_maintenance", "sla_hours": 24}
        assert client.post(url, headers=token("operator"), json={**ok, "department_id": "no_such"}).json()["error"]["code"] == "DEPARTMENT_UNKNOWN"
        assert client.post(url, headers=token("operator"), json={**ok, "severity": "SEVERE"}).status_code == 422
        assert client.post(url, headers=token("operator"), json={**ok, "sla_hours": 0}).status_code == 422
        for role in ("citizen", "field_worker", "overlooker"):
            assert client.post(url, headers=token(role), json=ok).status_code == 403, role


# --------------------------------------------------------------------------------------------- copilot (51A.15)
def copilot_provider(*calls, cited=()):
    return FakeProvider(tool_plan=list(calls), structured={"copilot": {"answer": "Here is what I found.", "cited_ids": list(cited)}})


SEARCH = PlannedToolCall("search_cases", {"unresolved_only": True, "severity": ["HIGH", "CRITICAL"], "limit": 5})
COUNT = PlannedToolCall("count_cases", {"group_by": "status"})
OVERVIEW = PlannedToolCall("get_analytic", {"name": "overview"})


class TestCopilot:
    def ask(self, role="city_admin", sub="u-admin", **body):
        return client.post("/api/v1/copilot/query", headers=token(role, sub), json={"query": "what is open?", **body})

    def test_grounded_answer_with_contract_shape(self):
        env = install(copilot_provider(SEARCH))
        r = self.ask()
        assert r.status_code == 200, r.text
        b = r.json()
        assert set(b) >= {"answer", "data", "citations", "warnings"} and b["data"] and len(b["data"]) <= 5
        assert all(c["type"] == "CASE" for c in b["citations"]) and {c["id"] for c in b["citations"]} == {row["case_id"] for row in b["data"]}
        assert all(row["severity"] in ("HIGH", "CRITICAL") and row["status"] not in ("RESOLVED", "VERIFIED", "REJECTED") for row in b["data"])
        assert "reporter_id" not in json.dumps(b)                                                  # no reporter identity ever returned
        rec = env.analyses.records[-1]
        assert rec["task_type"] == "copilot" and "data" not in rec["result_json"] and rec["actor_id"] == "u-admin"

    def test_actor_comes_from_the_token_not_the_body(self):
        install(copilot_provider(SEARCH))
        r = self.ask(role="citizen", actor_context={"user_id": "x", "role": "CITY_ADMIN"})
        assert r.status_code == 403 and r.json()["error"]["code"] == "AUTH_FORBIDDEN"
        assert client.post("/api/v1/copilot/query", headers=token("field_worker"), json={"query": "x"}).status_code == 403
        assert client.post("/api/v1/copilot/query", json={"query": "x"}).status_code == 401

    def test_overlooker_gets_aggregates_only(self):
        install(copilot_provider(SEARCH, COUNT, OVERVIEW))
        b = self.ask(role="overlooker", sub="u-ovl").json()
        assert any(w.startswith("TOOL_EXECUTION_FAILED: search_cases") for w in b["warnings"])
        assert b["data"] and all("case_id" not in row for row in b["data"])                         # no individual cases
        assert {t["tool"] for t in b["tool_calls"]} == {"count_cases", "get_analytic"}

    def test_department_roles_are_pinned_to_their_department(self):
        env = install(copilot_provider(SEARCH))
        mgr = next(u for u in env.repo.city.users.values() if u["role"] == "DEPARTMENT_MANAGER" and u["department_id"] == "water_supply")
        b = self.ask(role="department_manager", sub=mgr["id"]).json()
        assert b["data"] and {row["department_id"] for row in b["data"]} == {"water_supply"}
        other = client.post("/api/v1/copilot/query", headers=token("department_manager", mgr["id"]), json={"query": "x", "scope": {"department_id": "road_maintenance"}})
        assert other.status_code == 200 and {row["department_id"] for row in other.json()["data"]} <= {"road_maintenance"}
        # a department-scoped role the system cannot place in a department is refused (deny by default)
        denied = self.ask(role="operator", sub="unknown-operator").json()
        assert denied["data"] == [] and any(w.startswith("TOOL_EXECUTION_FAILED") for w in denied["warnings"])

    def test_caller_scope_wins_over_the_model(self):
        env = install(copilot_provider(PlannedToolCall("search_cases", {"ward_label": "W01", "limit": 50})))
        ward = env.repo.city.ward_by_label["W02"]
        b = self.ask(scope={"ward_id": ward}).json()
        assert b["data"] and {row["ward"] for row in b["data"]} == {"W02"} and any(w.startswith("SCOPE_OVERRIDDEN") for w in b["warnings"])

    def test_analytics_tools_reproduce_the_planted_ground_truth(self):
        install(copilot_provider(PlannedToolCall("get_analytic", {"name": "recurrence"}), PlannedToolCall("get_analytic", {"name": "hotspots"})))
        b = self.ask().json()
        subs = {row["subcategory"] for row in b["data"]}
        assert {s["subcategory"] for s in TRUTH["recurring_sites"]} <= subs and {h["subcategory"] for h in TRUTH["hotspots"]} <= subs
        assert all(c["type"] == "ANALYTIC" for c in b["citations"])

    def test_without_provider_it_reports_unavailable_instead_of_inventing_data(self):
        install(None)
        b = self.ask().json()
        assert b["data"] == [] and b["citations"] == [] and any(w.startswith("COPILOT_UNAVAILABLE") for w in b["warnings"])

    def test_query_limits_are_a_422_envelope(self):
        install(copilot_provider(SEARCH))
        r = client.post("/api/v1/copilot/query", headers=token("city_admin"), json={"query": "x" * 1500})
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------------------------- error envelope everywhere (51A.1)
def test_auth_errors_use_the_envelope_and_keep_legacy_detail():
    r = client.get("/api/v1/me/", headers={"Authorization": "Bearer garbage", "X-Request-ID": "abc"})
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "auth.invalid_token" and body["error"]["request_id"] == "abc" and body["detail"]["code"] == "auth.invalid_token"
