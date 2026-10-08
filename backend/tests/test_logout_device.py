"""POST /auth/logout with the optional ``expo_push_token``: revokes that device of the refresh token's owner (and only theirs), audited without the token; the answer never changes."""
import json

import pytest

from backend.models import AuditEvent, DeviceToken

API = "/api/v1"
LOGOUT = f"{API}/auth/logout"
TOKEN = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaaa]"
TOKEN2 = "ExponentPushToken[bbbbbbbbbbbbbbbbbbbbbb]"
OTHER = "ExponentPushToken[cccccccccccccccccccccc]"


def login(e, key, password):
    return e.client.post(f"{API}/auth/login", json={"identifier": e.users[key]["email"], "password": password}).json()


def register_device(e, key, token):
    r = e.client.post(f"{API}/me/devices", json={"platform": "android", "expo_push_token": token}, headers=e.headers(key))
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def device(e, token):
    with e.session_factory() as db:
        d = db.query(DeviceToken).filter(DeviceToken.expo_push_token == token).one()
        return d.user_id, d.revoked_at


def audits(e):
    with e.session_factory() as db:
        return [(a.actor_id, a.entity_id, a.before_json, a.after_json) for a in db.query(AuditEvent).filter(AuditEvent.action == "device.revoked")]


def refresh_works(e, s):
    return e.client.post(f"{API}/auth/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 200


def test_logout_with_token_revokes_the_owners_device_and_the_refresh_token(staffed, password):
    e = staffed
    s = login(e, "alice", password)
    did = register_device(e, "alice", TOKEN)
    other = register_device(e, "alice", TOKEN2)
    r = e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"], "expo_push_token": TOKEN})
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    uid, revoked = device(e, TOKEN)
    assert uid == e.users["alice"]["id"] and revoked is not None
    assert device(e, TOKEN2)[1] is None                                                  # her other device stays
    assert e.client.post(f"{API}/auth/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401
    assert [d["id"] for d in e.client.get(f"{API}/me/devices", headers=e.headers("alice")).json()] == [other]      # the list (and push selection) no longer has it
    ((actor, entity, before, after),) = audits(e)
    assert actor == e.users["alice"]["id"] and entity == did and before == {"revoked": False} and after == {"revoked": True, "reason": "logout"}
    assert TOKEN not in json.dumps([before, after]) and e.client.delete(f"{API}/me/devices/{did}", headers=e.headers("alice")).status_code == 200      # DELETE still works (idempotent)
    assert len(audits(e)) == 1


def test_push_selection_ignores_the_revoked_device(staffed, password):
    from backend.services import push
    e = staffed
    s = login(e, "alice", password)
    register_device(e, "alice", TOKEN)
    with e.session_factory() as db:
        assert [t.expo_push_token for t in push._active_tokens(db, [e.users["alice"]["id"]])[e.users["alice"]["id"]]] == [TOKEN]
    assert e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"], "expo_push_token": TOKEN}).status_code == 200
    with e.session_factory() as db:
        assert push._active_tokens(db, [e.users["alice"]["id"]]) == {}


def test_a_token_bound_to_another_user_is_left_alone_and_nothing_is_revealed(staffed, password):
    e = staffed
    s = login(e, "alice", password)
    register_device(e, "bob", TOKEN)
    r = e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"], "expo_push_token": TOKEN})
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert device(e, TOKEN) == (e.users["bob"]["id"], None) and audits(e) == []
    assert not refresh_works(e, s)                                                       # the refresh token is revoked regardless
    ok = e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"], "expo_push_token": TOKEN2})
    assert ok.status_code == 200 and ok.json() == {"status": "ok"}                       # same answer for an unknown token (and a refresh token already revoked)


def test_unknown_token_and_already_revoked_device_change_nothing(staffed, password):
    e = staffed
    s = login(e, "alice", password)
    did = register_device(e, "alice", TOKEN)
    assert e.client.delete(f"{API}/me/devices/{did}", headers=e.headers("alice")).status_code == 200
    first = device(e, TOKEN)[1]
    assert len(audits(e)) == 1
    r = e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"], "expo_push_token": TOKEN})
    assert r.status_code == 200 and r.json() == {"status": "ok"} and device(e, TOKEN)[1] == first and len(audits(e)) == 1
    s2 = login(e, "alice", password)
    r = e.client.post(LOGOUT, json={"refresh_token": s2["refresh_token"], "expo_push_token": OTHER})
    assert r.status_code == 200 and r.json() == {"status": "ok"} and not refresh_works(e, s2)      # unknown: refresh token revoked, no new audit
    assert len(audits(e)) == 1


@pytest.mark.parametrize("bad", ["not-a-token", "ExponentPushToken[]", "ExpoPushToken", "x" * 300, "", "ExponentPushToken[" + "a" * 260 + "]"])
def test_invalid_token_format_is_a_422_and_revokes_nothing(staffed, password, bad):
    e = staffed
    s = login(e, "alice", password)
    register_device(e, "alice", TOKEN)
    r = e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"], "expo_push_token": bad})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert device(e, TOKEN)[1] is None and refresh_works(e, s)                           # nothing happened: the refresh token still works


def test_without_a_token_logout_is_unchanged_and_both_token_formats_are_accepted(staffed, password):
    e = staffed
    s = login(e, "alice", password)
    register_device(e, "alice", TOKEN)
    r = e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"]})
    assert r.status_code == 200 and r.json() == {"status": "ok"} and device(e, TOKEN)[1] is None and audits(e) == []
    assert not refresh_works(e, s)
    s2 = login(e, "alice", password)
    assert e.client.post(LOGOUT, json={"refresh_token": s2["refresh_token"], "expo_push_token": None}).status_code == 200 and device(e, TOKEN)[1] is None
    legacy = "ExpoPushToken[dddddddddddddddddddddd]"
    s3 = login(e, "alice", password)
    register_device(e, "alice", legacy)
    assert e.client.post(LOGOUT, json={"refresh_token": s3["refresh_token"], "expo_push_token": legacy}).status_code == 200 and device(e, legacy)[1] is not None


def test_a_bad_refresh_token_behaves_as_before_and_revokes_no_device(staffed, password):
    e = staffed
    login(e, "alice", password)
    register_device(e, "alice", TOKEN)
    r = e.client.post(LOGOUT, json={"refresh_token": "x" * 40, "expo_push_token": TOKEN})
    assert r.status_code == 200 and r.json() == {"status": "ok"} and device(e, TOKEN)[1] is None and audits(e) == []      # unknown refresh token: no owner, nothing to act on
    assert e.client.post(LOGOUT, json={"refresh_token": "short", "expo_push_token": TOKEN}).status_code == 422                # RefreshIn validation as before
    assert e.client.post(LOGOUT, json={"expo_push_token": TOKEN}).status_code == 422
    assert e.client.post(f"{API}/auth/refresh", json={"refresh_token": "x" * 40, "expo_push_token": TOKEN}).status_code == 401      # /refresh ignores the extra field


def test_a_revoked_refresh_token_cannot_be_used_to_revoke_a_device(staffed, password):
    e = staffed
    s = login(e, "alice", password)
    register_device(e, "alice", TOKEN)
    assert e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"]}).status_code == 200
    r = e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"], "expo_push_token": TOKEN})
    assert r.status_code == 200 and device(e, TOKEN)[1] is None and audits(e) == []


@pytest.mark.parametrize("key", ["alice", "roads_worker", "roads_op", "ward_officer", "roads_mgr", "admin", "overlooker"])
def test_every_role_can_log_out_its_device(staffed, password, key):
    e = staffed
    s = login(e, key, password)
    register_device(e, key, TOKEN)
    assert e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"], "expo_push_token": TOKEN}).status_code == 200
    assert device(e, TOKEN)[1] is not None


def test_logout_works_while_a_password_change_is_forced(staffed, password):
    from backend.models import User
    e = staffed
    s = login(e, "roads_op", password)
    register_device(e, "roads_op", TOKEN)
    with e.session_factory() as db:
        db.get(User, e.users["roads_op"]["id"]).must_change_password = True
        db.commit()
    assert e.client.post(LOGOUT, json={"refresh_token": s["refresh_token"], "expo_push_token": TOKEN}).status_code == 200 and device(e, TOKEN)[1] is not None
