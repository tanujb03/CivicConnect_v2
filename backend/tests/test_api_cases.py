"""§51A.4 / §51A.10 / §51A.11 + §35 + §43: case creation, visibility, edits, timeline, state machine."""
import pytest

from backend.core.exceptions import CivicConnectException
from backend.services import workflow


def body(e, **kw):
    return {"description": "Huge pothole outside the school gate, two bikes already fell", "category": "roads", "subcategory": "pothole", "location": e.where, "language": "en", **kw}


def create(e, who="alice", key=None, **kw):
    r = e.client.post("/api/v1/cases", headers=e.idem(who, key), json=body(e, **kw))
    assert r.status_code in (200, 201), r.text
    return r.json()["case"]


# ------------------------------------------------------------------------------------------------ state machine (pure)
def test_state_machine_follows_section_35():
    assert workflow.can_transition("SUBMITTED", "AI_PROCESSING") and workflow.can_transition("AWAITING_VERIFICATION", "VERIFIED")
    assert workflow.can_transition("AWAITING_VERIFICATION", "REOPENED") and workflow.can_transition("VERIFIED", "RESOLVED")
    assert not workflow.can_transition("SUBMITTED", "RESOLVED") and not workflow.can_transition("NEEDS_REVIEW", "IN_PROGRESS")
    assert not workflow.can_transition("RESOLVED", "ASSIGNED") and workflow.TRANSITIONS["REJECTED"] == frozenset()
    for state in workflow.STATES:                                  # every state is reachable and every target is a known state
        assert all(t in workflow.STATES for t in workflow.TRANSITIONS[state])


def test_illegal_transition_is_refused_with_the_allowed_moves(staffed):
    from backend.models import CivicCase
    c = create(staffed)
    with staffed.session_factory() as db:
        case = db.get(CivicCase, c["id"])
        with pytest.raises(CivicConnectException) as ex:
            workflow.transition(db, case, "RESOLVED", actor_id=None, actor_role="SYSTEM")
        assert ex.value.code == "INVALID_STATE_TRANSITION" and ex.value.status_code == 409 and "ASSIGNED" in ex.value.details["allowed"]
        with pytest.raises(CivicConnectException) as ex:
            workflow.transition(db, case, "REJECTED", actor_id="x", actor_role="operator")        # a rejection needs a reason
        assert ex.value.code == "REASON_REQUIRED"


