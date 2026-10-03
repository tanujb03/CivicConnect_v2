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

from . import vectors
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
        spoken = [t.strip() for t in db.execute(select(EvidenceItem.transcript).where(EvidenceItem.case_id == c.id, EvidenceItem.status == "READY", EvidenceItem.purpose == "REPORT",
                                                                                      EvidenceItem.media_type == "AUDIO", EvidenceItem.transcript.is_not(None))
                                                .order_by(EvidenceItem.created_at)).scalars() if t and t.strip()]           # what the citizen SAID counts as case text too
        written = sig.original_text if sig and sig.original_text else c.description or c.title
        return CaseSnapshot(id=c.id, category=c.category or "other", subcategory=c.subcategory, text="\n".join(x for x in (written, *spoken) if x) or None,
                            latitude=c.latitude, longitude=c.longitude, created_at=c.created_at, status=c.status, support_count=c.support_count, recurrence_count=c.recurrence_count,
                            location_tags=list(c.location_tags or []), incident_active=active is not None, reporter_id=c.reporter_id, department_id=c.department_id,
                            embedding=list(emb.vector) if emb else None, embedding_model=(emb.embedding_model or emb.model) if emb else None, evidence_ids=ev_ids)

    def get_case(self, case_id: str) -> CaseSnapshot | None:
        with session_scope() as db:
            c = db.get(CivicCase, case_id)
            return self._snapshot(db, c) if c else None

    VECTOR_LIMIT = 50           # pgvector path: nearest comparable vectors among the gated cases (= the policy's max_candidates)
    PORTABLE_CAP = 200          # SQLite / no pgvector: gated cases fetched and compared in Python

    @staticmethod
    def _usable(emb: CaseEmbedding | None) -> tuple[list[float] | None, str | None, int]:
        """(vector, embedding_model, dimension) of a stored embedding; rows from before migration 0003 have no embedding_dim / embedding_model, so they are derived."""
        if emb is None or not emb.vector:
            return None, None, 0
        vec = list(emb.vector)
        return vec, (emb.embedding_model or emb.model), (emb.embedding_dim or len(vec))

    @staticmethod
    def _point(case: CaseSnapshot) -> dict:
        return {"lon": case.longitude, "lat": case.latitude}

    @staticmethod
    def _gate_sql(same_category: bool) -> str:
        """The deterministic stage-1 gate on PostgreSQL: category, ST_DWithin radius, time window (the subject itself and rejected cases are never candidates)."""
        return ("FROM civic_cases c WHERE c.id <> :id AND c.status <> 'REJECTED' AND c.created_at BETWEEN :lo AND :hi " + ("AND c.category = :cat " if same_category else "")
                + "AND ST_DWithin(c.geog, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :r)")

    def _gate_pg(self, db, case: CaseSnapshot, lo, hi, radius_m: float, same_category: bool, limit: int) -> list[str]:
        sql = ("SELECT c.id " + self._gate_sql(same_category) + " ORDER BY ST_Distance(c.geog, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography), c.id LIMIT :n")
        return [r[0] for r in db.execute(text(sql), {"id": case.id, "lo": lo, "hi": hi, "cat": case.category, **self._point(case), "r": radius_m, "n": limit})]

    @staticmethod
    def _gate_portable(db, case: CaseSnapshot, lo, hi, radius_m: float, same_category: bool, limit: int) -> list[str]:
        b = bbox_around(case.latitude, case.longitude, radius_m)
        q = select(CivicCase).where(CivicCase.id != case.id, CivicCase.status != "REJECTED", CivicCase.created_at.between(lo, hi),
                                    CivicCase.latitude.between(b[0], b[2]), CivicCase.longitude.between(b[1], b[3]))
        if same_category:
            q = q.where(CivicCase.category == case.category)
        scored = sorted(((haversine_m((case.latitude, case.longitude), (c.latitude, c.longitude)), c.id) for c in db.execute(q).scalars()), key=lambda t: (t[0], t[1]))
        return [cid for d, cid in scored if d <= radius_m][:limit]

    def _rank_pgvector(self, db, case: CaseSnapshot, lo, hi, radius_m: float, same_category: bool, q_vec: list[float], model: str, dim: int, limit: int) -> list[str]:
        """Gated cases ordered by cosine distance, in SQL. The ORDER BY repeats the partial index's cast and ``embedding_dim = D`` is a literal, so the HNSW index of that
        dimension is usable; only vectors of the same ``embedding_model`` and dimension are compared."""
        sql = (f"WITH gated AS (SELECT c.id, ST_Distance(c.geog, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS d {self._gate_sql(same_category)}) "
               f"SELECT e.case_id FROM case_embeddings e JOIN gated g ON g.id = e.case_id WHERE e.embedding_dim = {int(dim)} AND e.embedding_model = :model "
               f"AND e.embedding_vec IS NOT NULL ORDER BY {vectors.vector_order_sql(dim)}, g.d, g.id LIMIT :n")
        params = {"id": case.id, "lo": lo, "hi": hi, "cat": case.category, **self._point(case), "r": radius_m, "model": model, "q": vectors.to_literal(q_vec), "n": limit}
        return [r[0] for r in db.execute(text(sql), params)]

    @staticmethod
    def _rank_python(db, pool: list[str], q_vec: list[float] | None, model: str | None, dim: int) -> list[str]:
        """Python cosine over the gated pool (nearest-first order in, same order out for ties and for cases without a comparable vector, which follow the ranked ones)."""
        if q_vec is None or not pool:
            return list(pool)
        embs = {e.case_id: e for e in db.execute(select(CaseEmbedding).where(CaseEmbedding.case_id.in_(pool))).scalars()}
        sims: dict[str, float] = {}
        for cid in pool:
            vec, m, d = SqlCaseRepository._usable(embs.get(cid))
            if vec is not None and m == model and d == dim and len(vec) == dim:
                sims[cid] = vectors.cosine(q_vec, vec)
        order = {cid: i for i, cid in enumerate(pool)}
        return sorted(sims, key=lambda c: (-sims[c], order[c])) + [c for c in pool if c not in sims]

    def fusion_candidates(self, case: CaseSnapshot, *, radius_m: float, time_window_days: float, max_candidates: int, same_category: bool) -> list[CaseSnapshot]:
        """AI-2 candidates (design §37). Stage 1 is the deterministic gate: category, spatial radius, time window (PostGIS ``ST_DWithin`` on PostgreSQL, bounding box + haversine
        elsewhere). Stage 2 ranks the gated cases by embedding similarity to the subject, comparing ONLY vectors with the same ``embedding_model`` and dimension: in SQL with
        pgvector (cosine distance, limit 50) when PostgreSQL has the extension, else in Python over at most 200 gated cases. Gated cases without a comparable vector follow, nearest
        first, so the lexical / geo / time signals still see them; their incomparable vectors are dropped from the snapshot."""
        from datetime import timedelta
        lo, hi = case.created_at - timedelta(days=time_window_days), case.created_at + timedelta(days=time_window_days)
        with session_scope() as db:
            q_vec, model, dim = self._usable(db.get(CaseEmbedding, case.id))
            pg = db.bind.dialect.name == "postgresql"
            if pg and q_vec is not None and vectors.vector_search_available(db):
                nearest = self._gate_pg(db, case, lo, hi, radius_m, same_category, max_candidates)
                ranked = self._rank_pgvector(db, case, lo, hi, radius_m, same_category, q_vec, model, dim, min(self.VECTOR_LIMIT, max_candidates))
                ids = ranked + [i for i in nearest if i not in set(ranked)]
            else:
                pool = (self._gate_pg(db, case, lo, hi, radius_m, same_category, self.PORTABLE_CAP) if pg
                        else self._gate_portable(db, case, lo, hi, radius_m, same_category, self.PORTABLE_CAP))
                ids = self._rank_python(db, pool, q_vec, model, dim)
            snaps = [self._snapshot(db, c) for c in (db.get(CivicCase, i) for i in ids[:max_candidates]) if c is not None]
            if q_vec is not None:
                for sn in snaps:
                    if sn.embedding is not None and (sn.embedding_model != model or len(sn.embedding) != dim):
                        sn.embedding, sn.embedding_model = None, None
            return snaps

    def save_embedding(self, case_id: str, vector: list[float], model: str) -> dict:
        """The JSON vector everywhere (SQLite, no extension) AND, on PostgreSQL with pgvector, ``embedding_vec`` + ``embedding_dim`` + ``embedding_model``."""
        vec = [float(x) for x in vector]
        dim = len(vec)
        if not 0 < dim <= vectors.MAX_VECTOR_DIM:
            raise ValueError(f"unsupported embedding dimension {dim}")
        with session_scope() as db:
            row = db.get(CaseEmbedding, case_id)
            native = vectors.vector_search_available(db)
            if row is None:
                row = CaseEmbedding(case_id=case_id, model=model, vector=vec)
                db.add(row)
            elif native:
                # clear the old pgvector value FIRST: the partial indexes evaluate ``embedding_vec::vector(D) WHERE embedding_dim = D``, so a stored vector of another
                # dimension must never meet the new ``embedding_dim`` (that raises "expected N dimensions")
                db.execute(text("UPDATE case_embeddings SET embedding_vec = NULL WHERE case_id = :id"), {"id": case_id})
            row.model, row.vector, row.embedding_dim, row.embedding_model, row.created_at = model, vec, dim, model, _now()
            db.flush()
            stored = False
            if native:
                try:
                    with db.begin_nested():
                        db.execute(text("UPDATE case_embeddings SET embedding_vec = CAST(:v AS vector) WHERE case_id = :id"), {"v": vectors.to_literal(vec), "id": case_id})
                    stored = True
                except Exception as e:                                # noqa: BLE001  (the JSON vector is already stored; pgvector is an accelerator)
                    log.warning("pgvector column not written for %s: %s", case_id, type(e).__name__)
                    with db.begin_nested():
                        db.execute(text("UPDATE case_embeddings SET embedding_vec = NULL WHERE case_id = :id"), {"id": case_id})
            return {"dim": dim, "model": model, "pgvector": stored}

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


    def pending_audio(self, case_id: str) -> list[str]:
        with session_scope() as db:
            return list(db.execute(select(EvidenceItem.id).where(EvidenceItem.case_id == case_id, EvidenceItem.status == "READY", EvidenceItem.purpose == "REPORT",
                                                                 EvidenceItem.media_type == "AUDIO", EvidenceItem.transcript.is_(None)).order_by(EvidenceItem.created_at)).scalars())

    def save_transcript(self, evidence_id: str, text: str, language: str | None) -> None:       # noqa: ARG002 (the language lives on the AIAnalysis row; the column holds the text)
        with session_scope() as db:
            ev = db.get(EvidenceItem, evidence_id)
            if ev is not None and not (ev.transcript or "").strip():
                ev.transcript = text


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
