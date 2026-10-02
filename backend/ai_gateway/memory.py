"""Demo-city-backed implementations of the gateway ports (SYNTHETIC data; design §58).

They exist so the AI path (intake -> fusion -> triage -> decision -> copilot) works end to end before the SQL repositories do, and so
tests/demos have deterministic cases. They are NOT a production store: replace them through ``configure_gateway`` with SQLAlchemy/PostGIS
implementations of the same ports.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from pydantic import BaseModel

from ai.evaluation.analytics_facts import build_fact_set
from ai.evaluation.analytics_reference import haversine_m, hotspots, recurring_sites
from ai.inference.errors import ToolPermissionDenied
from ai.inference.copilot.tools import ToolResult
from ai.inference.schemas import ActorContext, AnalyticsFactSet, Citation, CopilotScope, EvidenceInput

from .ports import CaseSnapshot

log = logging.getLogger("civicconnect.ai_gateway")

DEMO_DIR = Path(__file__).resolve().parents[2] / "ai" / "evaluation" / "datasets" / "demo_city_v1"
DEMO_NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
RESOLVED_STATES = {"VERIFIED", "RESOLVED", "REJECTED"}
DEPARTMENT_SCOPED_ROLES = {"operator", "department_manager"}
# demo-city user roles -> the backend's JWT role vocabulary (backend/models/user.py)
ROLE_ALIASES = {"department_operator": "operator", "city_administrator": "city_admin"}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def normalize_role(role: str | None) -> str:
    r = (role or "").strip().lower()
    return ROLE_ALIASES.get(r, r)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class DemoCity:
    """Loads the committed demo city once. Missing directory => empty city (the gateway then simply has no candidates)."""

    def __init__(self, directory: str | Path | None = None):
        d = Path(directory or os.environ.get("AI_GATEWAY_DEMO_CITY_DIR") or DEMO_DIR)
        self.directory = d
        self.cases = _read(d / "cases.jsonl")
        self.wards = {w["id"]: w for w in _read(d / "wards.jsonl")}
        self.departments = {x["id"]: x for x in _read(d / "departments.jsonl")}
        self.users = {u["id"]: u for u in _read(d / "users.jsonl")}
        self.incidents = _read(d / "incidents.jsonl")
        self.signals = {s["case_id"]: s for s in _read(d / "report_signals.jsonl") if s.get("is_primary")}
        self.by_id = {c["id"]: c for c in self.cases}
        self.ward_by_label = {w["label"]: w["id"] for w in self.wards.values()}

    def text_of(self, c: dict) -> str | None:
        s = self.signals.get(c["id"])
        return (s or {}).get("original_text") or c.get("canonical_description")

    def snapshot(self, c: dict) -> CaseSnapshot:
        loc = c["location"]
        return CaseSnapshot(
            id=c["id"], category=c["category"], subcategory=c.get("subcategory"), text=self.text_of(c),
            latitude=loc["latitude"], longitude=loc["longitude"], created_at=_dt(c["created_at"]), status=c.get("status"),
            support_count=int(c.get("support_count", 0)), recurrence_count=int(c.get("recurrence_count", 0)),
            location_tags=list(c.get("location_tags") or []), incident_active=bool(c.get("incident_id")),
            reporter_id=(self.signals.get(c["id"]) or {}).get("reporter_id"), department_id=c.get("department_id"))


class DemoCityRepository:
    """CaseRepository over the demo city (+ cases registered at runtime, e.g. by tests)."""

    def __init__(self, city: DemoCity | None = None):
        self.city = city or DemoCity()
        self._extra: dict[str, CaseSnapshot] = {}
        self.decisions: dict[str, list[dict]] = defaultdict(list)

    def register_case(self, case: CaseSnapshot) -> None:
        self._extra[case.id] = case

    def _all(self) -> list[CaseSnapshot]:
        return [self.city.snapshot(c) for c in self.city.cases] + list(self._extra.values())

    def get_case(self, case_id: str) -> CaseSnapshot | None:
        if case_id in self._extra:
            return self._extra[case_id]
        c = self.city.by_id.get(case_id)
        return self.city.snapshot(c) if c else None

    def fusion_candidates(self, case: CaseSnapshot, *, radius_m: float, time_window_days: float, max_candidates: int, same_category: bool) -> list[CaseSnapshot]:
        picked = []
        for o in self._all():
            if o.id == case.id or (same_category and o.category != case.category):
                continue
            if abs((o.created_at - case.created_at).total_seconds()) > time_window_days * 86400:
                continue
            d = haversine_m((case.latitude, case.longitude), (o.latitude, o.longitude))
            if d <= radius_m:
                picked.append((d, o.id, o))
        return [o for _, _, o in sorted(picked, key=lambda t: (t[0], t[1]))[:max_candidates]]

    def save_triage_decision(self, case_id: str, decision: dict, actor_id: str) -> None:
        self.decisions[case_id].append({**decision, "decided_by": actor_id})

    def department_of(self, user_id: str) -> str | None:
        return (self.city.users.get(user_id) or {}).get("department_id")


class MemoryEvidenceResolver:
    """Evidence registry. Register transcripts/bytes the way the real resolver would hand back signed storage objects."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[EvidenceInput, str | None]] = {}

    def register(self, evidence: EvidenceInput, owner_id: str | None = None) -> None:
        self._items[evidence.evidence_id] = (evidence, owner_id)

    def resolve(self, evidence_id: str, actor_id: str) -> EvidenceInput | None:
        item = self._items.get(evidence_id)
        if item is None:
            return None
        evidence, owner = item
        return evidence if owner in (None, actor_id) else None   # evidence uploaded by someone else is not visible


