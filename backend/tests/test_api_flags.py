"""WP4 community flags: permissions, duplicates, the review threshold, notification fan-out, resolving, map hiding and the audit trail (SQLite)."""
from __future__ import annotations

import uuid

import pytest

from backend.tests.helpers import create_case

API = "/api/v1"


@pytest.fixture
def fl(staffed):
    """``staffed`` with the flags router mounted (the parent registers it in api/v1/router.py; until then the test mounts it and removes it again)."""
    from backend.api.v1 import flags
    from backend.core.config import settings
    from backend.main import app
    before = list(app.router.routes)
    mounted = any(getattr(r, "path", "").endswith("/flags/{flag_id}/resolve") for r in before)
    if not mounted:
        app.include_router(flags.router, prefix=settings.API_V1_STR, tags=["flags"])
    e = staffed
    e.make_user("citizen", "carol")
    e.make_user("citizen", "dave")
    with e.session_factory() as db:
        from backend.models import Ward
        e.other_ward_id = db.query(Ward).filter(Ward.id != e.ward_id).first().id
    e.make_user("ward_officer", "other_officer", ward_id=e.other_ward_id)
    yield e
    if not mounted:
        app.router.routes[:] = before
        app.openapi_schema = None


def flag(e, who, case_id, kind="STILL_EXISTS", comment=None, key=None):
    body = {"kind": kind, **({"comment": comment} if comment else {})}
    return e.client.post(f"{API}/cases/{case_id}/flags", headers=e.idem(who, key), json=body)


def support(e, who, case_id):
    assert e.client.post(f"{API}/cases/{case_id}/support", headers=e.idem(who)).status_code == 200


def set_threshold(e, value):
    from backend.models import SystemSetting
    with e.session_factory() as db:
        db.add(SystemSetting(key="flag_review_threshold", value_json=value))
        db.commit()


def timeline_types(e, who, case_id):
    r = e.client.get(f"{API}/cases/{case_id}/timeline", headers=e.headers(who))
    assert r.status_code == 200, r.text
    return [i["event_type"] for i in r.json()["items"]]


def notified(e, type_="CASE_FLAG_REVIEW"):
    from backend.models import Notification, User
    with e.session_factory() as db:
        rows = db.query(Notification, User.email).join(User, User.id == Notification.user_id).filter(Notification.type == type_).all()
        return sorted(((email.split("@")[0], n.payload) for n, email in rows), key=lambda t: (t[0], t[1].get("case_id", "")))


def audit_actions(e, entity_id):
    from backend.models import AuditEvent
    with e.session_factory() as db:
        return [a.action for a in db.query(AuditEvent).filter(AuditEvent.entity_id == entity_id).order_by(AuditEvent.created_at)]


# ------------------------------------------------------------------------------------------------ creating
def test_who_may_flag_a_case(fl):
    e = fl
    c = create_case(e, "alice")
    r = flag(e, "alice", c["id"], "OUTDATED", "fixed last week")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "OUTDATED" and body["status"] == "OPEN" and body["case_id"] == c["id"] and body["comment"] == "fixed last week"
    assert "user_id" not in body and "resolved_by" not in body                                  # a flag never identifies its author
    assert flag(e, "bob", c["id"]).status_code == 404                                           # a citizen who cannot see the case cannot flag it
    support(e, "bob", c["id"])
    assert flag(e, "bob", c["id"]).status_code == 201                                           # once they back it they can see it
    assert flag(e, "overlooker", c["id"]).status_code == 404                                    # aggregates only
    assert flag(e, "roads_worker", c["id"]).status_code == 404                                  # no work order on it
    assert flag(e, "roads_op", c["id"]).status_code == 201                                      # staff with access to the case may flag too
    assert flag(e, "water_op", c["id"]).status_code == 404                                      # other department
    assert flag(e, "other_officer", c["id"]).status_code == 404                                 # other ward
    assert flag(e, "ward_officer", c["id"]).status_code == 201 and flag(e, "admin", c["id"]).status_code == 201
    assert flag(e, "alice", str(uuid.uuid4())).status_code == 404


