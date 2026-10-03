"""Cases as plain dicts in the demo-city row format (the shape ``ai.evaluation.analytics_reference`` and the copilot tools consume).

REST analytics, hotspots, recurring problems and the AI-5/AI-6 fact sources all read cases through this one function, so a number shown on a dashboard and a number
quoted by the copilot come from the same rows.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import CivicCase, IncidentCase

RESOLVED = {"VERIFIED", "RESOLVED", "REJECTED"}


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def sla_breached(c: CivicCase, now: datetime) -> bool:
    if c.sla_deadline is None:
        return False
    return (c.closed_at or now) > c.sla_deadline if c.status in ("RESOLVED", "REJECTED") or c.closed_at else now > c.sla_deadline


def row(c: CivicCase, now: datetime, incident_id: str | None = None) -> dict:
    return {"id": c.id, "public_case_id": c.case_number, "title": c.title, "canonical_description": c.description, "category": c.category, "subcategory": c.subcategory,
            "severity": c.severity, "priority": c.priority, "priority_score": c.priority_score, "sla_class": c.sla_class, "sla_hours": c.sla_hours, "status": c.status,
            "location": {"latitude": c.latitude, "longitude": c.longitude}, "location_tags": list(c.location_tags or []), "ward_id": c.ward_id, "department_id": c.department_id,
            "created_at": iso(c.created_at), "updated_at": iso(c.updated_at), "closed_at": iso(c.closed_at), "reopen_count": c.reopen_count, "support_count": c.support_count,
            "recurrence_count": c.recurrence_count, "incident_id": incident_id, "language": c.language, "sla_deadline": iso(c.sla_deadline), "sla_breached": sla_breached(c, now)}


def case_rows(db: Session, clause=True, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    q = select(CivicCase)
    if clause is not True:
        q = q.where(clause)
    cases = list(db.execute(q.order_by(CivicCase.created_at)).scalars())
    incident_of = dict(db.execute(select(IncidentCase.case_id, IncidentCase.incident_id)).all())
    return [row(c, now, incident_of.get(c.id)) for c in cases]
