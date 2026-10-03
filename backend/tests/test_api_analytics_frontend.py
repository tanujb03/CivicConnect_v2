"""Analytics the admin and overlooker apps chart: /analytics/trends (SQL group-by), department performance (A07), ward heatmap (A09), overview distributions.
Cases are inserted directly with exact timestamps so every number can be checked by hand."""
import random
import uuid
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import event

from backend.models import CivicCase, Ward

TRENDS = "/api/v1/analytics/trends"
UTC = timezone.utc


def at(d: date, hour: int = 12) -> datetime:
    return datetime.combine(d, time(hour), tzinfo=UTC)


def mk(e, created: datetime, *, status="SUBMITTED", category="roads", subcategory="pothole", priority="NORMAL", severity="MEDIUM", department_id="road_maintenance",
       ward_id=None, closed: datetime | None = None, sla_hours: int | None = 48, lat=None, lon=None) -> str:
    with e.session_factory() as db:
        c = CivicCase(case_number="T-" + uuid.uuid4().hex[:20].upper(), category=category, subcategory=subcategory, priority=priority, severity=severity, status=status,
                      latitude=lat if lat is not None else e.where["latitude"], longitude=lon if lon is not None else e.where["longitude"], ward_id=ward_id or e.ward_id,
                      department_id=department_id, created_at=created, closed_at=closed, sla_hours=sla_hours,
                      sla_deadline=created + timedelta(hours=sla_hours) if sla_hours else None, reporter_id=e.users["alice"]["id"])
        db.add(c)
        db.commit()
        return c.id


def get(e, who, url):
    r = e.client.get(url, headers=e.headers(who))
    assert r.status_code == 200, (who, url, r.text)
    return r.json()


# ------------------------------------------------------------------------------------------------ trends
def seed_week(e):
    today = datetime.now(UTC).date()
    mk(e, at(today), category="roads", status="SUBMITTED")
    mk(e, at(today), category="roads", status="SUBMITTED", priority="URGENT")
    mk(e, at(today - timedelta(days=1)), category="roads", status="RESOLVED", closed=at(today))                          # created yesterday, resolved today
    mk(e, at(today - timedelta(days=1)), category="water_supply", department_id="water_supply", status="IN_PROGRESS", priority="CRITICAL")
    mk(e, at(today - timedelta(days=40)), category="roads", status="SUBMITTED")                                          # outside the 30-day window
    return today


def test_daily_trends_group_by_category_and_status_and_zero_fill_the_totals(staffed):
    e = staffed
    today = seed_week(e)
    t = get(e, "admin", TRENDS)
    assert (t["granularity"], t["from"], t["until"], t["scope"]) == ("daily", (today - timedelta(days=29)).isoformat(), today.isoformat(), "city")
    assert len(t["totals"]) == 30 and [x["bucket"] for x in t["totals"]][0] == t["from"] and t["totals"][-1]["bucket"] == today.isoformat()
    key = lambda r: (r["bucket"], r["category"], r["status"])           # noqa: E731
    yesterday = (today - timedelta(days=1)).isoformat()
    assert sorted(t["series"], key=key) == sorted([
        {"bucket": today.isoformat(), "category": "roads", "status": "SUBMITTED", "count": 2},
        {"bucket": yesterday, "category": "roads", "status": "RESOLVED", "count": 1},
        {"bucket": yesterday, "category": "water_supply", "status": "IN_PROGRESS", "count": 1}], key=key)                # the 40-day-old case is outside the window
    totals = {x["bucket"]: x for x in t["totals"]}
    assert totals[today.isoformat()] == {"bucket": today.isoformat(), "created": 2, "resolved": 1, "critical": 1}          # resolved is counted on the day it was closed
    assert totals[yesterday] == {"bucket": yesterday, "created": 2, "resolved": 0, "critical": 1}                          # a CRITICAL priority case is critical too
    assert sum(x["created"] for x in t["totals"]) == 4 and sum(x["resolved"] for x in t["totals"]) == 1
    assert all(x == {"bucket": x["bucket"], "created": 0, "resolved": 0, "critical": 0} for b, x in totals.items() if b not in (today.isoformat(), yesterday))
    wide = get(e, "admin", TRENDS + "?days=60")
    assert len(wide["totals"]) == 60 and sum(x["created"] for x in wide["totals"]) == 5                                   # now the old case is inside
    only = get(e, "admin", TRENDS + "?category=water_supply")
    assert [r["category"] for r in only["series"]] == ["water_supply"] and sum(x["created"] for x in only["totals"]) == 1