def test_flag_request_validation_and_authentication(fl):
    e = fl
    c = create_case(e, "alice")
    assert e.client.post(f"{API}/cases/{c['id']}/flags", json={"kind": "OUTDATED"}).status_code == 401
    assert e.client.post(f"{API}/cases/{c['id']}/flags", headers=e.headers("alice"), json={"kind": "OUTDATED"}).json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert flag(e, "alice", c["id"], "SPAM").status_code == 422
    assert flag(e, "alice", c["id"], "OUTDATED", "x" * 1001).status_code == 422
    assert e.client.get(f"{API}/cases/{c['id']}/flags").status_code == 401
    assert e.client.post(f"{API}/flags/{uuid.uuid4()}/resolve", json={"status": "UPHELD"}).status_code == 401


def test_a_reporter_cannot_flag_their_own_case_inappropriate(fl):
    e = fl
    c = create_case(e, "alice")
    r = flag(e, "alice", c["id"], "INAPPROPRIATE")
    assert r.status_code == 403 and r.json()["error"]["code"] == "FLAG_NOT_ALLOWED"
    assert flag(e, "alice", c["id"], "INCORRECT").status_code == 201                            # the other kinds are fine
    support(e, "bob", c["id"])
    assert flag(e, "bob", c["id"], "INAPPROPRIATE").status_code == 201


def test_one_flag_per_user_per_kind_and_idempotent_replay(fl):
    e = fl
    c = create_case(e, "alice")
    support(e, "bob", c["id"])
    assert flag(e, "alice", c["id"], "OUTDATED").status_code == 201
    dup = flag(e, "alice", c["id"], "OUTDATED")
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "FLAG_ALREADY_EXISTS"
    assert flag(e, "alice", c["id"], "INCORRECT").status_code == 201                            # another kind
    assert flag(e, "bob", c["id"], "OUTDATED").status_code == 201                               # another user
    first = flag(e, "bob", c["id"], "STILL_EXISTS", key="k-1")
    again = flag(e, "bob", c["id"], "STILL_EXISTS", key="k-1")
    assert first.status_code == again.status_code == 201 and again.headers["Idempotent-Replayed"] == "true" and again.json() == first.json()
    assert e.client.get(f"{API}/cases/{c['id']}/flags", headers=e.headers("roads_op")).json()["counts"]["by_status"]["OPEN"] == 4


# ------------------------------------------------------------------------------------------------ threshold, fan-out
def test_threshold_crossing_notifies_once_and_marks_the_case(fl):
    e = fl
    c = create_case(e, "alice")
    support(e, "bob", c["id"])
    flag(e, "alice", c["id"], "OUTDATED")
    flag(e, "bob", c["id"], "OUTDATED")
    assert "FLAG_REVIEW_REQUESTED" not in timeline_types(e, "roads_op", c["id"]) and notified(e) == []
    detail = e.client.get(f"{API}/cases/{c['id']}", headers=e.headers("roads_op")).json()
    assert detail["open_flag_count"] == 2 and detail["needs_flag_review"] is False
    assert flag(e, "roads_op", c["id"], "INCORRECT").status_code == 201                         # third open flag reaches the default threshold of 3
    assert timeline_types(e, "roads_op", c["id"]).count("FLAG_REVIEW_REQUESTED") == 1
    got = notified(e)
    assert [who for who, _ in got] == ["roads_mgr", "ward_officer"]                             # the flagging operator is not told about their own flag
    payload = got[0][1]
    assert payload["case_id"] == c["id"] and payload["case_number"] == c["case_number"] and payload["title"] and payload["message"]
    assert flag(e, "ward_officer", c["id"], "STILL_EXISTS").status_code == 201                  # later flags do not alert again
    assert timeline_types(e, "roads_op", c["id"]).count("FLAG_REVIEW_REQUESTED") == 1 and len(notified(e)) == 2
    assert "FLAG_REVIEW_REQUESTED" not in timeline_types(e, "alice", c["id"])                   # internal event: the reporter does not see it
    detail = e.client.get(f"{API}/cases/{c['id']}", headers=e.headers("roads_op")).json()
    assert detail["open_flag_count"] == 4 and detail["needs_flag_review"] is True
    own = e.client.get(f"{API}/cases/{c['id']}", headers=e.headers("alice")).json()
    assert own["open_flag_count"] == 0 and own["needs_flag_review"] is False                    # citizens never learn the flag count


