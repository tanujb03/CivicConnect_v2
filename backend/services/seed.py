"""Reference data and the synthetic demo city (design §58) loaded into the database.

* ``seed_reference``: departments (from the taxonomy the AI adapter also uses) and wards (from the demo city). Safe to run repeatedly.
* ``seed_demo_city``: the 560-case synthetic city (users, cases, report signals, work orders, verifications, incidents, relations, timeline). EVERY row is flagged
  ``synthetic``; accounts are demo logins with one shared development password. Never run it against a production database.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.security import get_password_hash
from backend.models import (
    Base, CaseCounter, CaseEvent, CaseRelation, CivicCase, Department, Incident, IncidentCase, ReportSignal, User, Verification, Ward, WorkOrder,
)
from backend.services import taxonomy as tx

DEMO_DIR = Path(__file__).resolve().parents[2] / "ai" / "evaluation" / "datasets" / "demo_city_v1"
ROLE_MAP = {"CITIZEN": "citizen", "WARD_OFFICER": "ward_officer", "DEPARTMENT_OPERATOR": "operator", "DEPARTMENT_MANAGER": "department_manager",
            "FIELD_WORKER": "field_worker", "CITY_ADMINISTRATOR": "city_admin", "OVERLOOKER": "overlooker"}
VERIFICATION_MAP = {"CONFIRMED_FIXED": "YES", "NOT_FIXED": "NO"}
DEMO_DOMAIN = "demo.civicconnect.test"


def _rows(name: str, directory: Path = DEMO_DIR) -> list[dict]:
    p = directory / f"{name}.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def seed_reference(db: Session, directory: Path = DEMO_DIR) -> dict:
    t = tx.taxonomy()
    added = {"departments": 0, "wards": 0}
    for d in t.departments.values():
        if db.get(Department, d.id) is None:
            db.add(Department(id=d.id, code=d.code, name=d.label.get("en", d.id), name_i18n=dict(d.label), category_coverage=list(d.category_ids)))
            added["departments"] += 1
    for w in _rows("wards", directory):
        if db.get(Ward, w["id"]) is None:
            c = w.get("centroid") or {}
            db.add(Ward(id=w["id"], label=w.get("label"), name=w["name"], municipality_id=w.get("municipality_id"), boundary=w.get("boundary"),
                        centroid_lat=c.get("latitude"), centroid_lon=c.get("longitude")))
            added["wards"] += 1
    db.flush()
    return added


def _email_for(u: dict, ward_label: dict[str, str], counters: dict[str, int]) -> str:
    role = ROLE_MAP[u["role"]]
    if role == "citizen":
        counters["citizen"] = counters.get("citizen", 0) + 1
        return f"citizen{counters['citizen']:03d}@{DEMO_DOMAIN}"
    if role == "ward_officer":
        return f"ward{ward_label[u['ward_id']][1:]}@{DEMO_DOMAIN}" if u.get("ward_id") in ward_label else f"ward{counters.setdefault('w', 0) + 1}@{DEMO_DOMAIN}"
    if role in ("operator", "department_manager", "field_worker"):
        prefix = {"operator": "operator", "department_manager": "manager", "field_worker": "worker"}[role]
        return f"{prefix}.{u['department_id']}@{DEMO_DOMAIN}"
    return f"{'admin' if role == 'city_admin' else role}@{DEMO_DOMAIN}"


def seed_demo_city(db: Session, directory: Path = DEMO_DIR, password: str | None = None) -> dict:
    """Idempotent: returns {'skipped': True} when demo cases already exist."""
    if db.execute(select(func.count()).select_from(CivicCase).where(CivicCase.synthetic.is_(True))).scalar_one():
        return {"skipped": True}
    seed_reference(db, directory)
    pw_hash = get_password_hash(password or settings.DEMO_PASSWORD)          # one hash for every demo account (bcrypt is deliberately slow)
    wards = {w["id"]: w for w in _rows("wards", directory)}
    ward_label = {i: w["label"] for i, w in wards.items()}
    counters: dict[str, int] = {}
    accounts: list[dict] = []
    for u in _rows("users", directory):
        email = _email_for(u, ward_label, counters)
        db.add(User(id=u["id"], name=u["name"], email=email, hashed_password=pw_hash, role=ROLE_MAP[u["role"]], department_id=u.get("department_id"),
                    ward_id=u.get("ward_id"), preferred_language=u.get("preferred_language", "en"), synthetic=True))
        if ROLE_MAP[u["role"]] != "citizen" or counters.get("citizen") == 1:
            accounts.append({"email": email, "role": ROLE_MAP[u["role"]]})
    db.add(User(name="Demo System Administrator", email=f"sysadmin@{DEMO_DOMAIN}", hashed_password=pw_hash, role="system_admin", synthetic=True))
    accounts.append({"email": f"sysadmin@{DEMO_DOMAIN}", "role": "system_admin"})
    db.flush()                                                                     # users must exist before wards point at them
    for w in db.execute(select(Ward)).scalars():                                  # ward officers also own their ward
        officer = next((u for u in _rows("users", directory) if u["role"] == "WARD_OFFICER" and u.get("ward_id") == w.id), None)
        if officer:
            w.officer_id = officer["id"]
    db.flush()
    signals = _rows("report_signals", directory)
    reporter_of = {s["case_id"]: s["reporter_id"] for s in signals if s.get("is_primary")}
    cases = _rows("cases", directory)
    for c in cases:
        loc = c["location"]
        db.add(CivicCase(id=c["id"], case_number=c["public_case_id"], title=c["title"], description=c.get("canonical_description"), category=c["category"], subcategory=c.get("subcategory"),
                         severity=c["severity"], priority=c["priority"], priority_score=c["priority_score"], sla_class=c.get("sla_class"), sla_hours=c.get("sla_hours"),
                         sla_deadline=_dt(c.get("sla_deadline")), status=c["status"], latitude=loc["latitude"], longitude=loc["longitude"], location_tags=c.get("location_tags") or [],
                         ward_id=c.get("ward_id"), department_id=c.get("department_id"), reporter_id=reporter_of.get(c["id"]), language=c.get("language"), source="CITIZEN",
                         support_count=c.get("support_count", 0), recurrence_count=c.get("recurrence_count", 0), reopen_count=c.get("reopen_count", 0), synthetic=True,
                         created_at=_dt(c["created_at"]), updated_at=_dt(c["updated_at"]), closed_at=_dt(c.get("closed_at"))))
    db.flush()
    for s in signals:
        db.add(ReportSignal(id=s["id"], case_id=s["case_id"], reporter_id=s["reporter_id"], original_text=s["original_text"], original_language=s.get("original_language"),
                            source_type=s.get("source_type", "SMARTPHONE"), is_primary=bool(s.get("is_primary")), latitude=s.get("latitude"), longitude=s.get("longitude"),
                            created_at=_dt(s["created_at"])))
    for w in _rows("work_orders", directory):
        c = next((x for x in cases if x["id"] == w["case_id"]), None)
        db.add(WorkOrder(id=w["id"], case_id=w["case_id"], department_id=w["department_id"], assigned_worker_id=w.get("assigned_worker_id"), priority=w["priority"],
                         deadline=_dt(w.get("deadline")), status=w["status"], created_at=_dt(w["created_at"]), completed_at=_dt(w.get("completed_at")),
                         started_at=_dt(w["created_at"]) if w["status"] in ("IN_PROGRESS", "COMPLETED") else None, instructions=f"Synthetic work order for {c['public_case_id'] if c else w['case_id']}"))
    for v in _rows("verifications", directory):
        db.add(Verification(id=v["id"], case_id=v["case_id"], citizen_id=v["citizen_id"], result=VERIFICATION_MAP.get(v["result"], "NO"), created_at=_dt(v["created_at"])))
    for r in _rows("case_relations", directory):
        db.add(CaseRelation(id=r["id"], case_a=r["case_a"], case_b=r["case_b"], relation_type=r["relation_type"], similarity_score=r.get("similarity_score"), created_at=_dt(r["created_at"])))
    for inc in _rows("incidents", directory):
        c = inc.get("center") or {}
        db.add(Incident(id=inc["id"], title=inc["title"], description=inc.get("description"), geometry=inc.get("geometry"), center_lat=c.get("latitude"), center_lon=c.get("longitude"),
                        ward_id=inc.get("ward_id"), status="ACTIVE" if inc["status"] == "ACTIVE" else "ENDED", created_by=inc.get("created_by"), started_at=_dt(inc["started_at"]),
                        ended_at=_dt(inc.get("ended_at"))))
    db.flush()
    for c in cases:
        if c.get("incident_id"):
            db.add(IncidentCase(incident_id=c["incident_id"], case_id=c["id"], added_by=None))
    for e in _rows("status_events", directory):
        db.add(CaseEvent(case_id=e["case_id"], event_type="CASE_CREATED" if e.get("from_state") is None else "STATUS_CHANGED", actor_role=e.get("actor_role"),
                         event_metadata={"from": e.get("from_state"), "to": e["to_state"]}, created_at=_dt(e["at"])))
    year_max = max((int(c["public_case_id"].split("-")[-1]) for c in cases), default=0)
    if db.get(CaseCounter, 2026) is None:
        db.add(CaseCounter(year=2026, last=0))                                          # new real cases are CC-2026-000001..., never DEMO-...
    db.commit()
    return {"skipped": False, "cases": len(cases), "accounts": accounts, "password": password or settings.DEMO_PASSWORD, "demo_numbering_max": year_max}


def reset_all(db: Session) -> None:
    """Delete every row (development only)."""
    if settings.ENVIRONMENT.lower() == "prod":
        raise RuntimeError("refusing to wipe a production database")
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