def test_weekly_trends_use_whole_monday_based_weeks(staffed):
    e = staffed
    today = seed_week(e)
    t = get(e, "admin", TRENDS + "?granularity=weekly&days=30")
    buckets = [x["bucket"] for x in t["totals"]]
    monday = lambda d: d - timedelta(days=d.weekday())      # noqa: E731
    assert t["granularity"] == "weekly" and t["from"] == monday(today - timedelta(days=29)).isoformat() and buckets[-1] == monday(today).isoformat()
    assert all(date.fromisoformat(b).weekday() == 0 for b in buckets) and all(date.fromisoformat(b) - date.fromisoformat(a) == timedelta(days=7) for a, b in zip(buckets, buckets[1:]))
    totals = {x["bucket"]: x for x in t["totals"]}
    assert sum(x["created"] for x in t["totals"]) == 4 and sum(x["resolved"] for x in t["totals"]) == 1 and sum(x["critical"] for x in t["totals"]) == 2
    this_week = monday(today).isoformat()
    last_day = today - timedelta(days=1)
    assert totals[this_week]["created"] == 2 + (1 if last_day.weekday() != 6 else 0) * 2                              # yesterday is in this week unless it was Sunday
    assert {(r["bucket"], r["category"]) for r in t["series"]} <= {(b, c) for b in buckets for c in ("roads", "water_supply")}


def test_trends_validation_and_roles(staffed):
    e = staffed
    for bad in ("?granularity=hourly", "?days=6", "?days=366", "?days=abc"):
        assert e.client.get(TRENDS + bad, headers=e.headers("admin")).status_code == 422, bad
    assert e.client.get(TRENDS).status_code == 401
    for who in ("alice", "roads_worker"):
        assert e.client.get(TRENDS, headers=e.headers(who)).status_code == 403, who                                       # no view_analytics
    for who in ("roads_op", "roads_mgr", "ward_officer", "admin", "overlooker"):
        assert e.client.get(TRENDS, headers=e.headers(who)).status_code == 200, who


def test_trends_are_scoped_to_the_callers_role(staffed):
    e = staffed
    today = datetime.now(UTC).date()
    other_ward = None
    with e.session_factory() as db:
        other_ward = db.query(Ward).filter(Ward.id != e.ward_id).first().id
    mk(e, at(today), department_id="road_maintenance", ward_id=e.ward_id)
    mk(e, at(today), department_id="road_maintenance", ward_id=other_ward)
    mk(e, at(today), category="water_supply", department_id="water_supply", ward_id=e.ward_id)
    mk(e, at(today), department_id=None, ward_id=other_ward)                                                          # not routed yet: every department operator sees it

    def created(who):
        t = get(e, who, TRENDS)
        return t["scope"], sum(x["created"] for x in t["totals"])
    assert created("admin") == ("city", 4) and created("overlooker") == ("city", 4)                                     # city aggregates
    assert created("roads_op") == ("department:road_maintenance", 3) and created("roads_mgr") == ("department:road_maintenance", 3)
    assert created("water_op") == ("department:water_supply", 2)
    assert created("ward_officer") == (f"ward:{e.ward_id}", 2)