class MemoryAnalysisStore:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def save(self, record: dict) -> str:
        rid = str(uuid.uuid4())
        self.records.append({"id": rid, **record})
        return rid

    def latest(self, case_id: str, task_type: str) -> dict | None:
        for r in reversed(self.records):
            if r.get("case_id") == case_id and r.get("task_type") == task_type:
                return r
        return None


class MemoryAuditSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, *, actor_id: str, action: str, entity_type: str, entity_id: str, before: dict | None, after: dict | None) -> bool:
        self.events.append({"id": str(uuid.uuid4()), "at": datetime.now(timezone.utc).isoformat(), "actor_id": actor_id, "action": action,
                            "entity_type": entity_type, "entity_id": entity_id, "before": before, "after": after})
        return True


class EventStreamAuditSink:
    """Records in memory (the source of truth until the AuditEvent table exists) and propagates to the Redis ``civic:audit`` stream, best effort."""

    def __init__(self, inner: MemoryAuditSink | None = None):
        self.inner = inner or MemoryAuditSink()

    @property
    def events(self) -> list[dict]:
        return self.inner.events

    def emit(self, *, actor_id: str, action: str, entity_type: str, entity_id: str, before: dict | None, after: dict | None) -> bool:
        ok = self.inner.emit(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, before=before, after=after)
        try:
            from backend.events import emit_audit
            emit_audit(actor_id, action, entity_id, {"entity_type": entity_type, "before": before, "after": after})
        except Exception as e:  # propagation must never break the request
            log.warning("audit propagation skipped: %s", type(e).__name__)
        return ok


# --------------------------------------------------------------------------- copilot tools
def _cite_id(*parts: Any) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "civicconnect-demo-analytic/" + "/".join(map(str, parts))))


