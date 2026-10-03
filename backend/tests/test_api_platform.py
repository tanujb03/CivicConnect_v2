"""Evidence protocol, map, analytics, incidents, offline sync and the §51A contract surface."""
import hashlib
import json
import uuid

from backend.storage import sign_blob_token, verify_blob_token
from backend.tests.helpers import JPEG, WAV, case_body, create_case, upload


# ------------------------------------------------------------------------------------------------ evidence (§51A.6, §44)
def init(e, who, **kw):
    data = kw.pop("data", JPEG)
    body = {"filename": "p.jpg", "mime_type": "image/jpeg", "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), **kw}
    return e.client.post("/api/v1/evidence/upload-init", headers=e.idem(who), json=body)


def test_upload_init_rejects_unsafe_files(staffed):
    e = staffed
    assert init(e, "alice", mime_type="application/x-msdownload", filename="a.exe").status_code == 415
    assert init(e, "alice", filename="photo.exe").status_code == 415                      # extension must match the type
    assert init(e, "alice", size_bytes=10**9).status_code == 413
    assert init(e, "alice", sha256="zz").status_code == 422
    assert init(e, "overlooker").status_code == 403
    r = init(e, "alice")
    assert r.status_code == 201 and "/evidence/blob/" in r.json()["upload_url"] and r.json()["expires_at"]


def test_complete_validates_size_checksum_and_content(staffed):
    e = staffed
    # not uploaded yet
    pending = init(e, "alice").json()
    assert e.client.post(f"/api/v1/evidence/{pending['evidence_id']}/complete", headers=e.headers("alice")).json()["error"]["code"] == "UPLOAD_INCOMPLETE"
    # wrong bytes (checksum) -> rejected for good
    bad = init(e, "alice").json()
    path = bad["upload_url"].split("localhost:8000")[1]
    assert e.client.put(path, content=JPEG + b"tampered", headers={"Content-Type": "image/jpeg"}).status_code == 204
    r = e.client.post(f"/api/v1/evidence/{bad['evidence_id']}/complete", headers=e.headers("alice"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "EVIDENCE_REJECTED"
    # a "jpeg" that is not a jpeg
    fake = b"MZ this is an executable pretending to be a photo" * 3
    f = init(e, "alice", data=fake).json()
    e.client.put(f["upload_url"].split("localhost:8000")[1], content=fake, headers={"Content-Type": "image/jpeg"})
    assert e.client.post(f"/api/v1/evidence/{f['evidence_id']}/complete", headers=e.headers("alice")).json()["error"]["code"] == "EVIDENCE_REJECTED"
    # only the uploader completes; the happy path is idempotent
    ok = upload(e, "alice")
    assert e.client.post(f"/api/v1/evidence/{ok['id']}/complete", headers=e.headers("alice")).json()["status"] == "READY"
    assert e.client.post(f"/api/v1/evidence/{ok['id']}/complete", headers=e.headers("bob")).status_code == 404
    audio = upload(e, "alice", data=WAV, mime="audio/wav", name="voice.wav")
    assert audio["media_type"] == "AUDIO"


def test_signed_urls_expire_and_cannot_be_forged(staffed):
    e = staffed
    tok = sign_blob_token("evidence/x.jpg", "PUT", 60, "image/jpeg", now=1000)
    assert verify_blob_token(tok, "PUT", now=1030) and verify_blob_token(tok, "PUT", now=1100) is None and verify_blob_token(tok, "GET", now=1030) is None
    assert verify_blob_token(tok[:-3] + "AAA", "PUT", now=1030) is None
    assert e.client.put("/api/v1/evidence/blob/garbage", content=b"x").status_code == 403
    ev = upload(e, "alice")
    meta = e.client.get(f"/api/v1/evidence/{ev['id']}", headers=e.headers("alice")).json()
    got = e.client.get(meta["download_url"].split("localhost:8000")[1])
    assert got.status_code == 200 and got.content == JPEG and got.headers["x-content-type-options"] == "nosniff"


def test_evidence_visibility(staffed):
    e = staffed
    ev = upload(e, "alice")
    assert e.client.get(f"/api/v1/evidence/{ev['id']}", headers=e.headers("bob")).status_code == 404            # not yours, no case yet
    case = create_case(e, "alice", evidence_ids=[ev["id"]])
    assert e.client.get(f"/api/v1/evidence/{ev['id']}", headers=e.headers("roads_op")).status_code == 200      # department staff via the case
    assert e.client.get(f"/api/v1/evidence/{ev['id']}", headers=e.headers("water_op")).status_code == 404
    e.client.post(f"/api/v1/cases/{case['id']}/support", headers=e.idem("bob"))
    assert e.client.get(f"/api/v1/evidence/{ev['id']}", headers=e.headers("bob")).status_code == 404           # a supporter never sees someone else's photo


def test_direct_multipart_upload_runs_the_same_checks(staffed):
    e = staffed
    r = e.client.post("/api/v1/evidence", headers=e.headers("alice"), files={"file": ("a.jpg", JPEG, "image/jpeg")})
    assert r.status_code == 201 and r.json()["status"] == "READY"
    bad = e.client.post("/api/v1/evidence", headers=e.headers("alice"), files={"file": ("a.jpg", b"not a jpeg at all", "image/jpeg")})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "EVIDENCE_REJECTED"


# ------------------------------------------------------------------------------------------------ map / analytics
def test_map_markers_are_scoped_and_privacy_preserving(staffed):
    e = staffed
    c = create_case(e, "alice")
    lat, lon = e.where["latitude"], e.where["longitude"]
    bbox = f"{lon - 0.01},{lat - 0.01},{lon + 0.01},{lat + 0.01}"
    staff = e.client.get(f"/api/v1/map/cases?bbox={bbox}", headers=e.headers("roads_op")).json()["items"]
    assert [m["id"] for m in staff] == [c["id"]] and staff[0]["location"]["latitude"] == lat
    citizen = e.client.get(f"/api/v1/map/cases?bbox={bbox}", headers=e.headers("bob")).json()["items"]
    assert [m["id"] for m in citizen] == [c["id"]] and citizen[0]["location"]["latitude"] == round(lat, 4) and "title" not in citizen[0]
    assert e.client.get("/api/v1/map/cases?bbox=1,2,3", headers=e.headers("bob")).status_code == 422
    assert e.client.get(f"/api/v1/map/cases?bbox={bbox}", headers=e.headers("water_op")).json()["items"] == []
    assert e.client.get("/api/v1/map/hotspots", headers=e.headers("admin")).json() == {"items": []}
    assert e.client.get("/api/v1/map/recurring-problems", headers=e.headers("admin")).json() == {"items": []}
    assert e.client.get("/api/v1/map/cases").status_code == 401


def test_analytics_overview_matches_the_admin_client_contract(staffed):
    e = staffed
    create_case(e, "alice")
    create_case(e, "bob", category="water_supply", subcategory="no_water_supply", description="no water")
    ov = e.client.get("/api/v1/analytics/overview", headers=e.headers("admin")).json()
    assert {"open_cases", "critical_cases", "sla_at_risk", "unassigned", "awaiting_verification", "reopened", "median_resolution_hours", "category_distribution", "daily_trend"} <= set(ov)
    assert ov["open_cases"] == 2 and ov["unassigned"] == 2 and len(ov["daily_trend"]) == 30 and ov["daily_trend"][-1]["created"] == 2
    assert e.client.get("/api/v1/analytics/overview", headers=e.headers("roads_op")).json()["open_cases"] == 1          # department scope
    assert e.client.get("/api/v1/analytics/overview", headers=e.headers("overlooker")).json()["open_cases"] == 2          # city aggregates
    limited = e.client.get("/api/v1/analytics/overview", headers=e.headers("alice"))
    assert limited.status_code == 403                                                                                      # citizens: no city analytics
    assert [d["department_id"] for d in e.client.get("/api/v1/analytics/departments", headers=e.headers("admin")).json()["items"]] == ["road_maintenance", "water_supply"]
    assert e.client.get("/api/v1/analytics/departments/nope", headers=e.headers("admin")).status_code == 404


# ------------------------------------------------------------------------------------------------ incidents
def test_incident_lifecycle_and_permissions(staffed):
    e = staffed
    a, b = create_case(e, "alice"), create_case(e, "bob")
    lat, lon = e.where["latitude"], e.where["longitude"]
    ring = [[lon - .01, lat - .01], [lon + .01, lat - .01], [lon + .01, lat + .01], [lon - .01, lat + .01], [lon - .01, lat - .01]]
    body = {"title": "Burst main on Station Road", "description": "water on the road", "category": "water_supply", "boundary": {"type": "Polygon", "coordinates": [ring]}, "case_ids": [a["id"]]}
    assert e.client.post("/api/v1/incidents", headers=e.idem("roads_op"), json=body).status_code == 403                  # operators cannot open incidents
    assert e.client.post("/api/v1/incidents", headers=e.idem("admin"), json={**body, "boundary": {"type": "Nope"}}).status_code == 422
    r = e.client.post("/api/v1/incidents", headers=e.idem("ward_officer"), json=body)
    assert r.status_code == 201 and r.json()["case_count"] == 1 and r.json()["ward_id"] == e.ward_id
    iid = r.json()["id"]
    assert e.client.post(f"/api/v1/incidents/{iid}/cases", headers=e.idem("ward_officer"), json={"case_id": b["id"]}).json()["added"] is True
    assert e.client.post(f"/api/v1/incidents/{iid}/cases", headers=e.idem("ward_officer"), json={"case_id": b["id"]}).json()["added"] is False
    d = e.client.get(f"/api/v1/incidents/{iid}", headers=e.headers("admin")).json()
    assert set(d["case_ids"]) == {a["id"], b["id"]} and d["timeline"][0]["event_type"] == "INCIDENT_CREATED" and d["boundary"]["type"] == "Polygon"
    ov = e.client.get(f"/api/v1/incidents/{iid}", headers=e.headers("overlooker")).json()
    assert ov["case_ids"] == [] and ov["case_count"] == 2                                                                   # aggregates only
    assert e.client.get(f"/api/v1/incidents/{iid}", headers=e.headers("alice")).status_code == 403
    assert any(n["type"] == "INCIDENT_CREATED" for n in e.client.get("/api/v1/me/notifications", headers=e.headers("alice")).json()["items"])
    assert e.client.get("/api/v1/analytics/incidents", headers=e.headers("overlooker")).json()["items"][0]["case_count"] == 2
    assert e.client.patch(f"/api/v1/incidents/{iid}", headers=e.idem("admin"), json={"status": "ENDED"}).json()["status"] == "ENDED"
    assert e.client.post(f"/api/v1/incidents/{iid}/cases", headers=e.idem("admin"), json={"case_id": a["id"]}).status_code == 409
    assert e.client.get("/api/v1/incidents/nope", headers=e.headers("admin")).status_code == 404


# ------------------------------------------------------------------------------------------------ offline sync (§51A.16)
def test_sync_batch_is_idempotent_ordered_and_reports_rejections(staffed):
    e = staffed
    k1, k2, k3 = (str(uuid.uuid4()) for _ in range(3))
    batch = {"device_id": "dev-1", "mutations": [
        {"idempotency_key": k1, "client_timestamp": "2026-10-03T08:00:00Z", "operation": "CREATE_CASE", "payload": case_body(e, client_case_id=k1)},
        {"idempotency_key": k2, "operation": "CREATE_CASE", "payload": {"location": e.where}},                                  # invalid: nothing to report
        {"idempotency_key": k3, "operation": "SUPPORT_CASE", "payload": {"case_id": "missing"}}]}
    first = e.client.post("/api/v1/sync/mutations", headers=e.headers("alice"), json=batch).json()
    assert [r["status"] for r in first["results"]] == ["APPLIED", "REJECTED", "REJECTED"] and first["results"][0]["server_resource_id"]
    assert first["results"][1]["error"]["code"] == "VALIDATION_ERROR" and first["results"][2]["error"]["code"] == "CASE_NOT_FOUND"
    retry = e.client.post("/api/v1/sync/mutations", headers=e.headers("alice"), json=batch).json()
    assert [r["status"] for r in retry["results"]] == ["ALREADY_APPLIED", "REJECTED", "REJECTED"]
    assert retry["results"][0]["server_resource_id"] == first["results"][0]["server_resource_id"]
    assert len(e.client.get("/api/v1/cases", headers=e.headers("alice")).json()["items"]) == 1               # the retry never created a second case
    clash = e.client.post("/api/v1/sync/mutations", headers=e.headers("alice"), json={"mutations": [{"idempotency_key": k1, "operation": "CREATE_CASE", "payload": case_body(e, description="other")}]}).json()
    assert clash["results"][0]["status"] == "REJECTED" and clash["results"][0]["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert e.client.post("/api/v1/sync/mutations", headers=e.headers("alice"), json={"mutations": []}).status_code == 422
    assert e.client.post("/api/v1/sync/mutations", json=batch).status_code == 401


def test_sync_changes_stream_is_cursor_based_and_scoped(staffed):
    e = staffed
    mine, other = create_case(e, "alice"), create_case(e, "bob")
    page = e.client.get("/api/v1/sync/changes?limit=2", headers=e.headers("alice")).json()
    assert page["has_more"] is True and len(page["changes"]) == 2
    rest = e.client.get(f"/api/v1/sync/changes?cursor={page['server_cursor']}&limit=50", headers=e.headers("alice")).json()
    assert rest["has_more"] is False and {c["case_id"] for c in page["changes"] + rest["changes"]} == {mine["id"]} and other["id"] not in rest["cases"]
    nothing = e.client.get(f"/api/v1/sync/changes?cursor={rest['server_cursor']}", headers=e.headers("alice")).json()
    assert nothing["changes"] == [] and nothing["server_cursor"] == rest["server_cursor"]
    assert e.client.get("/api/v1/sync/changes?cursor=@@@", headers=e.headers("alice")).json()["error"]["code"] == "INVALID_CURSOR"


# ------------------------------------------------------------------------------------------------ contract
SECTION_51A = [("post", "/auth/register"), ("post", "/auth/login"), ("post", "/auth/refresh"), ("get", "/auth/me"), ("get", "/me"), ("patch", "/me"), ("get", "/me/notifications"),
               ("post", "/me/notifications/{notification_id}/read"), ("post", "/cases"), ("get", "/cases/{case_id}"), ("get", "/cases"), ("patch", "/cases/{case_id}"),
               ("post", "/cases/{case_id}/contributors"), ("post", "/cases/intake/analyze"), ("post", "/evidence/upload-init"), ("post", "/evidence/{evidence_id}/complete"),
               ("get", "/evidence/{evidence_id}"), ("post", "/cases/{case_id}/fusion/analyze"), ("post", "/cases/{case_id}/triage/analyze"), ("post", "/cases/{case_id}/triage/decision"),
               ("post", "/cases/{case_id}/work-orders"), ("get", "/work-orders"), ("get", "/work-orders/{work_order_id}"), ("post", "/work-orders/{work_order_id}/start"),
               ("post", "/work-orders/{work_order_id}/complete"), ("post", "/cases/{case_id}/verification"), ("get", "/cases/{case_id}/timeline"), ("get", "/map/cases"),
               ("get", "/map/hotspots"), ("get", "/map/recurring-problems"), ("get", "/analytics/overview"), ("get", "/analytics/departments/{department_id}"),
               ("get", "/analytics/incidents"), ("post", "/incidents"), ("get", "/incidents/{incident_id}"), ("post", "/incidents/{incident_id}/cases"), ("post", "/copilot/query"),
               ("post", "/sync/mutations"), ("get", "/sync/changes"), ("get", "/health/live"), ("get", "/health/ready")]


def test_every_section_51a_endpoint_exists_in_the_openapi_document():
    from backend.main import app
    paths = app.openapi()["paths"]
    missing = [(m, p) for m, p in SECTION_51A if m not in paths.get(f"/api/v1{p}", {})]
    assert missing == []


def test_committed_openapi_json_is_current():
    """Regenerate with: python -m backend.scripts.generate_openapi"""
    from pathlib import Path

    from backend.main import app
    committed = json.loads((Path(__file__).resolve().parents[1] / "openapi.json").read_text(encoding="utf-8"))
    assert committed["paths"].keys() == app.openapi()["paths"].keys(), "backend/openapi.json is stale: run python -m backend.scripts.generate_openapi"


def test_health_endpoints_and_readiness(staffed):
    e = staffed
    assert e.client.get("/api/v1/health/live").json() == {"status": "ok"}
    r = e.client.get("/api/v1/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"] == "ok" and r.json()["checks"]["storage"] == "ok" and r.json()["status"] == "ready"
    assert "email" not in r.text


def test_unhandled_errors_never_leak_internals(staffed, monkeypatch):
    e = staffed
    from backend.services import analytics
    monkeypatch.setattr(analytics, "overview", lambda *a, **k: 1 / 0)
    r = e.client.get("/api/v1/analytics/overview", headers=e.headers("admin"))
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL_ERROR" and "division" not in r.text
