"""Asynchronous AI enrichment of a new case (design §23 / Parth plan phase D): the queue worker calls this for ``civic:ai_jobs`` messages.

The case never waits for it and nothing here decides anything. Jobs, in the order they are queued:

* ``transcribe``: speech-to-text (Groq Whisper through the provider) of the case's report audio; transcript + detected language go on the evidence item and on a
  ``transcription`` AIAnalysis. No provider, or a provider that is down, degrades to a visible warning on that analysis and on the timeline.
* ``embed``: the case text -> a vector (local M7 if ``AI_EMBED_ONNX_PATH`` is set, else the provider's embedder, else skipped with a warning), stored as the JSON vector AND in
  the pgvector columns where they exist.
* ``triage``: the AI-3 recommendation, so the operator opens a case that is already analysed.
* ``fusion``: AI-2 duplicate candidates as ``POSSIBLE_DUPLICATE`` relations a human confirms or dismisses.
"""
from __future__ import annotations

import logging

from sqlalchemy import or_, select

from backend.db.session import session_scope
from backend.models import CaseRelation
from backend.services.workflow import add_event

log = logging.getLogger("civicconnect.ai_jobs")
RELATION_FOR = {"POSSIBLE_DUPLICATE": "POSSIBLE_DUPLICATE", "RELATED": "RELATED"}


def _internal_event(case_id: str, event_type: str, metadata: dict) -> None:
    with session_scope() as db:
        add_event(db, case_id, event_type, actor_id=None, actor_role="AI", visibility="INTERNAL", metadata=metadata)


def run_job(job_type: str, case_id: str) -> str | None:
    """Returns a short outcome string (also used by tests); never raises."""
    try:
        from backend.ai_gateway import get_gateway
        from backend.ai_gateway.service import SYSTEM_ACTOR
        gw = get_gateway()
        if gw.repo.get_case(case_id) is None:
            return "skipped: case not in the gateway's store"
        if job_type == "triage":
            gw.triage(case_id, SYSTEM_ACTOR)
            return "triage stored"
        if job_type == "transcribe":
            out = gw.transcribe_case(case_id, SYSTEM_ACTOR)
            if out["status"] != "nothing_to_do":
                _internal_event(case_id, "AUDIO_TRANSCRIBED" if out["transcribed"] else "AUDIO_NOT_TRANSCRIBED",
                                {"transcribed": out["transcribed"], "detected_language": out["detected_language"], "warnings": out["warnings"], "analysis_id": out["analysis_id"]})
            return f"transcribe: {out['status']} ({out.get('transcribed', 0)})"
        if job_type == "embed":
            out = gw.embed_case(case_id, SYSTEM_ACTOR)
            _internal_event(case_id, "CASE_EMBEDDED" if out["stored"] else "EMBEDDING_SKIPPED",
                            {"stored": out["stored"], "model": out["model"], "dim": out["dim"], "pgvector": out["pgvector"], "source": out["source"], "warnings": out["warnings"],
                             "analysis_id": out["analysis_id"]})
            return f"embed: {'stored' if out['stored'] else 'skipped'}" + (f" ({out['model']}, {out['dim']}d, pgvector={out['pgvector']})" if out["stored"] else "")
        if job_type == "fusion":
            res = gw.fusion(case_id, SYSTEM_ACTOR)
            rel = RELATION_FOR.get(res.recommendation)
            if not rel or not res.matches:
                return f"fusion: {res.recommendation}"
            with session_scope() as db:
                for m in res.matches[:5]:
                    other = m.case_id
                    exists = db.execute(select(CaseRelation.id).where(or_((CaseRelation.case_a == case_id) & (CaseRelation.case_b == other),
                                                                         (CaseRelation.case_a == other) & (CaseRelation.case_b == case_id)))).first()
                    if not exists:
                        db.add(CaseRelation(case_a=case_id, case_b=other, relation_type=rel, similarity_score=m.similarity, created_by="ai"))
                add_event(db, case_id, "DUPLICATE_CANDIDATES_FOUND", actor_id=None, actor_role="AI", visibility="INTERNAL",
                          metadata={"matches": [{"case_id": m.case_id, "similarity": m.similarity} for m in res.matches[:5]], "recommendation": res.recommendation})
            return f"fusion: {res.recommendation} ({len(res.matches)})"
        return f"skipped: unknown job {job_type}"
    except Exception as e:
        log.warning("ai job %s for %s failed: %s: %s", job_type, case_id, type(e).__name__, e)
        return f"failed: {type(e).__name__}"