def test_fan_out_reaches_department_operators_managers_and_the_ward_officer_only(fl):
    e = fl
    set_threshold(e, 1)
    c = create_case(e, "alice")
    assert flag(e, "alice", c["id"], "INCORRECT").status_code == 201
    assert sorted(who for who, _ in notified(e)) == ["roads_mgr", "roads_op", "ward_officer"]   # not water_op, other_officer, admin, bob or the reporter


def test_the_flag_review_threshold_setting_is_honoured(fl):
    e = fl
    set_threshold(e, 2)
    c = create_case(e, "alice")
    flag(e, "alice", c["id"], "OUTDATED")
    assert notified(e) == []
    flag(e, "alice", c["id"], "INCORRECT")
    assert len(notified(e)) == 3 and timeline_types(e, "admin", c["id"]).count("FLAG_REVIEW_REQUESTED") == 1


# ------------------------------------------------------------------------------------------------ list
def test_listing_flags_is_staff_only_and_scoped(fl):
    e = fl
    c = create_case(e, "alice")
    support(e, "bob", c["id"])
    flag(e, "alice", c["id"], "OUTDATED")
    flag(e, "bob", c["id"], "INAPPROPRIATE")
    url = f"{API}/cases/{c['id']}/flags"
    for who in ("roads_op", "roads_mgr", "ward_officer", "admin"):
        r = e.client.get(url, headers=e.headers(who))
        assert r.status_code == 200, (who, r.text)
        body = r.json()
        assert len(body["items"]) == 2 and all("user_id" not in i for i in body["items"])
        assert body["counts"]["by_kind"] == {"STILL_EXISTS": 0, "OUTDATED": 1, "INCORRECT": 0, "INAPPROPRIATE": 1}
        assert body["counts"]["by_status"] == {"OPEN": 2, "UPHELD": 0, "DISMISSED": 0}
    for who in ("alice", "bob", "roads_worker", "overlooker"):
        assert e.client.get(url, headers=e.headers(who)).status_code == 403, who
    assert e.client.get(url, headers=e.headers("water_op")).status_code == 404                  # other department
    assert e.client.get(url, headers=e.headers("other_officer")).status_code == 404             # other ward
    assert e.client.get(f"{API}/cases/{uuid.uuid4()}/flags", headers=e.headers("admin")).status_code == 404
    empty = e.client.get(f"{API}/cases/{create_case(e, 'bob')['id']}/flags", headers=e.headers("admin")).json()
    assert empty["items"] == [] and empty["counts"]["by_kind"]["INCORRECT"] == 0 and empty["counts"]["by_status"]["OPEN"] == 0


