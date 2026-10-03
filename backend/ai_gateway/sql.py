"""SQL / PostGIS implementations of the gateway ports (``ports.py``): the AI path reads and writes the same database as the REST API.

Each method opens a short transaction of its own (``session_scope``), so the gateway also works from queue workers. Callers must commit what they want the AI to see
BEFORE calling the gateway (the route handlers do).

The copilot tools and the AI-5 fact source reuse the demo-city implementations over live rows: ``DbCity`` serves the same dict rows from the database, so the tool
logic (RBAC, scoping, grounding) exists once and is covered by the same tests.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text

from ai.inference.schemas import EvidenceInput
from backend.db.session import session_scope
from backend.models import AIAnalysis, CaseEmbedding, CivicCase, Department, EvidenceItem, Incident, IncidentCase, ReportSignal, User, Ward
from backend.services import evidence as evidence_service
from backend.services import triage as triage_service
from backend.services.audit import record_audit
from backend.services.city_rows import case_rows
from backend.services.geo import bbox_around, haversine_m
from backend.storage import get_storage

from .memory import DemoCity, DemoCityFactSource, DemoCityToolExecutor
from .ports import CaseSnapshot

log = logging.getLogger("civicconnect.ai_gateway.sql")
SYSTEM_USER_ID = "system"
MAX_AI_MEDIA_BYTES = 12 * 1024 * 1024


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DbCity(DemoCity):
    """The demo city's read interface over the live database (no files)."""

    def __init__(self) -> None:                                   # noqa: D107 (deliberately does not call the file-loading base initialiser)
        self.directory = None

    @property
    def cases(self) -> list[dict]:
        with session_scope() as db:
            return case_rows(db, True, _now())

    @property
    def by_id(self) -> dict[str, dict]:
        return {c["id"]: c for c in self.cases}

    @property
    def wards(self) -> dict[str, dict]:
        with session_scope() as db:
            return {w.id: {"id": w.id, "label": w.label or w.name, "name": w.name} for w in db.execute(select(Ward)).scalars()}

    @property
    def ward_by_label(self) -> dict[str, str]:
        return {w["label"]: i for i, w in self.wards.items()}

    @property
    def departments(self) -> dict[str, dict]:
        with session_scope() as db:
            return {d.id: {"id": d.id, "name": d.name, "code": d.code} for d in db.execute(select(Department)).scalars()}

    @property
    def incidents(self) -> list[dict]:
        with session_scope() as db:
            return [{"id": i.id, "title": i.title, "status": i.status, "ward_id": i.ward_id, "started_at": i.started_at.isoformat(),
                     "center": {"latitude": i.center_lat, "longitude": i.center_lon}} for i in db.execute(select(Incident)).scalars()]

    @property
    def users(self) -> dict[str, dict]:
        with session_scope() as db:
            return {u.id: {"id": u.id, "role": u.role, "department_id": u.department_id} for u in db.execute(select(User)).scalars()}


class SqlCaseRepository:
    def __init__(self) -> None:
        self.city = DbCity()

    @staticmethod
    def _snapshot(db, c: CivicCase) -> CaseSnapshot:
        sig = db.execute(select(ReportSignal).where(ReportSignal.case_id == c.id, ReportSignal.is_primary.is_(True))).scalars().first()
        emb = db.get(CaseEmbedding, c.id)
        ev_ids = list(db.execute(select(EvidenceItem.id).where(EvidenceItem.case_id == c.id, EvidenceItem.status == "READY", EvidenceItem.purpose == "REPORT")
                                 .order_by(EvidenceItem.created_at)).scalars())
        active = db.execute(select(IncidentCase.case_id).join(Incident, Incident.id == IncidentCase.incident_id).where(IncidentCase.case_id == c.id, Incident.status == "ACTIVE")).first()
        return CaseSnapshot(id=c.id, category=c.category or "other", subcategory=c.subcategory, text=(sig.original_text if sig and sig.original_text else c.description or c.title),
                            latitude=c.latitude, longitude=c.longitude, created_at=c.created_at, status=c.status, support_count=c.support_count, recurrence_count=c.recurrence_count,
                            location_tags=list(c.location_tags or []), incident_active=active is not None, reporter_id=c.reporter_id, department_id=c.department_id,
                            embedding=list(emb.vector) if emb else None, embedding_model=emb.model if emb else None, evidence_ids=ev_ids)

    def get_case(self, case_id: str) -> CaseSnapshot | None:
        with session_scope() as db:
            c = db.get(CivicCase, case_id)
            return self._snapshot(db, c) if c else None

    def fusion_candidates(self, case: CaseSnapshot, *, radius_m: float, time_window_days: float, max_candidates: int, same_category: bool) -> list[CaseSnapshot]:
        """Candidates bounded by the fusion policy (design §37 stage 1): category, spatial radius, time window. PostGIS ``ST_DWithin`` on PostgreSQL, bounding box + haversine elsewhere."""
        from datetime import timedelta
        lo, hi = case.created_at - timedelta(days=time_window_days), case.created_at + timedelta(days=time_window_days)
        with session_scope() as db:
            if db.bind.dialect.name == "postgresql":
                sql = ("SELECT id FROM civic_cases WHERE id <> :id AND status <> 'REJECTED' AND created_at BETWEEN :lo AND :hi "
                       + ("AND category = :cat " if same_category else "")
                       + "AND ST_DWithin(geog, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :r) "
                         "ORDER BY ST_Distance(geog, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography), id LIMIT :n")
                ids = [r[0] for r in db.execute(text(sql), {"id": case.id, "lo": lo, "hi": hi, "cat": case.category, "lon": case.longitude, "lat": case.latitude, "r": radius_m, "n": max_candidates})]
                cands = [db.get(CivicCase, i) for i in ids]
            else:
                b = bbox_around(case.latitude, case.longitude, radius_m)
                q = select(CivicCase).where(CivicCase.id != case.id, CivicCase.status != "REJECTED", CivicCase.created_at.between(lo, hi),
                                            CivicCase.latitude.between(b[0], b[2]), CivicCase.longitude.between(b[1], b[3]))
                if same_category:
                    q = q.where(CivicCase.category == case.category)
                scored = sorted(((haversine_m((case.latitude, case.longitude), (c.latitude, c.longitude)), c.id, c) for c in db.execute(q).scalars()), key=lambda t: (t[0], t[1]))
                cands = [c for d, _, c in scored if d <= radius_m][:max_candidates]
            return [self._snapshot(db, c) for c in cands]

    def save_triage_decision(self, case_id: str, decision: dict, actor_id: str) -> None:
        with session_scope() as db:
            case = db.get(CivicCase, case_id)
            user = db.get(User, actor_id)
            triage_service.apply_decision(db, case, decision, actor_id, user.role if user else None)

    def department_of(self, user_id: str) -> str | None:
        with session_scope() as db:
            u = db.get(User, user_id)
            return u.department_id if u else None


