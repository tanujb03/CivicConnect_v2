"""The whole demo path of the implementation plan, through the HTTP API and the SQL-backed AI gateway:

citizen input -> evidence -> case -> fusion -> triage -> work order -> resolution evidence -> verification -> analytics
"""
from backend.models import AIAnalysis, AuditEvent, CaseEvent, CaseRelation, CivicCase, Notification, WorkOrder
from backend.tests.helpers import create_case, upload


def triage_and_assign(e, case, operator="roads_op", **override):
    rec = e.client.post(f"/api/v1/cases/{case['id']}/triage/analyze", headers=e.headers(operator))
    assert rec.status_code == 200, rec.text
    r = rec.json()["recommendation"]
    decision = {"severity": r["severity"], "priority": r["priority"], "department_id": r["department_id"], "sla_hours": r["sla_hours"], "reason": "confirmed from the photo", **override}
    d = e.client.post(f"/api/v1/cases/{case['id']}/triage/decision", headers=e.idem(operator), json=decision)
    assert d.status_code == 200, d.text
    return rec.json(), d.json()


def test_full_lifecycle_from_report_to_resolved(staffed):
    e = staffed
    photo = upload(e, "alice")                                                       # 1. evidence (signed URL protocol)
    assert photo["status"] == "READY" and photo["media_type"] == "IMAGE" and photo["case_id"] is None
    case = create_case(e, "alice", evidence_ids=[photo["id"]])                       # 2. case with the evidence attached
    cid = case["id"]
    detail = e.client.get(f"/api/v1/cases/{cid}", headers=e.headers("alice")).json()
    assert [x["id"] for x in detail["evidence"]] == [photo["id"]] and detail["status"] == "NEEDS_REVIEW"

    fusion = e.client.post(f"/api/v1/cases/{cid}/fusion/analyze", headers=e.headers("roads_op"))      # 3. fusion (SQL candidates)
    assert fusion.status_code == 200 and fusion.json()["recommendation"] == "NO_MATCH"

    rec, dec = triage_and_assign(e, case)                                            # 4. triage: AI recommends, a human decides
    assert rec["recommendation"]["department_id"] == "road_maintenance" and dec["decided_by"] == e.users["roads_op"]["id"] and dec["overridden"] is False
    assert e.client.get(f"/api/v1/cases/{cid}", headers=e.headers("roads_op")).json()["status"] == "ASSIGNED"

    wo = e.client.post(f"/api/v1/cases/{cid}/work-orders", headers=e.idem("roads_op"),                # 5. work order
                       json={"assignee_id": e.users["roads_worker"]["id"], "instructions": "Fill and compact the pothole", "due_at": "2026-12-01T10:00:00Z"})
    assert wo.status_code == 201 and wo.json()["status"] == "ASSIGNED" and wo.json()["case_number"] == case["case_number"]
    wid = wo.json()["id"]
    assert e.client.get(f"/api/v1/cases/{cid}", headers=e.headers("roads_op")).json()["status"] == "WORK_ORDER_CREATED"
    mine = e.client.get("/api/v1/work-orders", headers=e.headers("roads_worker")).json()["items"]
    assert [w["id"] for w in mine] == [wid]
    assert e.client.get("/api/v1/work-orders", headers=e.headers("water_worker")).json()["items"] == []              # not theirs
    assert e.client.get(f"/api/v1/work-orders/{wid}", headers=e.headers("water_worker")).status_code == 404
    ctx = e.client.get(f"/api/v1/work-orders/{wid}", headers=e.headers("roads_worker")).json()
    assert ctx["case"]["case_number"] == case["case_number"] and ctx["evidence"][0]["download_url"] and ctx["instructions"] == "Fill and compact the pothole"

    early = e.client.post(f"/api/v1/work-orders/{wid}/complete", headers=e.idem("roads_worker"), json={"notes": "done", "resolution_evidence_ids": []})
    assert early.status_code == 409 and early.json()["error"]["code"] == "INVALID_STATE"                          # must start first
    started = e.client.post(f"/api/v1/work-orders/{wid}/start", headers=e.idem("roads_worker"))                    # 6. start
    assert started.status_code == 200 and started.json()["status"] == "IN_PROGRESS" and started.json()["started_at"]
    assert e.client.get(f"/api/v1/cases/{cid}", headers=e.headers("alice")).json()["status"] == "IN_PROGRESS"

    no_proof = e.client.post(f"/api/v1/work-orders/{wid}/complete", headers=e.idem("roads_worker"), json={"notes": "fixed", "resolution_evidence_ids": []})
    assert no_proof.status_code == 422 and no_proof.json()["error"]["code"] == "RESOLUTION_EVIDENCE_REQUIRED"
    after = upload(e, "roads_worker", name="after.jpg", purpose="RESOLUTION")                                       # 7. resolution evidence
    done = e.client.post(f"/api/v1/work-orders/{wid}/complete", headers=e.idem("roads_worker"), json={"notes": "Pothole filled and compacted", "resolution_evidence_ids": [after["id"]]})
    assert done.status_code == 200 and done.json()["status"] == "COMPLETED" and done.json().get("resolution_review") is None    # field worker never sees AI flags
    state = e.client.get(f"/api/v1/cases/{cid}", headers=e.headers("alice")).json()
    assert state["status"] == "AWAITING_VERIFICATION" and state["closed_at"] is None                              # completing work does NOT close the case
    assert any(x["purpose"] == "RESOLUTION" for x in state["evidence"])                                           # the reporter can see the proof to verify it
    notes = e.client.get("/api/v1/me/notifications", headers=e.headers("alice")).json()["items"]
    assert "VERIFICATION_REQUESTED" in [n["type"] for n in notes]

    wrong = e.client.post(f"/api/v1/cases/{cid}/verification", headers=e.idem("bob"), json={"result": "YES"})
    assert wrong.status_code == 404                                                                               # bob cannot even see the case
    v = e.client.post(f"/api/v1/cases/{cid}/verification", headers=e.idem("alice"), json={"result": "YES", "comment": "road is smooth again"})   # 8. verification
    assert v.status_code == 201 and v.json()["case_status"] == "RESOLVED" and v.json()["reopened"] is False
    final = e.client.get(f"/api/v1/cases/{cid}", headers=e.headers("admin")).json()
    assert final["status"] == "RESOLVED" and final["closed_at"]
    again = e.client.post(f"/api/v1/cases/{cid}/verification", headers=e.idem("alice"), json={"result": "YES"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "NOT_AWAITING_VERIFICATION"

    timeline = [(t["event_type"], t["metadata"].get("to")) for t in e.client.get(f"/api/v1/cases/{cid}/timeline?limit=100", headers=e.headers("admin")).json()["items"]]
    statuses = [to for ev, to in timeline if ev == "STATUS_CHANGED"]
    assert statuses == ["AI_PROCESSING", "NEEDS_REVIEW", "ASSIGNED", "WORK_ORDER_CREATED", "IN_PROGRESS", "RESOLUTION_SUBMITTED", "AWAITING_VERIFICATION", "VERIFIED", "RESOLVED"]
    assert {"TRIAGE_DECIDED", "WORK_ORDER_ASSIGNED", "WORK_STARTED", "VERIFICATION_RECORDED", "EVIDENCE_ADDED"} <= {ev for ev, _ in timeline}
    citizen_tl = {t["event_type"] for t in e.client.get(f"/api/v1/cases/{cid}/timeline?limit=100", headers=e.headers("alice")).json()["items"]}
    assert "TRIAGE_DECIDED" not in citizen_tl and "WORK_ORDER_ASSIGNED" not in citizen_tl and "VERIFICATION_RECORDED" in citizen_tl

    with e.session_factory() as db:                                                                               # persistence of everything AI and audit
        assert {a.task_type for a in db.query(AIAnalysis).filter(AIAnalysis.case_id == cid)} >= {"fusion", "triage", "resolution"}
        actions = [a.action for a in db.query(AuditEvent).order_by(AuditEvent.created_at)]
        assert "TRIAGE_DECISION_RECORDED" in actions and "VERIFICATION_RECORDED" in actions and "CASE_RESOLVED" in actions and "CASE_VERIFIED" in actions
        types = {n.type for n in db.query(Notification)}
        assert {"CASE_ASSIGNED", "WORK_ORDER_ASSIGNED", "VERIFICATION_REQUESTED", "CASE_RESOLVED"} <= types

    ov = e.client.get("/api/v1/analytics/overview", headers=e.headers("admin")).json()                            # 9. analytics reflect it
    assert ov["total_cases"] == 1 and ov["open_cases"] == 0 and ov["median_resolution_hours"] >= 0
    assert ov["category_distribution"] == [{"category": "roads", "count": 1}] and sum(d["resolved"] for d in ov["daily_trend"]) == 1
    dept = e.client.get("/api/v1/analytics/departments/road_maintenance", headers=e.headers("roads_op")).json()
    assert dept["resolved"] == 1 and dept["active"] == 0
    assert e.client.get("/api/v1/analytics/departments/water_supply", headers=e.headers("roads_op")).status_code == 403     # another department


def test_staff_review_of_a_completed_work_order_exposes_the_ai4_flags_but_never_acts_on_them(staffed):
    e = staffed
    case = create_case(e)
    triage_and_assign(e, case)
    wid = e.client.post(f"/api/v1/cases/{case['id']}/work-orders", headers=e.idem("roads_op"), json={"assignee_id": e.users["roads_worker"]["id"], "instructions": "fix"}).json()["id"]
    e.client.post(f"/api/v1/work-orders/{wid}/start", headers=e.idem("roads_worker"))
    after = upload(e, "roads_worker", purpose="RESOLUTION")
    # a manager (staff) completes it: staff may complete without proof, and see the AI-4 review in the response
    r = e.client.post(f"/api/v1/work-orders/{wid}/complete", headers=e.idem("roads_mgr"), json={"notes": "Done", "resolution_evidence_ids": []})
    assert r.status_code == 200 and "resolution_review" in r.json()
    review = r.json()["resolution_review"]
    assert review is None or review["autonomous_closure_allowed"] is False                                       # flag-only, by contract
    assert e.client.get(f"/api/v1/cases/{case['id']}", headers=e.headers("admin")).json()["status"] == "AWAITING_VERIFICATION"   # the flags changed nothing
    detail = e.client.get(f"/api/v1/work-orders/{wid}", headers=e.headers("roads_mgr")).json()
    assert "resolution_review" in detail
    assert e.client.get(f"/api/v1/work-orders/{wid}", headers=e.headers("roads_worker")).json()["resolution_review"] is None
    assert after["status"] == "READY"


def test_triage_decision_that_differs_from_the_ai_is_audited_as_an_override(staffed):
    e = staffed
    case = create_case(e)
    rec, dec = triage_and_assign(e, case, priority="URGENT", severity="CRITICAL", sla_hours=4, reason="burst main nearby, escalate")
    assert dec["overridden"] is True and {"priority", "sla_hours"} & set(dec["overridden_fields"])
    with e.session_factory() as db:
        assert db.query(AuditEvent).filter(AuditEvent.action == "AI_RECOMMENDATION_OVERRIDDEN").count() == 1
        c = db.get(CivicCase, case["id"])
        assert c.priority == "URGENT" and c.severity == "CRITICAL" and c.sla_hours == 4 and c.triaged_at is not None and c.status == "ASSIGNED"


def test_triage_decision_is_idempotent_when_a_key_is_sent_and_respects_scope_and_state(staffed):
    e = staffed
    case = create_case(e)
    payload = {"severity": "HIGH", "priority": "HIGH", "department_id": "road_maintenance", "sla_hours": 24, "reason": "ok"}
    h = e.idem("roads_op", "decide-1")
    a = e.client.post(f"/api/v1/cases/{case['id']}/triage/decision", headers=h, json=payload)
    b = e.client.post(f"/api/v1/cases/{case['id']}/triage/decision", headers=h, json=payload)
    assert a.status_code == b.status_code == 200 and b.headers["idempotent-replayed"] == "true" and a.json()["recorded_at"] == b.json()["recorded_at"]
    with e.session_factory() as db:
        assert db.query(CaseEvent).filter(CaseEvent.case_id == case["id"], CaseEvent.event_type == "TRIAGE_DECIDED").count() == 1
    # the water operator cannot triage a roads case (object-level authorization also guards the AI endpoints)
    other = create_case(e)
    assert e.client.post(f"/api/v1/cases/{other['id']}/triage/decision", headers=e.idem("water_op"), json=payload).status_code == 404
    assert e.client.post(f"/api/v1/cases/{other['id']}/triage/analyze", headers=e.headers("water_op")).status_code == 404
    assert e.client.post(f"/api/v1/cases/{other['id']}/fusion/analyze", headers=e.headers("water_op")).status_code == 404
    assert e.client.post(f"/api/v1/cases/{other['id']}/triage/decision", headers=e.idem("alice"), json=payload).status_code == 403             # citizens cannot triage
    # an in-progress case can no longer be triaged
    with e.session_factory() as db:
        db.get(CivicCase, other["id"]).status = "IN_PROGRESS"
        db.commit()
    late = e.client.post(f"/api/v1/cases/{other['id']}/triage/decision", headers=e.idem("roads_op"), json=payload)
    assert late.status_code == 409 and late.json()["error"]["code"] == "INVALID_STATE"
    unknown = e.client.post(f"/api/v1/cases/{case['id']}/triage/decision", headers=e.idem("roads_op"), json={**payload, "department_id": "no_such"})
    assert unknown.json()["error"]["code"] == "DEPARTMENT_UNKNOWN"


def test_work_order_rules(staffed):
    e = staffed
    case = create_case(e)
    w = e.users["roads_worker"]["id"]
    body = {"assignee_id": w, "instructions": "fix it"}
    assert e.client.post(f"/api/v1/cases/{case['id']}/work-orders", headers=e.idem("roads_op"), json=body).status_code == 409        # not triaged yet
    triage_and_assign(e, case)
    assert e.client.post(f"/api/v1/cases/{case['id']}/work-orders", headers=e.idem("alice"), json=body).status_code == 403
    wrong_dept = e.client.post(f"/api/v1/cases/{case['id']}/work-orders", headers=e.idem("roads_op"), json={**body, "assignee_id": e.users["water_worker"]["id"]})
    assert wrong_dept.status_code == 422 and wrong_dept.json()["error"]["code"] == "ASSIGNEE_WRONG_DEPARTMENT"
    not_worker = e.client.post(f"/api/v1/cases/{case['id']}/work-orders", headers=e.idem("roads_op"), json={**body, "assignee_id": e.users["alice"]["id"]})
    assert not_worker.json()["error"]["code"] == "ASSIGNEE_INVALID"
    ok = e.client.post(f"/api/v1/cases/{case['id']}/work-orders", headers=e.idem("roads_op"), json=body)
    assert ok.status_code == 201
    wid = ok.json()["id"]
    assert e.client.post(f"/api/v1/cases/{case['id']}/work-orders", headers=e.idem("roads_op"), json=body).status_code == 409      # one active order per case
    # reassign before work starts, edit instructions, then cancel: the case returns to ASSIGNED
    assert e.client.patch(f"/api/v1/work-orders/{wid}", headers=e.idem("roads_op"), json={"instructions": "fix it today"}).json()["instructions"] == "fix it today"
    assert e.client.patch(f"/api/v1/work-orders/{wid}", headers=e.idem("roads_worker"), json={"instructions": "x"}).status_code == 403
    # another worker may not start someone else's order
    e.make_user("field_worker", "roads_worker2", department_id="road_maintenance")
    assert e.client.post(f"/api/v1/work-orders/{wid}/start", headers=e.idem("roads_worker2")).status_code == 404
    c = e.client.post(f"/api/v1/work-orders/{wid}/cancel", headers=e.idem("roads_op"), json={"reason": "assigned to the wrong crew"})
    assert c.status_code == 200 and c.json()["status"] == "CANCELLED"
    assert e.client.get(f"/api/v1/cases/{case['id']}", headers=e.headers("roads_op")).json()["status"] == "ASSIGNED"
    again = e.client.post(f"/api/v1/cases/{case['id']}/work-orders", headers=e.idem("roads_op"), json={"assignee_id": e.users["roads_worker2"]["id"], "instructions": "retry"})
    assert again.status_code == 201
    with e.session_factory() as db:
        assert db.query(WorkOrder).filter(WorkOrder.case_id == case["id"]).count() == 2


def test_verification_policy_reopens_escalates_or_asks_staff(staffed):
    e = staffed
    def awaiting(who="alice"):
        case = create_case(e, who)
        triage_and_assign(e, case, priority="NORMAL", severity="MEDIUM")
        wid = e.client.post(f"/api/v1/cases/{case['id']}/work-orders", headers=e.idem("roads_op"), json={"assignee_id": e.users["roads_worker"]["id"], "instructions": "fix"}).json()["id"]
        e.client.post(f"/api/v1/work-orders/{wid}/start", headers=e.idem("roads_worker"))
        ev = upload(e, "roads_worker", purpose="RESOLUTION")
        assert e.client.post(f"/api/v1/work-orders/{wid}/complete", headers=e.idem("roads_worker"), json={"notes": "x", "resolution_evidence_ids": [ev["id"]]}).status_code == 200
        return case
    c1 = awaiting()
    r = e.client.post(f"/api/v1/cases/{c1['id']}/verification", headers=e.idem("alice"), json={"result": "STILL_OCCURRING", "comment": "water is back on the road"}).json()
    assert r["case_status"] == "REOPENED" and r["reopened"] is True
    with e.session_factory() as db:
        c = db.get(CivicCase, c1["id"])
        assert c.status == "REOPENED" and c.reopen_count == 1 and c.priority == "HIGH" and c.closed_at is None          # escalated NORMAL -> HIGH
        assert db.query(AuditEvent).filter(AuditEvent.action == "CASE_REOPENED").count() == 1
    again = e.client.post(f"/api/v1/cases/{c1['id']}/work-orders", headers=e.idem("roads_op"), json={"assignee_id": e.users["roads_worker"]["id"], "instructions": "redo"})
    assert again.status_code == 201                                                                                     # a reopened case gets a new work order

    c2 = awaiting()
    r = e.client.post(f"/api/v1/cases/{c2['id']}/verification", headers=e.idem("alice"), json={"result": "PARTIAL"}).json()
    assert r["case_status"] == "AWAITING_VERIFICATION" and r["reopened"] is False                                       # a human decides
    r = e.client.post(f"/api/v1/cases/{c2['id']}/verification", headers=e.idem("alice"), json={"result": "NO"}).json()
    assert r["case_status"] == "REOPENED"
    with e.session_factory() as db:
        assert db.get(CivicCase, c2["id"]).priority == "NORMAL"                                                          # NO reopens without escalating
        # the department operator was told about the partial fix and the reopening
        assert db.query(Notification).filter(Notification.user_id == e.users["roads_op"]["id"]).count() >= 2

    c3 = awaiting()
    assert e.client.post(f"/api/v1/cases/{c3['id']}/verification", headers=e.idem("overlooker"), json={"result": "YES"}).status_code == 403
    e.make_user("citizen", "dave")
    assert e.client.post(f"/api/v1/cases/{c3['id']}/verification", headers=e.idem("dave"), json={"result": "YES"}).status_code == 404
    e.client.post(f"/api/v1/cases/{c3['id']}/support", headers=e.idem("dave"))
    assert e.client.post(f"/api/v1/cases/{c3['id']}/verification", headers=e.idem("dave"), json={"result": "YES"}).status_code == 403       # a supporter may not verify
    e.client.post(f"/api/v1/cases/{c3['id']}/contributors", headers=e.idem("alice"), json={"user_id": e.users["dave"]["id"]})
    ok = e.client.post(f"/api/v1/cases/{c3['id']}/verification", headers=e.idem("dave"), json={"result": "YES"})
    assert ok.status_code == 201 and ok.json()["case_status"] == "RESOLVED"                                             # a contributor may


def test_fusion_finds_a_nearby_duplicate_and_the_async_job_stores_the_relation(staffed):
    from backend.services.ai_jobs import run_job
    e = staffed
    first = create_case(e, "alice", description="Huge pothole outside the school gate, two bikes fell")
    dup = create_case(e, "bob", description="big pothole at the school gate, bikes keep falling")
    far = create_case(e, "bob", description="pothole far away", location={"latitude": e.where["latitude"] + 0.2, "longitude": e.where["longitude"]})
    res = e.client.post(f"/api/v1/cases/{dup['id']}/fusion/analyze", headers=e.headers("roads_op")).json()
    assert [m["case_id"] for m in res["matches"]] == [first["id"]] and far["id"] not in [m["case_id"] for m in res["matches"]]
    assert set(res["matches"][0]["signals"]) >= {"semantic", "geospatial", "temporal"}
    outcome = run_job("fusion", dup["id"])
    assert outcome.startswith("fusion")
    assert run_job("fusion", "not-a-case").startswith("skipped")
    assert run_job("bogus", dup["id"]).startswith("skipped")
    with e.session_factory() as db:
        rels = db.query(CaseRelation).all()
        assert all({r.case_a, r.case_b} == {dup["id"], first["id"]} for r in rels)
    assert run_job("triage", first["id"]) == "triage stored"
    with e.session_factory() as db:
        assert db.query(AIAnalysis).filter(AIAnalysis.case_id == first["id"], AIAnalysis.task_type == "triage").count() == 1