class DemoCityToolExecutor:
    """ToolExecutor (§4 of the handoff) over the demo city. Read-only, no SQL, RBAC per ``actor``.

    * ``overlooker`` (§51A.18 "scoped") may only call count/analytic tools -> aggregates, never individual cases.
    * ``operator``/``department_manager`` are pinned to their own department; with no known department they are refused (deny by default).
    * No reporter identity is ever returned.
    """

    def __init__(self, repo: DemoCityRepository, now: datetime = DEMO_NOW):
        self.repo = repo
        self.city = repo.city
        self.now = now

    # -- scope ------------------------------------------------------------------------------------------------
    def _filtered(self, args: BaseModel, scope: CopilotScope, actor: ActorContext) -> list[dict]:
        role = normalize_role(actor.role)
        a = args.model_dump()
        dept = a.get("department_id")
        if role in DEPARTMENT_SCOPED_ROLES:
            own = self.repo.department_of(actor.user_id)
            if own is None:
                raise ToolPermissionDenied("department scope unknown for this actor")
            if dept not in (None, own):
                raise ToolPermissionDenied("other department")
            dept = own
        ward = a.get("ward_id") or (self.city.ward_by_label.get(a["ward_label"]) if a.get("ward_label") else None)
        if a.get("ward_label") and ward is None:
            return []
        lo, hi = a.get("created_from") or scope.from_, a.get("created_until") or scope.until
        out = []
        for c in self.city.cases:
            if a.get("category") and c["category"] != a["category"]:
                continue
            if a.get("subcategory") and c.get("subcategory") != a["subcategory"]:
                continue
            if a.get("status") and c["status"] not in a["status"]:
                continue
            if a.get("unresolved_only") and c["status"] in RESOLVED_STATES:
                continue
            if a.get("severity") and c["severity"] not in a["severity"]:
                continue
            if a.get("priority") and c["priority"] not in a["priority"]:
                continue
            if ward and c["ward_id"] != ward:
                continue
            if dept and c["department_id"] != dept:
                continue
            created = _dt(c["created_at"])
            if a.get("older_than_days") is not None and (self.now - created).days < a["older_than_days"]:
                continue
            if lo and created < lo.astimezone(timezone.utc):
                continue
            if hi and created > hi.astimezone(timezone.utc):
                continue
            out.append(c)
        return out

    def _row(self, c: dict) -> dict:
        return {"case_id": c["id"], "public_case_id": c["public_case_id"], "title": c["title"], "category": c["category"],
                "subcategory": c.get("subcategory"), "status": c["status"], "severity": c["severity"], "priority": c["priority"],
                "ward": (self.city.wards.get(c["ward_id"]) or {}).get("label"), "department_id": c.get("department_id"),
                "created_at": c["created_at"], "support_count": c["support_count"], "sla_breached": c["sla_breached"], "synthetic": True}

    def scoped_cases(self, *, ward_id: str | None, department_id: str | None, actor: ActorContext) -> list[dict]:
        """Cases the actor may see inside the requested ward/department (department-scoped roles are pinned; unknown department => ToolPermissionDenied)."""
        return self._filtered(_Window(ward_id=ward_id, department_id=department_id), CopilotScope(), actor)

    # -- tools ------------------------------------------------------------------------------------------------
    def execute(self, tool: str, arguments: BaseModel, *, scope: CopilotScope, actor: ActorContext) -> ToolResult:
        role = normalize_role(actor.role)
        if tool == "search_cases":
            if role == "overlooker":
                raise ToolPermissionDenied("overlookers see aggregates only")
            return self._search(arguments, scope, actor)
        if tool == "count_cases":
            return self._count(arguments, scope, actor)
        if tool == "get_analytic":
            return self._analytic(arguments, scope, actor)
        raise ToolPermissionDenied(f"unknown tool {tool}")

    def _search(self, args: BaseModel, scope: CopilotScope, actor: ActorContext) -> ToolResult:
        cases = self._filtered(args, scope, actor)
        key = {"priority": lambda c: (-c["priority_score"], c["created_at"]), "age": lambda c: c["created_at"],
               "support": lambda c: (-c["support_count"], c["created_at"])}[args.sort]  # type: ignore[attr-defined]
        cases = sorted(cases, key=key)
        limit = args.limit  # type: ignore[attr-defined]
        rows = [self._row(c) for c in cases[:limit]]
        return ToolResult(rows=rows, citations=[Citation(type="CASE", id=r["case_id"]) for r in rows], truncated=len(cases) > limit)

    def _count(self, args: BaseModel, scope: CopilotScope, actor: ActorContext) -> ToolResult:
        cases = self._filtered(args, scope, actor)
        by = args.group_by  # type: ignore[attr-defined]
        field = {"category": "category", "status": "status", "severity": "severity", "priority": "priority",
                 "ward": "ward_id", "department": "department_id"}[by]
        counts = Counter(c[field] for c in cases)
        if by == "ward":
            counts = Counter({(self.city.wards.get(k) or {}).get("label", k): v for k, v in counts.items()})
        rows = [{"group_by": by, "group": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))]
        return ToolResult(rows=rows, citations=[Citation(type="ANALYTIC", id=_cite_id("count_cases", by, args.model_dump_json(exclude_none=True)))])

    def _analytic(self, args: BaseModel, scope: CopilotScope, actor: ActorContext) -> ToolResult:
        name = args.name  # type: ignore[attr-defined]
        cases = self._filtered(_Window(ward_id=getattr(args, "ward_id", None), department_id=getattr(args, "department_id", None)), scope, actor)
        cite = [Citation(type="ANALYTIC", id=_cite_id("get_analytic", name))]
        if name == "overview":
            statuses = Counter(c["status"] for c in cases)
            open_n = sum(v for k, v in statuses.items() if k not in RESOLVED_STATES)
            rows = [{"metric": "total_cases", "value": len(cases)}, {"metric": "open_cases", "value": open_n},
                    {"metric": "sla_breached", "value": sum(bool(c["sla_breached"]) for c in cases)},
                    *({"metric": f"status:{k}", "value": v} for k, v in sorted(statuses.items()))]
            active = [i for i in self.city.incidents if i.get("status") == "ACTIVE"]
            rows.append({"metric": "active_incidents", "value": len(active)})
            return ToolResult(rows=rows, citations=cite + [Citation(type="INCIDENT", id=i["id"]) for i in active])
        if name == "hotspots":
            rows = [{k: h[k] for k in ("subcategory", "recent_cases", "baseline_cases", "ratio_vs_baseline", "center")} for h in hotspots(cases, self.now)]
            return ToolResult(rows=rows, citations=cite)
        if name == "recurrence":
            rows = [{k: s[k] for k in ("subcategory", "n_cases", "n_resolved", "n_reopened", "center", "first_at", "last_at")} for s in recurring_sites(cases)]
            return ToolResult(rows=rows, citations=cite)
        if name == "department_performance":
            by_dep: dict[str, list[dict]] = defaultdict(list)
            for c in cases:
                by_dep[c["department_id"] or "unassigned"].append(c)
            rows = []
            for dep, items in sorted(by_dep.items()):
                days = [(_dt(c["closed_at"]) - _dt(c["created_at"])).total_seconds() / 86400 for c in items if c.get("closed_at") and c["status"] == "RESOLVED"]
                rows.append({"department_id": dep, "cases": len(items), "resolved": sum(c["status"] == "RESOLVED" for c in items),
                             "sla_breached": sum(bool(c["sla_breached"]) for c in items),
                             "median_resolution_days": round(median(days), 1) if days else None})
            return ToolResult(rows=rows, citations=cite)
        if name == "ward_comparison":
            by_ward: dict[str, list[dict]] = defaultdict(list)
            for c in cases:
                by_ward[(self.city.wards.get(c["ward_id"]) or {}).get("label", "?")].append(c)
            rows = [{"ward": w, "cases": len(v), "open": sum(c["status"] not in RESOLVED_STATES for c in v),
                     "sla_breached": sum(bool(c["sla_breached"]) for c in v)} for w, v in sorted(by_ward.items())]
            return ToolResult(rows=rows, citations=cite)
        raise ToolPermissionDenied(f"unknown analytic {name}")


class _Window(BaseModel):
    """Filter carrier used by analytics (ward/department only; the caller's scope dates are applied by ``_filtered``)."""

    ward_id: str | None = None
    department_id: str | None = None


class DemoCityFactSource:
    """AnalyticsFactSource over the demo city, scoped exactly like the copilot executor."""

    def __init__(self, executor: DemoCityToolExecutor):
        self.executor, self.city, self.now = executor, executor.city, executor.now

    def facts(self, *, actor_id: str, role: str, ward_id: str | None, department_id: str | None) -> AnalyticsFactSet:
        cases = self.executor.scoped_cases(ward_id=ward_id, department_id=department_id, actor=ActorContext(user_id=actor_id, role=role))
        parts = ["Synthetic demo city"]
        if ward_id:
            parts.append(f"ward {(self.city.wards.get(ward_id) or {}).get('label', ward_id)}")
        if department_id:
            parts.append((self.city.departments.get(department_id) or {}).get("name", department_id))
        return build_fact_set(cases, self.city.wards, self.city.departments, self.city.incidents, self.now, scope_label=", ".join(parts))