class SqlEvidenceResolver:
    """Evidence the actor may see, as bytes handed to the adapter (it never fetches by id or URL). ``system`` (queue workers, hooks) sees all READY evidence."""

    def resolve(self, evidence_id: str, actor_id: str) -> EvidenceInput | None:
        with session_scope() as db:
            ev = db.get(EvidenceItem, evidence_id)
            if ev is None or ev.status != "READY" or ev.media_type == "VIDEO":
                return None
            if actor_id != SYSTEM_USER_ID:
                user = db.get(User, actor_id)
                if user is None or not evidence_service.can_view(db, user, ev):
                    return None
            if ev.size_bytes > MAX_AI_MEDIA_BYTES:
                return None
            try:
                data = get_storage().get(ev.object_key)
            except Exception as e:
                log.warning("evidence %s unreadable: %s", evidence_id, type(e).__name__)
                return None
            return EvidenceInput(evidence_id=ev.id, media_type=ev.media_type, mime_type=ev.mime_type, data=data, transcript=ev.transcript, captured_at=ev.captured_at)


class SqlAnalysisStore:
    KNOWN = {"task_type", "case_id", "actor_id", "confidence", "model", "model_version", "prompt_version", "schema_version", "source", "degraded", "result_json", "created_at"}

    def save(self, record: dict) -> str:
        with session_scope() as db:
            row = AIAnalysis(case_id=record.get("case_id"), actor_id=record.get("actor_id"), task_type=record["task_type"], model=record.get("model"), model_version=record.get("model_version"),
                             prompt_version=record.get("prompt_version"), schema_version=record.get("schema_version"), source=record.get("source"), degraded=record.get("degraded"),
                             confidence=record.get("confidence"), result_json=record.get("result_json") or {}, extra={k: v for k, v in record.items() if k not in self.KNOWN})
            db.add(row)
            db.flush()
            return row.id

    def latest(self, case_id: str, task_type: str) -> dict | None:
        with session_scope() as db:
            r = db.execute(select(AIAnalysis).where(AIAnalysis.case_id == case_id, AIAnalysis.task_type == task_type).order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())).scalars().first()
            if r is None:
                return None
            return {"id": r.id, "case_id": r.case_id, "task_type": r.task_type, "actor_id": r.actor_id, "confidence": r.confidence, "model": r.model, "result_json": r.result_json,
                    "created_at": r.created_at.isoformat(), **(r.extra or {})}


class SqlAuditSink:
    def emit(self, *, actor_id: str, action: str, entity_type: str, entity_id: str, before: dict | None, after: dict | None) -> bool:
        with session_scope() as db:
            record_audit(db, actor_id=None if actor_id == SYSTEM_USER_ID else actor_id, action=action, entity_type=entity_type, entity_id=entity_id, before=before, after=after)
        return True


class DbToolExecutor(DemoCityToolExecutor):
    """Copilot tools over live rows (read-only, RBAC per actor); ``now`` is the real clock."""

    def __init__(self, repo: SqlCaseRepository):
        self.repo, self.city = repo, repo.city

    @property
    def now(self) -> datetime:                                    # type: ignore[override]
        return _now()


class DbFactSource(DemoCityFactSource):
    def __init__(self, executor: DbToolExecutor):
        self.executor, self.city = executor, executor.city

    @property
    def now(self) -> datetime:                                    # type: ignore[override]
        return _now()


def build_sql_gateway() -> Any:
    from .deps import build_ai_service
    from .envfile import load_env_file
    from .service import AIGateway
    from .text_model import build_from_env as build_text_models
    from .vision import build_from_env as build_vision
    load_env_file()
    repo = SqlCaseRepository()
    executor = DbToolExecutor(repo)
    classifier, embedder = build_text_models()
    ai = build_ai_service(executor, classifier)
    return AIGateway(ai=ai, repo=repo, evidence=SqlEvidenceResolver(), analyses=SqlAnalysisStore(), audit=SqlAuditSink(), facts=DbFactSource(executor), vision=build_vision(), embedder=embedder)