# ------------------------------------------------------------------------------------------------ creation
def test_create_case_is_server_authoritative_and_walks_to_needs_review(staffed):
    e = staffed
    c = create(e, priority="CRITICAL", status="RESOLVED", severity="LOW")                    # client-sent authority fields are ignored
    assert c["case_number"].startswith("CC-2026-") and c["status"] == "NEEDS_REVIEW" and c["category"] == "roads" and c["subcategory"] == "pothole"
    assert c["priority"] in ("LOW", "NORMAL", "HIGH", "URGENT", "CRITICAL") and c["priority"] != "RESOLVED" and c["department_id"] == "road_maintenance"
    assert c["ward_id"] == e.ward_id and c["sla_hours"] and c["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    again = create(e)
    assert again["case_number"] != c["case_number"] and int(again["case_number"][-6:]) == int(c["case_number"][-6:]) + 1
    tl = e.client.get(f"/api/v1/cases/{c['id']}/timeline", headers=e.headers("alice")).json()["items"]
    assert [t["event_type"] for t in tl] == ["CASE_CREATED", "STATUS_CHANGED", "STATUS_CHANGED"]
    assert [t["metadata"].get("to") for t in tl][1:] == ["AI_PROCESSING", "NEEDS_REVIEW"]


def test_create_case_validation(staffed):
    e = staffed
    h = e.idem("alice")
    assert e.client.post("/api/v1/cases", headers=h, json={"location": e.where}).status_code == 422                               # nothing to report
    assert e.client.post("/api/v1/cases", headers=e.idem("alice"), json={"description": "x", "location": {"latitude": 95, "longitude": 0}}).status_code == 422
    assert e.client.post("/api/v1/cases", headers=e.idem("alice"), json={"description": "x"}).status_code == 422                   # no location
    c = e.client.post("/api/v1/cases", headers=e.idem("alice"), json={"description": "something broken", "category": "made_up", "location": e.where}).json()["case"]
    assert c["category"] == "other"                                                                                                  # unknown category -> the human-triage bucket
    assert e.client.post("/api/v1/cases", headers=e.headers("alice"), json=body(e)).json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert e.client.post("/api/v1/cases", json=body(e)).status_code == 401


def test_overlooker_cannot_create_cases(staffed):
    r = staffed.client.post("/api/v1/cases", headers=staffed.idem("overlooker"), json=body(staffed))
    assert r.status_code == 403 and r.json()["error"]["code"] == "AUTH_FORBIDDEN"


def test_idempotency_key_replays_the_same_response_and_never_duplicates(staffed):
    e = staffed
    h = e.idem("alice", "key-1")
    first = e.client.post("/api/v1/cases", headers=h, json=body(e))
    second = e.client.post("/api/v1/cases", headers=h, json=body(e))
    assert first.status_code == second.status_code == 201 and first.json() == second.json() and second.headers["idempotent-replayed"] == "true"
    clash = e.client.post("/api/v1/cases", headers=h, json=body(e, description="a different report"))
    assert clash.status_code == 422 and clash.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert len(e.client.get("/api/v1/cases", headers=e.headers("alice")).json()["items"]) == 1
    other_user = e.client.post("/api/v1/cases", headers=e.idem("bob", "key-1"), json=body(e))                                       # the key is scoped per user
    assert other_user.status_code == 201 and other_user.json()["case"]["id"] != first.json()["case"]["id"]


def test_client_case_id_dedupes_offline_retries_even_with_a_new_idempotency_key(staffed):
    e = staffed
    a = e.client.post("/api/v1/cases", headers=e.idem("alice"), json=body(e, client_case_id="offline-1"))
    b = e.client.post("/api/v1/cases", headers=e.idem("alice"), json=body(e, client_case_id="offline-1"))
    assert a.status_code == 201 and b.status_code == 200 and a.json()["case"]["id"] == b.json()["case"]["id"]


def test_create_case_attaches_ready_evidence_only(staffed):
    e = staffed
    bad = e.client.post("/api/v1/cases", headers=e.idem("alice"), json=body(e, evidence_ids=["00000000-0000-0000-0000-000000000000"]))
    assert bad.status_code == 404 and bad.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"


# ------------------------------------------------------------------------------------------------ visibility (object level)
def test_citizens_see_only_their_own_cases_and_get_404_for_others(staffed):
    e = staffed
    mine, theirs = create(e, "alice"), create(e, "bob")
    ids = {c["id"] for c in e.client.get("/api/v1/cases", headers=e.headers("alice")).json()["items"]}
    assert ids == {mine["id"]}
    r = e.client.get(f"/api/v1/cases/{theirs['id']}", headers=e.headers("alice"))
    assert r.status_code == 404 and r.json()["error"]["code"] == "CASE_NOT_FOUND"                       # indistinguishable from "does not exist"
    assert e.client.get("/api/v1/cases/no-such-case", headers=e.headers("alice")).status_code == 404
    assert e.client.get(f"/api/v1/cases/{theirs['id']}/timeline", headers=e.headers("alice")).status_code == 404
    assert e.client.patch(f"/api/v1/cases/{theirs['id']}", headers=e.idem("alice"), json={"title": "hijack"}).status_code == 404


def test_staff_scopes_department_ward_city(staffed):
    e = staffed
    road = create(e, "alice")
    water = create(e, "alice", category="water_supply", subcategory="no_water_supply", description="No water since morning")
    def ids(who):
        return {c["id"] for c in e.client.get("/api/v1/cases?limit=100", headers=e.headers(who)).json()["items"]}
    assert ids("roads_op") == {road["id"]} and ids("water_op") == {water["id"]} and ids("roads_mgr") == {road["id"]}
    assert ids("admin") == {road["id"], water["id"]} and ids("ward_officer") == {road["id"], water["id"]}      # both cases are in the ward
    assert e.client.get(f"/api/v1/cases/{water['id']}", headers=e.headers("roads_op")).status_code == 404
    assert e.client.get(f"/api/v1/cases/{water['id']}", headers=e.headers("admin")).status_code == 200
    # a ward officer of another ward sees nothing
    from backend.models import Ward
    with e.session_factory() as db:
        other = db.query(Ward).filter(Ward.id != e.ward_id).first().id
    e.make_user("ward_officer", "other_ward", ward_id=other)
    assert ids("other_ward") == set()
    # an operator with no department sees nothing (deny by default)
    e.make_user("operator", "lost_op")
    assert ids("lost_op") == set()


def test_overlooker_gets_aggregates_but_never_case_lists(staffed):
    e = staffed
    c = create(e)
    assert e.client.get("/api/v1/cases", headers=e.headers("overlooker")).status_code == 403
    assert e.client.get(f"/api/v1/cases/{c['id']}", headers=e.headers("overlooker")).status_code == 404
    r = e.client.get("/api/v1/analytics/overview", headers=e.headers("overlooker"))
    assert r.status_code == 200 and r.json()["total_cases"] == 1


def test_case_detail_hides_the_reporter_from_citizens_and_shows_it_to_staff(staffed):
    e = staffed
    c = create(e)
    citizen = e.client.get(f"/api/v1/cases/{c['id']}", headers=e.headers("alice")).json()
    staff = e.client.get(f"/api/v1/cases/{c['id']}", headers=e.headers("roads_op")).json()
    assert citizen["is_reporter"] is True and citizen["reporter"] is None
    assert staff["is_reporter"] is False and staff["reporter"]["id"] == e.users["alice"]["id"]
    assert set(citizen) >= {"id", "case_number", "status", "priority", "location", "evidence", "work_orders", "timeline", "contributors"}


# ------------------------------------------------------------------------------------------------ listing
def test_listing_filters_sorting_and_cursor_pagination(staffed):
    e = staffed
    made = [create(e, "alice", description=f"pothole number {i} near the market") for i in range(5)]
    made += [create(e, "alice", category="water_supply", subcategory="no_water_supply", description="no water here")]
    h = e.headers("admin")
    page1 = e.client.get("/api/v1/cases?limit=4", headers=h).json()
    assert len(page1["items"]) == 4 and page1["next_cursor"]
    page2 = e.client.get(f"/api/v1/cases?limit=4&cursor={page1['next_cursor']}", headers=h).json()
    got = [c["id"] for c in page1["items"] + page2["items"]]
    assert len(got) == 6 and len(set(got)) == 6 and page2["next_cursor"] is None                      # no gaps, no repeats
    assert [c["case_number"] for c in page1["items"]] == sorted((c["case_number"] for c in made), reverse=True)[:4]    # newest first
    oldest = e.client.get("/api/v1/cases?sort=oldest&limit=2", headers=h).json()["items"]
    assert oldest[0]["case_number"] < oldest[1]["case_number"]
    assert len(e.client.get("/api/v1/cases?category=water_supply", headers=h).json()["items"]) == 1
    assert len(e.client.get("/api/v1/cases?status=NEEDS_REVIEW,RESOLVED", headers=h).json()["items"]) == 6
    assert e.client.get("/api/v1/cases?status=RESOLVED", headers=h).json()["items"] == []
    assert len(e.client.get("/api/v1/cases?q=market", headers=h).json()["items"]) == 5
    assert len(e.client.get(f"/api/v1/cases?q={made[0]['case_number']}", headers=h).json()["items"]) == 1
    assert e.client.get("/api/v1/cases?sort=bogus", headers=h).json()["error"]["code"] == "VALIDATION_ERROR"
    assert e.client.get("/api/v1/cases?limit=0", headers=h).status_code == 422
    assert len(e.client.get("/api/v1/cases?limit=1000", headers=h).json()["items"]) == 6               # limit is clamped, never an error or a full dump
    prio = e.client.get("/api/v1/cases?sort=priority", headers=h).json()["items"]
    assert len(prio) == 6


# ------------------------------------------------------------------------------------------------ edits
def test_citizen_edits_are_limited_to_their_own_pre_processing_case(staffed):
    e = staffed
    c = create(e)
    ok = e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("alice"), json={"title": "Pothole at Shivaji school gate"})
    assert ok.status_code == 200 and ok.json()["title"] == "Pothole at Shivaji school gate"
    r = e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("alice"), json={"priority": "CRITICAL"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "AUTH_FORBIDDEN" and r.json()["error"]["details"]["field"] == "priority"
    r = e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("alice"), json={"status": "RESOLVED"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "FIELD_NOT_PERMITTED"                    # status only moves through the workflow
    assert e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("bob"), json={"title": "x"}).status_code == 404
    echo = e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("alice"), json={"title": "Pothole at Shivaji school gate", "case_number": c["case_number"], "status": "NEEDS_REVIEW"})
    assert echo.status_code == 200                                                                          # echoing unchanged read-only fields is harmless
    from backend.models import CivicCase
    with e.session_factory() as db:
        db.get(CivicCase, c["id"]).status = "ASSIGNED"
        db.commit()
    late = e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("alice"), json={"title": "too late"})
    assert late.status_code == 409 and late.json()["error"]["code"] == "CASE_NOT_EDITABLE"