def test_trends_equal_an_independent_python_computation_and_use_group_by(staffed):
    e = staffed
    rnd, today = random.Random(7), datetime.now(UTC).date()
    cats, statuses = ["roads", "water_supply", "solid_waste"], ["SUBMITTED", "IN_PROGRESS", "RESOLVED", "REOPENED"]
    rows = []
    for _ in range(60):
        created_day = today - timedelta(days=rnd.randint(0, 34))
        status, cat = rnd.choice(statuses), rnd.choice(cats)
        closed = at(min(today, created_day + timedelta(days=rnd.randint(0, 3)))) if status == "RESOLVED" else None
        prio = rnd.choice(["LOW", "NORMAL", "HIGH", "URGENT", "CRITICAL"])
        mk(e, at(created_day), status=status, category=cat, closed=closed, priority=prio, department_id=None)
        rows.append((created_day, cat, status, closed, prio))
    statements = []

    def spy(conn, cursor, statement, *a):
        statements.append(statement)
    from backend.db import session as dbs
    event.listen(dbs.engine, "before_cursor_execute", spy)
    try:
        t = get(e, "admin", TRENDS + "?days=30")
    finally:
        event.remove(dbs.engine, "before_cursor_execute", spy)
    first = today - timedelta(days=29)
    inside = [r for r in rows if r[0] >= first]
    assert Counter((x["bucket"], x["category"], x["status"]) for x in t["series"] for _ in range(x["count"])) == Counter((r[0].isoformat(), r[1], r[2]) for r in inside)
    totals = {x["bucket"]: x for x in t["totals"]}
    for d in (first + timedelta(days=i) for i in range(30)):
        k = d.isoformat()
        assert totals[k]["created"] == sum(r[0] == d for r in inside) and totals[k]["critical"] == sum(r[0] == d and r[4] in ("URGENT", "CRITICAL") for r in inside), k
        assert totals[k]["resolved"] == sum(r[2] == "RESOLVED" and r[3].date() == d for r in rows if r[3] and r[3].date() >= first), k
    aggregates = [s for s in statements if "GROUP BY" in s.upper() and "civic_cases" in s]
    assert len(aggregates) == 3, statements                                                                           # created+status, critical, resolved: all grouped in SQL
    assert not [s for s in statements if "civic_cases" in s and "GROUP BY" not in s.upper()]                          # no case rows were loaded into Python


# ------------------------------------------------------------------------------------------------ department performance (A07)
def seed_roads(e):
    now = datetime.now(UTC)
    for hours in (10, 20, 30, 40):                                                                        # four resolved last week; SLA 24 h: two on time, two late
        done = now - timedelta(days=3)
        mk(e, done - timedelta(hours=hours), status="RESOLVED", closed=done, sla_hours=24, severity="LOW", subcategory="pothole")
    mk(e, now - timedelta(days=60), status="RESOLVED", closed=now - timedelta(days=50), sla_hours=24)      # resolved long ago: outside the 30-day window
    mk(e, now - timedelta(days=2), status="IN_PROGRESS", severity="HIGH")
    mk(e, now - timedelta(days=4), status="ASSIGNED", severity="HIGH")
    mk(e, now - timedelta(days=6), status="SUBMITTED", severity="CRITICAL")
    mk(e, now - timedelta(days=8), status="REOPENED", severity="LOW")
    return now


def test_department_performance_has_everything_the_a07_page_shows(staffed):
    e = staffed
    seed_roads(e)
    mk(e, datetime.now(UTC) - timedelta(days=1), department_id="water_supply", category="water_supply", subcategory="no_water_supply", status="SUBMITTED", severity="CRITICAL")
    d = get(e, "admin", "/api/v1/analytics/departments/road_maintenance")
    assert set(d) == {"department_id", "name", "days", "incoming", "active", "resolved", "median_resolution_hours", "sla_compliance_pct", "reopened", "backlog_age_days",
                      "recurring_cases", "by_severity"}
    names = {x["id"]: x["name"] for x in get(e, "admin", "/api/v1/reference/departments")["items"]}
    assert (d["department_id"], d["days"], d["name"]) == ("road_maintenance", 30, names["road_maintenance"])                  # the same name the reference data shows
    assert d["incoming"] == 8 and d["resolved"] == 4                                                       # created in the last 30 d; closed in the last 30 d (not the one 50 d ago)
    assert d["median_resolution_hours"] == 25.0 and d["sla_compliance_pct"] == 50.0                       # 10, 20, 30, 40 h against a 24 h SLA
    assert d["active"] == 4 and d["reopened"] == 1 and d["backlog_age_days"] == 5.0                       # open: 2, 4, 6 and 8 days old -> median 5
    assert d["by_severity"] == [{"severity": "CRITICAL", "count": 1}, {"severity": "HIGH", "count": 2}, {"severity": "MEDIUM", "count": 0}, {"severity": "LOW", "count": 1}]
    assert d["recurring_cases"] == 1                                                                       # nine potholes within 150 m: one recurring site
    w = get(e, "admin", "/api/v1/analytics/departments/water_supply")
    assert (w["active"], w["incoming"], w["resolved"], w["recurring_cases"], w["sla_compliance_pct"]) == (1, 1, 0, 0, 0.0)
    assert [x["severity"] for x in w["by_severity"]] == ["CRITICAL", "HIGH", "MEDIUM", "LOW"] and w["by_severity"][0]["count"] == 1
    items = {i["department_id"]: i for i in get(e, "admin", "/api/v1/analytics/departments")["items"]}
    assert items["road_maintenance"] == d and items["water_supply"] == w                                  # the list carries the same object per department


