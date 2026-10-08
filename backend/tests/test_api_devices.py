"""POST/GET/DELETE /me/devices (Expo push tokens) and the PENDING marking of new notifications. The router is mounted on a private app here (the real mount is one line
in backend/api/v1/router.py), with the same error handlers as backend.main."""
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

TOKEN = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaaa]"
TOKEN2 = "ExponentPushToken[bbbbbbbbbbbbbbbbbbbbbb]"
URL = "/api/v1/me/devices"
ROLES = [("citizen", "alice"), ("field_worker", "w"), ("operator", "op"), ("ward_officer", "wo"), ("department_manager", "mgr"), ("city_admin", "admin")]


@pytest.fixture
def api(env):
    from backend.api.v1 import devices
    from backend.core.exceptions import (
        CivicConnectException,
        civicconnect_exception_handler,
        http_exception_handler,
        unhandled_exception_handler,
        validation_exception_handler,
    )
    app = FastAPI()
    app.include_router(devices.router, prefix="/api/v1/me")
    app.add_exception_handler(CivicConnectException, civicconnect_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    env.make_user("citizen", "alice")
    env.make_user("citizen", "bob")
    env.client = TestClient(app, raise_server_exceptions=False)
    return env


def body(token=TOKEN, **kw):
    return {"platform": "android", "expo_push_token": token, **kw}


def test_register_creates_then_upserts_the_same_row_and_never_returns_the_token(api):
    r = api.client.post(URL, json=body(device_id="d1", locale="mr"), headers=api.headers("alice"))
    assert r.status_code == 201
    d = r.json()
    assert d["platform"] == "android" and d["device_id"] == "d1" and d["locale"] == "mr" and d["revoked_at"] is None and "expo_push_token" not in d and TOKEN not in r.text
    again = api.client.post(URL, json=body(device_id="d2", platform="ios"), headers=api.headers("alice"))
    assert again.status_code == 200 and again.json()["id"] == d["id"]
    a = again.json()
    assert a["device_id"] == "d2" and a["platform"] == "ios" and a["locale"] == "mr" and a["last_seen_at"] >= d["last_seen_at"]      # locale kept when omitted
    assert len(api.client.get(URL, headers=api.headers("alice")).json()) == 1


@pytest.mark.parametrize("role,key", ROLES)
def test_every_signed_in_role_can_register_list_and_revoke(api, role, key):
    if key not in api.users:
        api.make_user(role, key)
    r = api.client.post(URL, json=body(), headers=api.headers(key))
    assert r.status_code == 201
    assert [d["id"] for d in api.client.get(URL, headers=api.headers(key)).json()] == [r.json()["id"]]
    assert api.client.delete(f"{URL}/{r.json()['id']}", headers=api.headers(key)).status_code == 200
    assert api.client.get(URL, headers=api.headers(key)).json() == []


def test_unauthenticated_and_validation_errors(api):
    assert api.client.post(URL, json=body()).status_code == 401
    assert api.client.get(URL).status_code == 401
    assert api.client.delete(f"{URL}/x").status_code == 401
    h = api.headers("alice")
    for bad in ({"platform": "android", "expo_push_token": "not-a-token"}, {"platform": "symbian", "expo_push_token": TOKEN}, {"expo_push_token": TOKEN}, {}):
        r = api.client.post(URL, json=bad, headers=h)
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_token_held_by_another_user_is_rebound_to_the_caller(api):
    first = api.client.post(URL, json=body(device_id="old"), headers=api.headers("alice")).json()
    moved = api.client.post(URL, json=body(device_id="new"), headers=api.headers("bob"))
    assert moved.status_code == 200 and moved.json()["id"] == first["id"] and moved.json()["device_id"] == "new"
    assert api.client.get(URL, headers=api.headers("alice")).json() == []                       # the previous binding is gone
    assert [d["id"] for d in api.client.get(URL, headers=api.headers("bob")).json()] == [first["id"]]
    assert api.client.delete(f"{URL}/{first['id']}", headers=api.headers("alice")).status_code == 404       # alice no longer owns it
    from backend.models import AuditEvent
    with api.session_factory() as db:
        acts = [a.action for a in db.query(AuditEvent).filter(AuditEvent.entity_type == "device_token").order_by(AuditEvent.created_at)]
    assert "device.registered" in acts and "device.rebound" in acts


def test_revoke_is_owner_only_and_idempotent_and_register_revives(api):
    d = api.client.post(URL, json=body(), headers=api.headers("alice")).json()
    assert api.client.delete(f"{URL}/{d['id']}", headers=api.headers("bob")).status_code == 404
    miss = api.client.delete(f"{URL}/nope", headers=api.headers("alice"))
    assert miss.status_code == 404 and miss.json()["error"]["code"] == "DEVICE_NOT_FOUND"
    assert api.client.get(URL, headers=api.headers("alice")).json()[0]["revoked_at"] is None        # bob's attempt changed nothing
    one = api.client.delete(f"{URL}/{d['id']}", headers=api.headers("alice"))
    two = api.client.delete(f"{URL}/{d['id']}", headers=api.headers("alice"))
    assert one.status_code == two.status_code == 200 and one.json()["revoked_at"] and two.json()["revoked_at"] == one.json()["revoked_at"]
    assert api.client.get(URL, headers=api.headers("alice")).json() == []
    assert len(api.client.get(URL, params={"include_revoked": "true"}, headers=api.headers("alice")).json()) == 1
    back = api.client.post(URL, json=body(), headers=api.headers("alice"))
    assert back.status_code == 200 and back.json()["id"] == d["id"] and back.json()["revoked_at"] is None


def test_audit_rows_never_hold_a_token(api):
    d = api.client.post(URL, json=body(), headers=api.headers("alice")).json()
    api.client.delete(f"{URL}/{d['id']}", headers=api.headers("alice"))
    from backend.models import AuditEvent
    with api.session_factory() as db:
        rows = db.query(AuditEvent).filter(AuditEvent.entity_type == "device_token").all()
    assert {r.action for r in rows} == {"device.registered", "device.revoked"}
    assert all(TOKEN not in str((r.before_json, r.after_json)) and "Expo" not in str((r.before_json, r.after_json)) for r in rows)


# ------------------------------------------------------------------------------------------------ marking of new notifications
def _notify(api, key="alice"):
    from backend.services.notifications import notify
    with api.session_factory() as db:
        out = notify(db, [api.users[key]["id"]], "CASE_UPDATED", {"case_id": "c1", "title": "T", "message": "M"})
        db.commit()
        return out[0].push_status


def test_notify_marks_pending_only_for_users_with_an_active_token(api):
    assert _notify(api) == "NONE"                                                               # no token
    api.client.post(URL, json=body(), headers=api.headers("alice"))
    assert _notify(api) == "PENDING"
    assert _notify(api, "bob") == "NONE"                                                        # bob has none
    d = api.client.get(URL, headers=api.headers("alice")).json()[0]
    api.client.delete(f"{URL}/{d['id']}", headers=api.headers("alice"))
    assert _notify(api) == "NONE"                                                               # revoked


def test_notify_leaves_none_when_the_push_policy_is_off(api):
    from backend.models import SystemSetting
    api.client.post(URL, json=body(), headers=api.headers("alice"))
    with api.session_factory() as db:
        db.add(SystemSetting(key="notification_policy", value_json={"email": False, "sms": False, "push": False, "escalation_emails": False}))
        db.commit()
    assert _notify(api) == "NONE"


def test_a_failure_while_marking_never_breaks_the_notification_write(api, monkeypatch):
    from backend.models import Notification
    from backend.services import push
    api.client.post(URL, json=body(), headers=api.headers("alice"))
    monkeypatch.setattr(push, "push_enabled", lambda db: (_ for _ in ()).throw(RuntimeError("boom")))
    assert _notify(api) == "NONE"
    monkeypatch.setattr(push, "mark_pending", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert _notify(api) == "NONE"
    with api.session_factory() as db:
        assert db.query(Notification).count() == 2


# ------------------------------------------------------------------------------------------------ token cap and list bound
def test_registering_over_the_cap_revokes_the_least_recently_seen_token_with_an_audit_row(api, monkeypatch):
    from backend.core.config import settings
    from backend.models import AuditEvent
    monkeypatch.setattr(settings, "PUSH_MAX_DEVICES_PER_USER", 3)
    h = api.headers("alice")
    ids = [api.client.post(URL, json=body(f"ExponentPushToken[{c * 22}]"), headers=h).json()["id"] for c in "abc"]
    assert len(api.client.get(URL, headers=h).json()) == 3
    api.client.post(URL, json=body(f"ExponentPushToken[{'a' * 22}]"), headers=h)               # a is seen again: b is now the oldest
    d = api.client.post(URL, json=body(f"ExponentPushToken[{'d' * 22}]"), headers=h).json()
    active = {x["id"] for x in api.client.get(URL, headers=h).json()}
    assert active == {ids[0], ids[2], d["id"]}
    with api.session_factory() as db:
        rows = db.query(AuditEvent).filter(AuditEvent.action == "device.revoked").all()
    assert [(r.entity_id, r.after_json["reason"]) for r in rows] == [(ids[1], "limit")]
    assert api.client.post(URL, json=body(f"ExponentPushToken[{'d' * 22}]"), headers=h).status_code == 200      # a refresh at the cap revokes nothing
    assert len(api.client.get(URL, headers=h).json()) == 3
    # a token that moves in from another account counts against the new owner's cap too
    api.client.post(URL, json=body(f"ExponentPushToken[{'z' * 22}]"), headers=api.headers("bob"))
    api.client.post(URL, json=body(f"ExponentPushToken[{'z' * 22}]"), headers=h)
    assert len(api.client.get(URL, headers=h).json()) == 3 and api.client.get(URL, headers=api.headers("bob")).json() == []


def test_the_device_list_returns_at_most_the_50_newest(api):
    from datetime import datetime, timedelta, timezone

    from backend.models import DeviceToken
    now = datetime.now(timezone.utc)
    with api.session_factory() as db:
        db.add_all(DeviceToken(user_id=api.users["alice"]["id"], platform="ios", expo_push_token=f"ExponentPushToken[{i:022d}]", created_at=now - timedelta(minutes=i), revoked_at=now)
                   for i in range(60))
        db.commit()
    got = api.client.get(URL, params={"include_revoked": "true"}, headers=api.headers("alice")).json()
    assert len(got) == 50 and got[0]["created_at"] > got[-1]["created_at"]


def test_inactive_users_get_no_pending_mark(api):
    from backend.models import User
    api.client.post(URL, json=body(), headers=api.headers("alice"))
    with api.session_factory() as db:
        db.get(User, api.users["alice"]["id"]).is_active = False
        db.commit()
    assert _notify(api) == "NONE"