def test_staff_overrides_need_a_reason_and_are_audited(staffed):
    from backend.models import AuditEvent
    e = staffed
    c = create(e)
    no_reason = e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("roads_op"), json={"priority": "URGENT"})
    assert no_reason.status_code == 422 and no_reason.json()["error"]["code"] == "REASON_REQUIRED"
    ok = e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("roads_op"), json={"priority": "URGENT", "reason": "school zone, children at risk"})
    assert ok.status_code == 200 and ok.json()["priority"] == "URGENT"
    cat = e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("admin"), json={"category": "street_lighting", "subcategory": "light_not_working", "reason": "misfiled"})
    assert cat.status_code == 200 and cat.json()["category"] == "street_lighting"
    with e.session_factory() as db:
        actions = [(a.action, a.before_json, a.after_json) for a in db.query(AuditEvent).order_by(AuditEvent.created_at).all()]
    assert [a for a, _, _ in actions] == ["PRIORITY_OVERRIDDEN", "CATEGORY_OVERRIDDEN"]
    assert actions[0][1]["priority"] != "URGENT" and actions[0][2]["priority"] == "URGENT" and actions[0][2]["reason"]
    bad_dept = e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("admin"), json={"department_id": "no_such", "reason": "x"})
    assert bad_dept.json()["error"]["code"] == "DEPARTMENT_UNKNOWN"
    tl = e.client.get(f"/api/v1/cases/{c['id']}/timeline", headers=e.headers("alice")).json()["items"]
    assert "CASE_UPDATED" not in [t["event_type"] for t in tl]            # staff-side edits are internal events: the citizen's timeline does not show them
    assert "CASE_UPDATED" in [t["event_type"] for t in e.client.get(f"/api/v1/cases/{c['id']}/timeline", headers=e.headers("admin")).json()["items"]]


