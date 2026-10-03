"""Deterministic, role-scoped aggregates for §51A.12-§51A.13 (design §38-§40): counts come from the database, never from a model."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.evaluation.analytics_reference import hotspots as _hotspots
from ai.evaluation.analytics_reference import recurring_sites as _recurring
from backend.core.exceptions import CivicConnectException
from backend.core.pagination import clamp_limit, paginate
from backend.core.permissions import CITY_WIDE_ROLES, DEPARTMENT_ROLES, STAFF_ROLES, forbidden
from backend.models import CivicCase, Department, Incident, IncidentCase, User, Ward
from backend.services.cases import visibility_clause
from backend.services.city_rows import case_rows
from backend.services.geo import EARTH_RADIUS_M
import math

OPEN = {"SUBMITTED", "AI_PROCESSING", "NEEDS_REVIEW", "ASSIGNED", "WORK_ORDER_CREATED", "IN_PROGRESS", "RESOLUTION_SUBMITTED", "AWAITING_VERIFICATION", "REOPENED"}
UNASSIGNED = {"SUBMITTED", "AI_PROCESSING", "NEEDS_REVIEW"}
AT_RISK_FRACTION = 0.75
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")                      # display order of the workload charts
PRIORITIES = ("CRITICAL", "URGENT", "HIGH", "NORMAL", "LOW")
HIGH_PRIORITY = ("URGENT", "CRITICAL")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def scope_rows(db: Session, user: User, now: datetime | None = None) -> list[dict]:
    """Rows the user may aggregate: staff their scope; citizens / field workers only their own visible cases ('limited'); overlooker the whole city (aggregates only)."""
    if user.role == "overlooker":
        return case_rows(db, True, now)
    return case_rows(db, visibility_clause(user), now)


def _hours(c: dict) -> float:
    return (_dt(c["closed_at"]) - _dt(c["created_at"])).total_seconds() / 3600.0


def overview(db: Session, user: User, now: datetime | None = None, days: int = 30) -> dict:
    now = now or _now()
    rows = scope_rows(db, user, now)
    open_rows = [c for c in rows if c["status"] in OPEN]
    resolved = [c for c in rows if c["status"] == "RESOLVED" and c.get("closed_at")]

    def at_risk(c: dict) -> bool:
        if not c.get("sla_deadline"):
            return False
        created, deadline = _dt(c["created_at"]), _dt(c["sla_deadline"])
        return now >= created + (deadline - created) * AT_RISK_FRACTION

    trend: dict[str, dict] = {}
    start = (now - timedelta(days=days - 1)).date()
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        trend[d] = {"date": d, "created": 0, "resolved": 0}
    for c in rows:
        d = _dt(c["created_at"]).date().isoformat()
        if d in trend:
            trend[d]["created"] += 1
        if c.get("closed_at") and c["status"] == "RESOLVED":
            d = _dt(c["closed_at"]).date().isoformat()
            if d in trend:
                trend[d]["resolved"] += 1
    cats = Counter(c["category"] or "other" for c in rows)
    return {"open_cases": len(open_rows), "critical_cases": sum(c["priority"] in ("URGENT", "CRITICAL") for c in open_rows), "sla_at_risk": sum(at_risk(c) for c in open_rows),
            "unassigned": sum(c["status"] in UNASSIGNED for c in rows), "awaiting_verification": sum(c["status"] == "AWAITING_VERIFICATION" for c in rows),
            "reopened": sum(c["status"] == "REOPENED" for c in rows), "median_resolution_hours": round(median(_hours(c) for c in resolved), 1) if resolved else 0.0,
            "category_distribution": [{"category": k, "count": v} for k, v in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))],
            "daily_trend": list(trend.values()), "total_cases": len(rows), "scope": scope_label(user),
            "priority_distribution": _distribution(open_rows, "priority", PRIORITIES), "severity_distribution": _distribution(open_rows, "severity", SEVERITIES)}


def _distribution(rows: list[dict], field: str, order: tuple[str, ...]) -> list[dict]:
    """Counts per value of ``field`` in a fixed order, zeros included (charts need every bar)."""
    n = Counter(c[field] for c in rows)
    return [{field: v, "count": n.get(v, 0)} for v in order]


def scope_label(user: User) -> str:
    if user.role in CITY_WIDE_ROLES or user.role == "overlooker":
        return "city"
    if user.role in DEPARTMENT_ROLES:
        return f"department:{user.department_id}"
    if user.role == "ward_officer":
        return f"ward:{user.ward_id}"
    return "own"


def _department_stats(rows: list[dict], now: datetime, days: int = 30) -> dict:
    """The A07 numbers. ``incoming`` = created in the last ``days`` days; ``resolved`` / median / SLA compliance = cases CLOSED in that window (the page says "Resolved (30d)");
    ``active`` / ``backlog_age_days`` / ``by_severity`` = the open workload now; ``recurring_cases`` = recurring problem sites among these cases."""
    since = now - timedelta(days=days)
    resolved = [c for c in rows if c["status"] == "RESOLVED" and c.get("closed_at") and _dt(c["closed_at"]) >= since]
    opened = [c for c in rows if c["status"] in OPEN]
    on_time = [c for c in resolved if not c["sla_breached"]]
    ages = [(now - _dt(c["created_at"])).total_seconds() / 86400.0 for c in opened]
    return {"days": days, "incoming": sum(_dt(c["created_at"]) >= since for c in rows), "active": len(opened), "resolved": len(resolved),
            "median_resolution_hours": round(median(_hours(c) for c in resolved), 1) if resolved else 0.0,
            "sla_compliance_pct": round(100.0 * len(on_time) / len(resolved), 1) if resolved else 0.0, "reopened": sum(c["status"] == "REOPENED" for c in rows),
            "backlog_age_days": round(median(ages), 1) if ages else 0.0, "recurring_cases": len(_recurring(rows)),
            "by_severity": _distribution(opened, "severity", SEVERITIES)}


def department(db: Session, user: User, department_id: str, now: datetime | None = None, days: int = 30) -> dict:
    now = now or _now()
    if user.role not in STAFF_ROLES | {"overlooker"}:
        raise forbidden("Your role may not view department analytics.", capability="view_analytics")
    if user.role in DEPARTMENT_ROLES and user.department_id != department_id:
        raise forbidden("That department is outside your scope.")
    dept = db.get(Department, department_id)
    if dept is None:
        raise CivicConnectException("DEPARTMENT_NOT_FOUND", "The department does not exist.", 404)
    rows = [c for c in scope_rows(db, user, now) if c["department_id"] == department_id]
    return {"department_id": department_id, "name": dept.name, **_department_stats(rows, now, days)}


def departments(db: Session, user: User, now: datetime | None = None, days: int = 30) -> list[dict]:
    now = now or _now()
    rows = scope_rows(db, user, now)
    by: dict[str, list[dict]] = defaultdict(list)
    for c in rows:
        by[c["department_id"] or "unassigned"].append(c)
    names = {d.id: d.name for d in db.execute(select(Department)).scalars()}
    return [{"department_id": k, "name": names.get(k, "Unassigned"), **_department_stats(v, now, days)} for k, v in sorted(by.items())]


def wards(db: Session, user: User, now: datetime | None = None, days: int | None = None) -> list[dict]:
    """A09 ward heatmap numbers (``days`` limits the cases to those created in the last ``days`` days; default all time). ``critical`` = open URGENT/CRITICAL cases,
    ``backlog`` = open cases, ``recurrence`` = recurring problem sites in the ward, ``by_category`` = case counts per category."""
    now = now or _now()
    rows = scope_rows(db, user, now)
    if days:
        since = now - timedelta(days=days)
        rows = [c for c in rows if _dt(c["created_at"]) >= since]
    by: dict[str, list[dict]] = defaultdict(list)
    for c in rows:
        by[c["ward_id"] or "unknown"].append(c)
    ward_rows = list(db.execute(select(Ward)).scalars())
    labels, names = {w.id: (w.label or w.name) for w in ward_rows}, {w.id: w.name for w in ward_rows}
    out = []
    for k, v in sorted(by.items(), key=lambda kv: labels.get(kv[0], "~")):
        opened = [c for c in v if c["status"] in OPEN]
        resolved = [c for c in v if c["status"] == "RESOLVED" and c.get("closed_at")]
        cats = Counter(c["category"] or "other" for c in v)
        out.append({"ward_id": k, "label": labels.get(k, "Unknown"), "name": names.get(k, "Unknown"), "cases": len(v), "open": len(opened),
                    "sla_breached": sum(bool(c["sla_breached"]) for c in v), "reopened": sum(c["status"] == "REOPENED" for c in v),
                    "critical": sum(c["priority"] in HIGH_PRIORITY for c in opened), "backlog": len(opened),
                    "median_resolution_days": round(median(_hours(c) for c in resolved) / 24.0, 1) if resolved else 0.0, "recurrence": len(_recurring(v)),
                    "by_category": [{"category": c, "count": n} for c, n in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))]})
    return out


# ------------------------------------------------------------------------------------------------ trends (SQL group-by)
def _bucket(col, granularity: str, dialect: str):
    """SQL expression giving the UTC bucket label ``YYYY-MM-DD`` of a timestamp column: the day, or the Monday of its ISO week."""
    if dialect == "postgresql":
        utc = func.timezone("UTC", col)
        return func.to_char(func.date_trunc("week", utc) if granularity == "weekly" else utc, "YYYY-MM-DD")
    return func.date(col, "-6 days", "weekday 1") if granularity == "weekly" else func.strftime("%Y-%m-%d", col)      # SQLite (stored as UTC text)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def trends(db: Session, user: User, *, granularity: str = "daily", days: int = 30, category: str | None = None, now: datetime | None = None) -> dict:
    """Daily / weekly (Monday-based, UTC) counts of the cases in the caller's scope, grouped in SQL: ``series`` = cases CREATED in the bucket by category and current
    status (non-empty combinations only); ``totals`` = one zero-filled entry per bucket with cases created, cases resolved (by ``closed_at``) and created cases of
    priority URGENT/CRITICAL. The weekly window starts on the Monday of the first week so every bucket is a whole week."""
    if granularity not in ("daily", "weekly"):
        raise CivicConnectException("VALIDATION_ERROR", "granularity must be daily or weekly.", 422, {"field": "granularity"})
    now = now or _now()
    clause = True if user.role == "overlooker" else visibility_clause(user)
    today = now.date()
    first = today - timedelta(days=days - 1)
    if granularity == "weekly":
        first = _monday(first)
    since = datetime.combine(first, time.min, tzinfo=timezone.utc)
    dialect = db.get_bind().dialect.name
    cat = func.coalesce(CivicCase.category, "other")

    def scoped(q):
        q = q.where(clause) if clause is not True else q
        return q.where(cat == category) if category else q

    created_b, closed_b = _bucket(CivicCase.created_at, granularity, dialect), _bucket(CivicCase.closed_at, granularity, dialect)
    series = db.execute(scoped(select(created_b, cat, CivicCase.status, func.count()).where(CivicCase.created_at >= since)).group_by(created_b, cat, CivicCase.status)
                        .order_by(created_b, cat, CivicCase.status)).all()
    critical = dict(db.execute(scoped(select(created_b, func.count()).where(CivicCase.created_at >= since, CivicCase.priority.in_(HIGH_PRIORITY))).group_by(created_b)).all())
    resolved = dict(db.execute(scoped(select(closed_b, func.count()).where(CivicCase.status == "RESOLVED", CivicCase.closed_at >= since)).group_by(closed_b)).all())
    step = 7 if granularity == "weekly" else 1
    keys = [(first + timedelta(days=i)).isoformat() for i in range(0, (_monday(today) if granularity == "weekly" else today).toordinal() - first.toordinal() + 1, step)]
    created = Counter()
    for bucket, _c, _s, n in series:
        created[bucket] += n
    return {"granularity": granularity, "from": first.isoformat(), "until": today.isoformat(), "scope": scope_label(user),
            "series": [{"bucket": b, "category": c, "status": st, "count": n} for b, c, st, n in series],
            "totals": [{"bucket": k, "created": created.get(k, 0), "resolved": resolved.get(k, 0), "critical": critical.get(k, 0)} for k in keys]}


def incidents_summary(db: Session, user: User, *, cursor: str | None, limit: int | None) -> tuple[list[dict], str | None]:
    if user.role not in STAFF_ROLES | {"overlooker"}:
        raise forbidden("Your role may not view incident analytics.", capability="view_incidents")
    rows, nxt = paginate(db.query(Incident), [(Incident.started_at, True), (Incident.id, True)], cursor, clamp_limit(limit), lambda i: [i.started_at, i.id])
    counts = Counter(r for (r,) in db.execute(select(IncidentCase.incident_id).where(IncidentCase.incident_id.in_([i.id for i in rows]))).all()) if rows else {}
    return [{"id": i.id, "title": i.title, "status": i.status, "created_at": i.started_at, "case_count": counts.get(i.id, 0)} for i in rows], nxt


# ------------------------------------------------------------------------------------------------ geospatial aggregates (§39, §38)
def _circle(lat: float, lon: float, radius_m: float, n: int = 24) -> dict:
    ring = []
    for k in range(n):
        a = 2 * math.pi * k / n
        dlat = math.degrees(radius_m * math.sin(a) / EARTH_RADIUS_M)
        dlon = math.degrees(radius_m * math.cos(a) / (EARTH_RADIUS_M * max(math.cos(math.radians(lat)), 1e-6)))
        ring.append([round(lon + dlon, 6), round(lat + dlat, 6)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def hotspots(db: Session, user: User, now: datetime | None = None) -> list[dict]:
    now = now or _now()
    out = []
    for h in _hotspots(scope_rows(db, user, now), now):
        c = h["center"]
        item = {"id": f"hs-{h['subcategory']}-{h['cell'][0]}-{h['cell'][1]}", "geometry": _circle(c["latitude"], c["longitude"], 350.0 / 2 * 1.2),
                "metrics": {"subcategory": h["subcategory"], "recent_cases": h["recent_cases"], "baseline_cases": h["baseline_cases"], "ratio_vs_baseline": h["ratio_vs_baseline"],
                            "center": c}}
        if user.role in STAFF_ROLES:
            item["case_ids"] = h["case_ids"]
        out.append(item)
    return out


def recurring_problems(db: Session, user: User, now: datetime | None = None) -> list[dict]:
    import uuid
    now = now or _now()
    out = []
    for s in _recurring(scope_rows(db, user, now)):
        item = {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "civicconnect/recurring/" + ",".join(sorted(s["case_ids"])))), "category": s["subcategory"], "recurrence_count": s["n_cases"],
                "location": s["center"], "time_window": {"from": s["first_at"], "until": s["last_at"]}, "resolved": s["n_resolved"], "reopened": s["n_reopened"]}
        if user.role in STAFF_ROLES:
            item["case_ids"] = s["case_ids"]
        out.append(item)
    return out