def test_department_window_is_adjustable(staffed):
    e = staffed
    seed_roads(e)
    week = get(e, "admin", "/api/v1/analytics/departments/road_maintenance?days=7")
    assert week["days"] == 7 and week["incoming"] == 7 and week["resolved"] == 4                           # created in the last 7 d: the 4 resolved ones + the 2, 4 and 6 day old open ones
    long = get(e, "admin", "/api/v1/analytics/departments/road_maintenance?days=90")
    assert long["resolved"] == 5 and long["incoming"] == 9
    for bad in ("days=6", "days=366"):
        assert e.client.get(f"/api/v1/analytics/departments/road_maintenance?{bad}", headers=e.headers("admin")).status_code == 422


def test_department_analytics_roles_and_scope(staffed):
    e = staffed
    seed_roads(e)
    url = "/api/v1/analytics/departments"
    for who in ("alice", "roads_worker"):
        assert e.client.get(f"{url}/road_maintenance", headers=e.headers(who)).status_code == 403 and e.client.get(url, headers=e.headers(who)).status_code == 403
    for who in ("admin", "overlooker", "roads_op", "roads_mgr"):
        assert e.client.get(f"{url}/road_maintenance", headers=e.headers(who)).status_code == 200, who
    assert e.client.get(f"{url}/road_maintenance", headers=e.headers("water_op")).status_code == 403                  # another department
    assert e.client.get(f"{url}/water_supply", headers=e.headers("water_op")).status_code == 200
    assert e.client.get(f"{url}/nope", headers=e.headers("admin")).status_code == 404
    assert [i["department_id"] for i in get(e, "roads_op", url)["items"]] == ["road_maintenance"]                      # the list is scoped too
    assert get(e, "ward_officer", f"{url}/road_maintenance")["active"] == 4                                           # ward officers see their ward's cases of any department