# ------------------------------------------------------------------------------------------------ support / contributors
def test_support_raises_the_count_and_the_priority_inputs_and_is_idempotent_per_user(staffed):
    e = staffed
    c = create(e, "alice")
    r = e.client.post(f"/api/v1/cases/{c['id']}/support", headers=e.idem("bob"))
    assert r.status_code == 200 and r.json()["support_count"] == 1 and r.json()["created"] is True
    again = e.client.post(f"/api/v1/cases/{c['id']}/support", headers=e.idem("bob"))
    assert again.json()["support_count"] == 1 and again.json()["created"] is False
    assert e.client.get(f"/api/v1/cases/{c['id']}", headers=e.headers("bob")).status_code == 200            # a supporter can now follow the case
    detail = e.client.get(f"/api/v1/cases/{c['id']}", headers=e.headers("bob")).json()
    assert detail["reporter"] is None and detail["is_reporter"] is False and detail["evidence"] == []
    gone = e.client.request("DELETE", f"/api/v1/cases/{c['id']}/support", headers=e.idem("bob"))
    assert gone.json()["support_count"] == 0 and gone.json()["removed"] is True
    assert e.client.get(f"/api/v1/cases/{c['id']}", headers=e.headers("bob")).status_code == 404
    assert e.client.post("/api/v1/cases/nope/support", headers=e.idem("bob")).status_code == 404