# ------------------------------------------------------------------------------------------------ resolve
def test_resolve_flow_audit_timeline_and_review_clears(fl):
    e = fl
    set_threshold(e, 2)
    c = create_case(e, "alice")
    support(e, "bob", c["id"])
    f1 = flag(e, "alice", c["id"], "OUTDATED").json()
    f2 = flag(e, "bob", c["id"], "OUTDATED").json()
    assert e.client.get(f"{API}/cases/{c['id']}", headers=e.headers("roads_op")).json()["needs_flag_review"] is True
    r = e.client.post(f"{API}/flags/{f1['id']}/resolve", headers=e.idem("roads_op"), json={"status": "UPHELD"})
    assert r.status_code == 200 and r.json()["status"] == "UPHELD" and r.json()["resolved_at"]
    assert "user_id" not in r.json()
    detail = e.client.get(f"{API}/cases/{c['id']}", headers=e.headers("roads_op")).json()
    assert detail["open_flag_count"] == 1 and detail["needs_flag_review"] is False              # below the threshold again
    again = e.client.post(f"{API}/flags/{f1['id']}/resolve", headers=e.idem("roads_op"), json={"status": "DISMISSED"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "FLAG_ALREADY_RESOLVED"
    r2 = e.client.post(f"{API}/flags/{f2['id']}/resolve", headers=e.idem("ward_officer"), json={"status": "DISMISSED"})
    assert r2.status_code == 200 and r2.json()["status"] == "DISMISSED"
    assert audit_actions(e, f1["id"]) == ["case_flag.created", "case_flag.resolved"]
    from backend.models import AuditEvent
    with e.session_factory() as db:
        a = db.query(AuditEvent).filter(AuditEvent.entity_id == f1["id"], AuditEvent.action == "case_flag.resolved").one()
        assert a.actor_id == e.users["roads_op"]["id"] and a.before_json == {"status": "OPEN"} and a.after_json["status"] == "UPHELD"
    staff_tl = timeline_types(e, "roads_op", c["id"])
    assert staff_tl.count("FLAG_RESOLVED") == 2 and "FLAG_RESOLVED" not in timeline_types(e, "alice", c["id"])
    counts = e.client.get(f"{API}/cases/{c['id']}/flags", headers=e.headers("admin")).json()["counts"]["by_status"]
    assert counts == {"OPEN": 0, "UPHELD": 1, "DISMISSED": 1}


def test_resolve_permissions_and_errors(fl):
    e = fl
    c = create_case(e, "alice")
    f = flag(e, "alice", c["id"], "INCORRECT").json()
    url = f"{API}/flags/{f['id']}/resolve"
    for who in ("alice", "bob", "roads_worker", "overlooker"):
        assert e.client.post(url, headers=e.idem(who), json={"status": "UPHELD"}).status_code == 403, who
    assert e.client.post(url, headers=e.idem("water_op"), json={"status": "UPHELD"}).status_code == 404            # other department
    assert e.client.post(url, headers=e.idem("other_officer"), json={"status": "UPHELD"}).status_code == 404       # other ward
    assert e.client.post(f"{API}/flags/{uuid.uuid4()}/resolve", headers=e.idem("admin"), json={"status": "UPHELD"}).json()["error"]["code"] == "FLAG_NOT_FOUND"
    assert e.client.post(url, headers=e.idem("roads_op"), json={"status": "OPEN"}).status_code == 422
    assert e.client.post(url, headers=e.headers("roads_op"), json={"status": "UPHELD"}).json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    key = str(uuid.uuid4())
    first = e.client.post(url, headers=e.idem("admin", key), json={"status": "DISMISSED"})
    replay = e.client.post(url, headers=e.idem("admin", key), json={"status": "DISMISSED"})
    assert first.status_code == replay.status_code == 200 and replay.headers["Idempotent-Replayed"] == "true" and replay.json() == first.json()
    assert audit_actions(e, f["id"]).count("case_flag.resolved") == 1


# ------------------------------------------------------------------------------------------------ map hiding, case lists
def _map_ids(e, who, c):
    lat, lon = e.where["latitude"], e.where["longitude"]
    bbox = f"{lon - 0.01},{lat - 0.01},{lon + 0.01},{lat + 0.01}"
    r = e.client.get(f"{API}/map/cases?bbox={bbox}", headers=e.headers(who))
    assert r.status_code == 200, r.text
    return [m["id"] for m in r.json()["items"]]


def test_inappropriate_flags_at_the_threshold_hide_the_case_from_the_public_map_until_resolved(fl):
    e = fl
    set_threshold(e, 2)
    c, other = create_case(e, "alice"), create_case(e, "bob")
    support(e, "bob", c["id"])
    support(e, "carol", c["id"])
    assert set(_map_ids(e, "dave", c)) == {c["id"], other["id"]}
    f1 = flag(e, "bob", c["id"], "INAPPROPRIATE").json()
    assert c["id"] in _map_ids(e, "dave", c)                                                    # one flag is below the threshold
    flag(e, "carol", c["id"], "INAPPROPRIATE")
    assert _map_ids(e, "dave", c) == [other["id"]] and _map_ids(e, "overlooker", c) == [other["id"]] and _map_ids(e, "bob", c) == [other["id"]]
    assert c["id"] in _map_ids(e, "roads_op", c) and c["id"] in _map_ids(e, "admin", c)         # staff keep their operational view
    assert e.client.get(f"{API}/cases/{c['id']}", headers=e.headers("alice")).status_code == 200      # the case itself is unaffected
    assert e.client.post(f"{API}/flags/{f1['id']}/resolve", headers=e.idem("roads_op"), json={"status": "DISMISSED"}).status_code == 200
    assert c["id"] in _map_ids(e, "dave", c)                                                    # visible again


def test_other_kinds_of_flags_never_hide_a_case(fl):
    e = fl
    set_threshold(e, 2)
    c = create_case(e, "alice")
    support(e, "bob", c["id"])
    flag(e, "alice", c["id"], "OUTDATED")
    flag(e, "bob", c["id"], "OUTDATED")
    flag(e, "bob", c["id"], "INAPPROPRIATE")
    assert c["id"] in _map_ids(e, "carol", c)


def test_case_lists_carry_the_flag_fields_for_staff_only(fl):
    e = fl
    set_threshold(e, 1)
    c, quiet = create_case(e, "alice"), create_case(e, "alice")
    flag(e, "alice", c["id"], "INCORRECT")
    items = {i["id"]: i for i in e.client.get(f"{API}/cases", headers=e.headers("roads_op")).json()["items"]}
    assert items[c["id"]]["open_flag_count"] == 1 and items[c["id"]]["needs_flag_review"] is True
    assert items[quiet["id"]]["open_flag_count"] == 0 and items[quiet["id"]]["needs_flag_review"] is False
    mine = {i["id"]: i for i in e.client.get(f"{API}/cases", headers=e.headers("alice")).json()["items"]}
    assert mine[c["id"]]["open_flag_count"] == 0 and mine[c["id"]]["needs_flag_review"] is False
    patched = e.client.patch(f"{API}/cases/{c['id']}", headers=e.idem("roads_op"), json={"title": "Pothole near the school"}).json()
    assert patched["open_flag_count"] == 1 and patched["needs_flag_review"] is True


def test_the_case_list_counts_flags_with_one_grouped_query(fl):
    from sqlalchemy import event

    from backend.db import session as dbs
    e = fl
    cases = [create_case(e, "alice") for _ in range(4)]
    for c in cases:
        flag(e, "alice", c["id"], "OUTDATED")
    seen: list[str] = []

    def rec(conn, cursor, statement, *args):
        seen.append(statement)
    event.listen(dbs.engine, "before_cursor_execute", rec)
    try:
        assert e.client.get(f"{API}/cases", headers=e.headers("roads_op")).status_code == 200
    finally:
        event.remove(dbs.engine, "before_cursor_execute", rec)
    assert sum("case_flags" in s for s in seen) == 1


# ------------------------------------------------------------------------------------------------ review round: map hiding after UPHELD, map_hidden, every staff view
def _flag_three_inappropriate(e, c):
    for who in ("bob", "carol", "dave"):
        support(e, who, c["id"])
    return [flag(e, who, c["id"], "INAPPROPRIATE").json() for who in ("bob", "carol", "dave")]


def _resolve(e, who, flag_id, status):
    r = e.client.post(f"{API}/flags/{flag_id}/resolve", headers=e.idem(who), json={"status": status})
    assert r.status_code == 200, r.text


def test_an_upheld_inappropriate_flag_keeps_the_case_off_the_public_map(fl):
    e = fl
    c, other = create_case(e, "alice"), create_case(e, "alice")
    flags = _flag_three_inappropriate(e, c)
    assert _map_ids(e, "alice", c) == [other["id"]]
    _resolve(e, "roads_op", flags[0]["id"], "UPHELD")
    assert _map_ids(e, "alice", c) == [other["id"]]                                             # 2 open < 3, but one flag was upheld: still hidden
    _resolve(e, "roads_op", flags[1]["id"], "DISMISSED")
    _resolve(e, "roads_op", flags[2]["id"], "DISMISSED")
    assert _map_ids(e, "alice", c) == [other["id"]] and e.client.get(f"{API}/cases/{c['id']}", headers=e.headers("roads_op")).json()["map_hidden"] is True


def test_dismissing_every_flag_lifts_the_hiding(fl):
    e = fl
    c = create_case(e, "alice")
    flags = _flag_three_inappropriate(e, c)
    assert c["id"] not in _map_ids(e, "alice", c)
    assert e.client.get(f"{API}/cases/{c['id']}", headers=e.headers("roads_op")).json()["map_hidden"] is True
    for f in flags:
        _resolve(e, "roads_op", f["id"], "DISMISSED")
    assert c["id"] in _map_ids(e, "alice", c)
    assert e.client.get(f"{API}/cases/{c['id']}", headers=e.headers("roads_op")).json()["map_hidden"] is False


def test_map_hidden_tells_inappropriate_flags_from_other_flags_and_is_staff_only(fl):
    e = fl
    plain, bad = create_case(e, "alice"), create_case(e, "alice")
    for who in ("bob", "carol"):
        support(e, who, plain["id"])
    for who in ("alice", "bob", "carol"):
        flag(e, who, plain["id"], "OUTDATED")
    _flag_three_inappropriate(e, bad)
    items = {i["id"]: i for i in e.client.get(f"{API}/cases", headers=e.headers("roads_op")).json()["items"]}
    assert (items[plain["id"]]["needs_flag_review"], items[plain["id"]]["map_hidden"]) == (True, False)
    assert (items[bad["id"]]["needs_flag_review"], items[bad["id"]]["map_hidden"]) == (True, True)
    mine = {i["id"]: i for i in e.client.get(f"{API}/cases", headers=e.headers("alice")).json()["items"]}
    assert mine[bad["id"]]["map_hidden"] is False and mine[bad["id"]]["needs_flag_review"] is False      # citizens learn nothing


def test_review_notification_text_counts_flags_and_mentions_the_map_only_when_hidden(fl):
    e = fl
    plain, bad = create_case(e, "alice"), create_case(e, "alice")
    for who in ("bob", "carol"):
        support(e, who, plain["id"])
    for who in ("alice", "bob", "carol"):
        flag(e, who, plain["id"], "OUTDATED")
    _flag_three_inappropriate(e, bad)
    msgs = {p["case_id"]: p["message"] for who, p in notified(e) if who == "roads_op"}
    assert "3 open flags" in msgs[plain["id"]] and "citizens" not in msgs[plain["id"]] and "public map" not in msgs[plain["id"]]
    assert "3 open flags" in msgs[bad["id"]] and "hidden from the public map" in msgs[bad["id"]]


def test_every_case_view_staff_receive_carries_the_flag_fields(fl):
    e = fl
    set_threshold(e, 1)
    c, d = create_case(e, "alice"), create_case(e, "alice")
    flag(e, "alice", c["id"], "INCORRECT")
    flag(e, "alice", d["id"], "INCORRECT")
    rej = e.client.post(f"{API}/cases/{c['id']}/reject", headers=e.idem("roads_op"), json={"reason": "duplicate of another"})
    assert rej.status_code == 200 and (rej.json()["open_flag_count"], rej.json()["needs_flag_review"], rej.json()["map_hidden"]) == (1, True, False)
    _edit_case(e, d["id"], status="RESOLVED")
    reo = e.client.post(f"{API}/cases/{d['id']}/reopen", headers=e.idem("roads_op"), json={"reason": "problem is back"})
    assert reo.status_code == 200 and reo.json()["open_flag_count"] == 1 and reo.json()["needs_flag_review"] is True
    made = e.client.post(f"{API}/cases", headers=e.idem("roads_op"), json={"description": "Broken lamp", "category": "roads", "subcategory": "pothole", "location": e.where})
    assert made.status_code == 201 and made.json()["case"]["open_flag_count"] == 0 and made.json()["case"]["needs_flag_review"] is False
    snap = e.client.get(f"{API}/sync/changes", headers=e.headers("roads_op")).json()["cases"]
    assert snap[c["id"]]["open_flag_count"] == 1 and snap[c["id"]]["needs_flag_review"] is True and snap[d["id"]]["open_flag_count"] == 1
    mine = e.client.get(f"{API}/sync/changes", headers=e.headers("alice")).json()["cases"]
    assert mine[c["id"]]["open_flag_count"] == 0 and mine[c["id"]]["needs_flag_review"] is False and mine[c["id"]]["map_hidden"] is False


def test_hotspots_and_recurring_problems_keep_case_ids_staff_only_with_a_hidden_case(fl):
    e = fl
    set_threshold(e, 1)
    cases = [create_case(e, "alice") for _ in range(8)]
    support(e, "bob", cases[0]["id"])
    assert flag(e, "bob", cases[0]["id"], "INAPPROPRIATE").status_code == 201
    assert cases[0]["id"] not in _map_ids(e, "alice", cases[0])
    rec = e.client.get(f"{API}/map/recurring-problems", headers=e.headers("admin")).json()["items"]
    assert rec and cases[0]["id"] in rec[0]["case_ids"]                                         # staff keep the full picture
    for path in ("recurring-problems", "hotspots"):
        staff = e.client.get(f"{API}/map/{path}", headers=e.headers("admin")).json()["items"]
        assert all("case_ids" in i for i in staff)
        for who in ("alice", "overlooker"):
            items = e.client.get(f"{API}/map/{path}", headers=e.headers(who)).json()["items"]
            assert all("case_ids" not in i for i in items), (path, who)


# ------------------------------------------------------------------------------------------------ review round: exactly-once review, resolve races, recipients
def test_lowering_the_threshold_below_the_current_count_fires_on_the_next_flag(fl):
    e = fl
    c = create_case(e, "alice")
    support(e, "bob", c["id"])
    flag(e, "alice", c["id"], "OUTDATED")
    flag(e, "bob", c["id"], "OUTDATED")
    set_threshold(e, 1)                                                                         # 2 open flags are now above the threshold
    assert notified(e) == []
    assert flag(e, "bob", c["id"], "INCORRECT").status_code == 201
    assert timeline_types(e, "admin", c["id"]).count("FLAG_REVIEW_REQUESTED") == 1 and len(notified(e)) == 3


def test_the_review_fires_again_after_a_resolution_and_a_new_crossing(fl):
    e = fl
    set_threshold(e, 2)
    c = create_case(e, "alice")
    support(e, "bob", c["id"])
    support(e, "carol", c["id"])
    f1 = flag(e, "alice", c["id"], "OUTDATED").json()
    flag(e, "bob", c["id"], "OUTDATED")
    assert timeline_types(e, "admin", c["id"]).count("FLAG_REVIEW_REQUESTED") == 1
    _resolve(e, "roads_op", f1["id"], "DISMISSED")
    flag(e, "carol", c["id"], "OUTDATED")                                                       # open 2 again, the old request is older than the resolution
    assert timeline_types(e, "admin", c["id"]).count("FLAG_REVIEW_REQUESTED") == 2 and len(notified(e)) == 6


def test_a_racing_request_that_already_recorded_the_review_does_not_repeat_it(fl):
    from backend.services.workflow import add_event
    e = fl
    c = create_case(e, "alice")
    support(e, "bob", c["id"])
    flag(e, "alice", c["id"], "OUTDATED")
    flag(e, "bob", c["id"], "OUTDATED")
    with e.session_factory() as db:                                                             # the other request committed its event first
        add_event(db, c["id"], "FLAG_REVIEW_REQUESTED", actor_id=None, actor_role="SYSTEM", visibility="INTERNAL", metadata={})
        db.commit()
    assert flag(e, "roads_op", c["id"], "INCORRECT").status_code == 201
    assert timeline_types(e, "admin", c["id"]).count("FLAG_REVIEW_REQUESTED") == 1 and notified(e) == []


def test_a_concurrent_duplicate_is_a_clean_409(fl, monkeypatch):
    from backend.models import CaseFlag
    from backend.services import flags as flag_service
    e = fl
    c = create_case(e, "alice")

    def racing(db, case_id, user_id, kind):                                                     # the other request inserts between our check and our insert
        db.add(CaseFlag(case_id=case_id, user_id=user_id, kind=kind))
        db.flush()
        return False
    monkeypatch.setattr(flag_service, "_already_flagged", racing)
    r = flag(e, "alice", c["id"], "OUTDATED")
    assert r.status_code == 409 and r.json()["error"]["code"] == "FLAG_ALREADY_EXISTS"
    assert "only once" in r.json()["error"]["message"] and "resolved" in r.json()["error"]["message"]
    assert e.client.post(f"{API}/flags/{uuid.uuid4()}/resolve", headers=e.idem("admin"), json={"status": "UPHELD"}).status_code == 404       # the app still works


def test_a_user_cannot_flag_a_kind_again_after_it_was_resolved(fl):
    e = fl
    c = create_case(e, "alice")
    f = flag(e, "alice", c["id"], "OUTDATED").json()
    _resolve(e, "roads_op", f["id"], "DISMISSED")
    again = flag(e, "alice", c["id"], "OUTDATED")
    assert again.status_code == 409 and again.json()["error"]["code"] == "FLAG_ALREADY_EXISTS" and "even after" in again.json()["error"]["message"]


def test_staff_cannot_resolve_their_own_flag_and_a_resolved_flag_stays_resolved(fl):
    e = fl
    c = create_case(e, "alice")
    f = flag(e, "roads_op", c["id"], "INCORRECT").json()
    own = e.client.post(f"{API}/flags/{f['id']}/resolve", headers=e.idem("roads_op"), json={"status": "UPHELD"})
    assert own.status_code == 403 and own.json()["error"]["code"] == "FLAG_NOT_ALLOWED"
    assert e.client.get(f"{API}/cases/{c['id']}/flags", headers=e.headers("admin")).json()["items"][0]["status"] == "OPEN"
    _resolve(e, "roads_mgr", f["id"], "UPHELD")                                                 # a colleague may
    late = e.client.post(f"{API}/flags/{f['id']}/resolve", headers=e.idem("admin"), json={"status": "DISMISSED"})
    assert late.status_code == 409 and late.json()["error"]["code"] == "FLAG_ALREADY_RESOLVED"
    assert e.client.get(f"{API}/cases/{c['id']}/flags", headers=e.headers("admin")).json()["items"][0]["status"] == "UPHELD"     # the first verdict stands


def test_the_flag_audit_rows_hold_ids_and_codes_only(fl):
    import json

    from backend.models import AuditEvent
    e = fl
    c = create_case(e, "alice")
    f = flag(e, "alice", c["id"], "INCORRECT", comment="my phone is 9999999999 and I am Alice").json()
    _resolve(e, "roads_op", f["id"], "UPHELD")
    with e.session_factory() as db:
        created = db.query(AuditEvent).filter(AuditEvent.entity_id == f["id"], AuditEvent.action == "case_flag.created").one()
        resolved = db.query(AuditEvent).filter(AuditEvent.entity_id == f["id"], AuditEvent.action == "case_flag.resolved").one()
        assert (created.entity_type, created.actor_id, created.before_json) == ("CASE_FLAG", e.users["alice"]["id"], None)
        assert created.after_json == {"case_id": c["id"], "kind": "INCORRECT", "status": "OPEN"}
        assert (resolved.actor_id, resolved.before_json) == (e.users["roads_op"]["id"], {"status": "OPEN"})
        assert resolved.after_json == {"case_id": c["id"], "kind": "INCORRECT", "status": "UPHELD"}
        blob = json.dumps([created.after_json, resolved.after_json])
        assert "9999999999" not in blob and "@example.test" not in blob and "Alice" not in blob


def _edit_case(e, case_id, **fields):
    from backend.models import CivicCase
    with e.session_factory() as db:
        for k, v in fields.items():
            setattr(db.get(CivicCase, case_id), k, v)
        db.commit()


def test_a_case_without_a_department_goes_to_the_ward_officer_and_without_a_ward_to_the_city_admins(fl):
    e = fl
    set_threshold(e, 1)
    c = create_case(e, "alice")
    _edit_case(e, c["id"], department_id=None)
    assert flag(e, "alice", c["id"], "INCORRECT").status_code == 201
    assert [who for who, _ in notified(e)] == ["ward_officer"]                                  # the department operators do not own an unassigned case
    d = create_case(e, "alice")
    _edit_case(e, d["id"], department_id=None, ward_id=None)
    assert flag(e, "alice", d["id"], "INCORRECT").status_code == 201
    assert sorted((who, p["case_id"]) for who, p in notified(e)) == sorted([("admin", d["id"]), ("ward_officer", c["id"])])


def test_inactive_reviewers_are_skipped_and_the_city_admins_are_the_fallback(fl):
    from backend.models import User
    e = fl
    set_threshold(e, 1)
    c = create_case(e, "alice")
    with e.session_factory() as db:
        db.get(User, e.users["roads_op"]["id"]).is_active = False
        db.commit()
    assert flag(e, "alice", c["id"], "INCORRECT").status_code == 201
    assert sorted(who for who, _ in notified(e)) == ["roads_mgr", "ward_officer"]               # the inactive operator is not told
    d = create_case(e, "alice")
    with e.session_factory() as db:
        for k in ("roads_mgr", "ward_officer"):
            db.get(User, e.users[k]["id"]).is_active = False
        db.commit()
    assert flag(e, "alice", d["id"], "INCORRECT").status_code == 201
    assert [who for who, p in notified(e) if p["case_id"] == d["id"]] == ["admin"]