# ------------------------------------------------------------------------------------------------ ward heatmap (A09)
def test_ward_metrics_for_the_heatmap(staffed):
    e = staffed
    now = datetime.now(UTC)
    with e.session_factory() as db:
        other = db.query(Ward).filter(Ward.id != e.ward_id).order_by(Ward.label).first()
        other_id, other_name = other.id, other.name
        mine = db.get(Ward, e.ward_id)
        my_name, my_label = mine.name, mine.label
    mk(e, now - timedelta(days=5), status="SUBMITTED", priority="URGENT", category="roads")
    mk(e, now - timedelta(days=4), status="IN_PROGRESS", priority="CRITICAL", category="roads")
    mk(e, now - timedelta(days=2), status="SUBMITTED", category="roads")
    mk(e, now - timedelta(days=3), status="IN_PROGRESS", priority="NORMAL", category="water_supply", subcategory="no_water_supply", department_id="water_supply")
    mk(e, now - timedelta(days=10), status="RESOLVED", closed=now - timedelta(days=8), priority="URGENT", category="roads")                   # 48 h to resolve, closed: not "critical"
    mk(e, now - timedelta(days=100), status="RESOLVED", closed=now - timedelta(days=97), category="solid_waste", subcategory="missed_collection", department_id="solid_waste")
    mk(e, now - timedelta(days=1), status="SUBMITTED", category="roads", ward_id=other_id)
    items = {w["ward_id"]: w for w in get(e, "admin", "/api/v1/analytics/wards")["items"]}
    w = items[e.ward_id]
    assert {"ward_id", "label", "name", "cases", "open", "sla_breached", "reopened", "critical", "backlog", "median_resolution_days", "recurrence", "by_category"} == set(w)
    assert (w["label"], w["name"]) == (my_label, my_name) and items[other_id]["name"] == other_name
    assert (w["cases"], w["open"], w["backlog"], w["critical"]) == (6, 4, 4, 2)                          # two open URGENT/CRITICAL cases; the resolved URGENT one is closed
    assert w["median_resolution_days"] == 2.5                                                           # 48 h and 72 h
    assert w["by_category"] == [{"category": "roads", "count": 4}, {"category": "solid_waste", "count": 1}, {"category": "water_supply", "count": 1}]
    assert w["recurrence"] == 1 and items[other_id]["recurrence"] == 0                                  # four roads potholes within 150 m in one ward
    assert (items[other_id]["cases"], items[other_id]["critical"], items[other_id]["median_resolution_days"]) == (1, 0, 0.0)
    recent = {x["ward_id"]: x for x in get(e, "admin", "/api/v1/analytics/wards?days=30")["items"]}
    assert recent[e.ward_id]["cases"] == 5 and recent[e.ward_id]["by_category"][0] == {"category": "roads", "count": 4}   # the 100-day-old case is outside
    assert e.client.get("/api/v1/analytics/wards?days=0", headers=e.headers("admin")).status_code == 422


def test_ward_analytics_roles_and_scope(staffed):
    e = staffed
    now = datetime.now(UTC)
    with e.session_factory() as db:
        other_id = db.query(Ward).filter(Ward.id != e.ward_id).first().id
    mk(e, now, ward_id=e.ward_id)
    mk(e, now, ward_id=other_id)
    url = "/api/v1/analytics/wards"
    assert e.client.get(url).status_code == 401 and e.client.get(url, headers=e.headers("alice")).status_code == 403
    assert {w["ward_id"] for w in get(e, "admin", url)["items"]} == {e.ward_id, other_id} == {w["ward_id"] for w in get(e, "overlooker", url)["items"]}
    assert [w["ward_id"] for w in get(e, "ward_officer", url)["items"]] == [e.ward_id]                                              # a ward officer sees their own ward only


# ------------------------------------------------------------------------------------------------ overview distributions
def test_overview_has_priority_and_severity_distributions_of_the_open_workload(staffed):
    e = staffed
    now = datetime.now(UTC)
    mk(e, now, priority="URGENT", severity="HIGH", status="SUBMITTED")
    mk(e, now, priority="URGENT", severity="CRITICAL", status="IN_PROGRESS")
    mk(e, now, priority="LOW", severity="LOW", status="SUBMITTED")
    mk(e, now, priority="HIGH", severity="HIGH", status="RESOLVED", closed=now)                                                # closed: not part of the open workload
    ov = get(e, "admin", "/api/v1/analytics/overview")
    assert ov["priority_distribution"] == [{"priority": "CRITICAL", "count": 0}, {"priority": "URGENT", "count": 2}, {"priority": "HIGH", "count": 0},
                                           {"priority": "NORMAL", "count": 0}, {"priority": "LOW", "count": 1}]
    assert ov["severity_distribution"] == [{"severity": "CRITICAL", "count": 1}, {"severity": "HIGH", "count": 1}, {"severity": "MEDIUM", "count": 0}, {"severity": "LOW", "count": 1}]
    assert [x["priority"] for x in get(e, "overlooker", "/api/v1/analytics/overview")["priority_distribution"]] == ["CRITICAL", "URGENT", "HIGH", "NORMAL", "LOW"]