def test_contributors_can_be_added_by_the_reporter_or_staff_only(staffed):
    e = staffed
    c = create(e, "alice")
    r = e.client.post(f"/api/v1/cases/{c['id']}/contributors", headers=e.idem("alice"), json={"user_id": e.users["bob"]["id"], "role": "CONTRIBUTOR"})
    assert r.status_code == 201 and r.json()["role"] == "CONTRIBUTOR"
    assert e.client.get(f"/api/v1/cases/{c['id']}", headers=e.headers("bob")).status_code == 200
    third = e.make_user("citizen", "carol")
    r = e.client.post(f"/api/v1/cases/{c['id']}/contributors", headers=e.idem("bob"), json={"user_id": third["id"]})
    assert r.status_code == 403                                                                           # a contributor cannot recruit others
    r = e.client.post(f"/api/v1/cases/{c['id']}/contributors", headers=e.idem("alice"), json={"user_id": "nobody"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "USER_NOT_FOUND"
    r = e.client.post(f"/api/v1/cases/{c['id']}/contributors", headers=e.idem("roads_op"), json={"user_id": third["id"]})
    assert r.status_code == 201


# ------------------------------------------------------------------------------------------------ reject / reopen
def test_reject_needs_a_reason_staff_and_leaves_an_audit_event(staffed):
    from backend.models import AuditEvent
    e = staffed
    c = create(e)
    assert e.client.post(f"/api/v1/cases/{c['id']}/reject", headers=e.idem("alice"), json={"reason": "no thanks"}).status_code == 403
    assert e.client.post(f"/api/v1/cases/{c['id']}/reject", headers=e.idem("roads_op"), json={"reason": "x"}).status_code == 422
    r = e.client.post(f"/api/v1/cases/{c['id']}/reject", headers=e.idem("roads_op"), json={"reason": "duplicate of an open complaint"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED" and r.json()["closed_at"]
    with e.session_factory() as db:
        assert db.query(AuditEvent).filter(AuditEvent.action == "CASE_REJECTED").count() == 1
    again = e.client.post(f"/api/v1/cases/{c['id']}/reject", headers=e.idem("roads_op"), json={"reason": "again please"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "INVALID_STATE_TRANSITION"      # terminal
    notes = e.client.get("/api/v1/me/notifications", headers=e.headers("alice")).json()["items"]
    assert any(n["type"] == "CASE_UPDATED" and n["payload"]["status"] == "REJECTED" for n in notes)         # the reporter is told


def test_reopen_is_staff_only_and_only_from_resolved_or_awaiting(staffed):
    from backend.models import CivicCase
    e = staffed
    c = create(e)
    assert e.client.post(f"/api/v1/cases/{c['id']}/reopen", headers=e.idem("roads_op"), json={"reason": "not closed yet"}).status_code == 409
    with e.session_factory() as db:
        db.get(CivicCase, c["id"]).status = "RESOLVED"
        db.commit()
    assert e.client.post(f"/api/v1/cases/{c['id']}/reopen", headers=e.idem("alice"), json={"reason": "I say so"}).status_code == 403
    r = e.client.post(f"/api/v1/cases/{c['id']}/reopen", headers=e.idem("roads_op"), json={"reason": "problem is back"})
    assert r.status_code == 200 and r.json()["status"] == "REOPENED" and r.json()["reopen_count"] == 1 and r.json()["closed_at"] is None


def test_timeline_is_role_filtered(staffed):
    e = staffed
    c = create(e)
    e.client.patch(f"/api/v1/cases/{c['id']}", headers=e.idem("admin"), json={"priority": "CRITICAL", "reason": "checked on site"})
    citizen = e.client.get(f"/api/v1/cases/{c['id']}/timeline", headers=e.headers("alice")).json()["items"]
    staff = e.client.get(f"/api/v1/cases/{c['id']}/timeline", headers=e.headers("admin")).json()["items"]
    assert len(staff) == len(citizen) + 1
    assert all(t["actor_id"] is None or t["actor_id"] == e.users["alice"]["id"] for t in citizen) or all(t["actor_id"] is None for t in citizen)
    page = e.client.get(f"/api/v1/cases/{c['id']}/timeline?limit=2", headers=e.headers("admin")).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = e.client.get(f"/api/v1/cases/{c['id']}/timeline?limit=2&cursor={page['next_cursor']}", headers=e.headers("admin")).json()
    assert len(page["items"]) + len(rest["items"]) == len(staff)
