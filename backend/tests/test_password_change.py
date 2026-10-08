"""WP2 auth hardening: POST /auth/change-password, POST /admin/users/{id}/reset-password, the forced-change gate (403 PASSWORD_CHANGE_REQUIRED), audit rows without secrets."""
import json

import pytest

from backend.core.config import settings
from backend.models import AuditEvent, RefreshToken, User

API = "/api/v1"
CHANGE = f"{API}/auth/change-password"
NEW_PW = "a-brand-new-passphrase"


def login(e, key, password):
    return e.client.post(f"{API}/auth/login", json={"identifier": e.users[key]["email"], "password": password})


def bearer(session):
    return {"Authorization": f"Bearer {session['access_token']}"}


def set_flag(e, key, value=True):
    with e.session_factory() as db:
        db.get(User, e.users[key]["id"]).must_change_password = value
        db.commit()


def row(e, key):
    with e.session_factory() as db:
        u = db.get(User, e.users[key]["id"])
        return {"hash": u.hashed_password, "forced": u.must_change_password, "changed_at": u.password_changed_at}


def live_tokens(e, key):
    with e.session_factory() as db:
        return db.query(RefreshToken).filter(RefreshToken.user_id == e.users[key]["id"], RefreshToken.revoked_at.is_(None)).count()


def audits(e, action):
    with e.session_factory() as db:
        return [(a.actor_id, a.entity_id, a.before_json, a.after_json) for a in db.query(AuditEvent).filter(AuditEvent.action == action).order_by(AuditEvent.created_at)]


# ------------------------------------------------------------------------------------------------ change-password
def test_change_password_success_returns_a_fresh_session_and_audits_without_secrets(staffed, password):
    e = staffed
    s1 = login(e, "alice", password).json()
    login(e, "alice", password)                                                                              # a second device
    old_hash = row(e, "alice")["hash"]
    r = e.client.post(CHANGE, headers=bearer(s1), json={"current_password": password, "new_password": NEW_PW})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["user"]["role"] == "CITIZEN" and out["user"]["must_change_password"] is False and out["access_token"] and out["refresh_token"] and out["token_type"] == "bearer"
    assert row(e, "alice")["hash"] != old_hash and row(e, "alice")["changed_at"] is not None and row(e, "alice")["forced"] is False
    assert login(e, "alice", password).status_code == 401 and login(e, "alice", NEW_PW).status_code == 200      # the old password is gone, the new one works
    assert e.client.get(f"{API}/auth/me", headers=bearer(out)).json()["must_change_password"] is False
    assert e.client.post(f"{API}/auth/refresh", json={"refresh_token": out["refresh_token"]}).status_code == 200  # the fresh refresh token is usable
    ((actor, entity, before, after),) = audits(e, "user.password_changed")
    assert actor == entity == e.users["alice"]["id"] and before == {"must_change_password": False} and after["sessions_revoked"] == 2
    blob = json.dumps([before, after])
    assert not any(s in blob for s in (password, NEW_PW, row(e, "alice")["hash"], old_hash, out["refresh_token"], s1["refresh_token"], "password_hash")) and "hashed_password" not in blob
    assert not any(s in r.text for s in (NEW_PW, row(e, "alice")["hash"]))


def test_change_password_revokes_every_other_refresh_token(staffed, password):
    e = staffed
    s1, s2, other = login(e, "alice", password).json(), login(e, "alice", password).json(), login(e, "bob", password).json()
    assert live_tokens(e, "alice") == 2
    new = e.client.post(CHANGE, headers=bearer(s1), json={"current_password": password, "new_password": NEW_PW}).json()
    assert live_tokens(e, "alice") == 1                                                                    # only the one just issued
    assert live_tokens(e, "bob") == 1                                                                      # other users untouched
    assert e.client.post(f"{API}/auth/refresh", json={"refresh_token": s2["refresh_token"]}).status_code == 401      # another device: signed out
    assert e.client.post(f"{API}/auth/refresh", json={"refresh_token": other["refresh_token"]}).status_code == 200
    r = e.client.post(f"{API}/auth/refresh", json={"refresh_token": s1["refresh_token"]})                  # the caller's own old token too
    assert r.status_code == 401 and r.json()["error"]["code"] == "AUTH_INVALID_TOKEN"
    assert new["refresh_token"] not in (s1["refresh_token"], s2["refresh_token"])


def test_wrong_current_password_changes_nothing_and_is_throttled(staffed, password):
    e = staffed
    s = login(e, "alice", password).json()
    before = row(e, "alice")
    r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": "not-my-password", "new_password": NEW_PW})
    assert r.status_code == 400 and r.json()["error"]["code"] == "CURRENT_PASSWORD_INCORRECT"
    assert row(e, "alice") == before and live_tokens(e, "alice") == 1 and audits(e, "user.password_changed") == []
    for _ in range(4):
        e.client.post(CHANGE, headers=bearer(s), json={"current_password": "nope", "new_password": NEW_PW})
    r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": NEW_PW})      # locked, even with the right password
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"
    assert row(e, "alice") == before


@pytest.mark.parametrize("bad", ["short", "123456789", "password", "Password", "12345678", "qwertyuiop", "aaaaaaaaaaaa", "   Qwerty   ", ""])
def test_weak_new_passwords_are_refused(staffed, password, bad):
    e = staffed
    s = login(e, "alice", password).json()
    r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": bad})
    assert r.status_code in (422,) and r.json()["error"]["code"] in ("WEAK_PASSWORD", "VALIDATION_ERROR"), r.text
    assert login(e, "alice", password).status_code == 200 and audits(e, "user.password_changed") == []


def test_new_password_must_differ_from_current_and_not_be_the_demo_password(staffed, password):
    e = staffed
    s = login(e, "alice", password).json()
    r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": password})
    assert r.status_code == 422 and r.json()["error"]["code"] == "WEAK_PASSWORD" and "different from the current password" in r.json()["error"]["details"]["reasons"]
    for demo in (settings.DEMO_PASSWORD, settings.DEMO_PASSWORD.upper()):
        r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": demo})
        assert r.status_code == 422 and r.json()["error"]["code"] == "WEAK_PASSWORD", demo
    r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": "x" * 9})
    assert r.status_code == 422 and r.json()["error"]["details"]["field"] == "new_password" and "at least 10 characters" in r.json()["error"]["details"]["reasons"]
    ok = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": "x" * 10 + "y"})
    assert ok.status_code == 200


def test_change_password_needs_authentication_and_a_valid_body(staffed, password):
    e = staffed
    assert e.client.post(CHANGE, json={"current_password": password, "new_password": NEW_PW}).status_code == 401
    s = login(e, "alice", password).json()
    assert e.client.post(CHANGE, headers=bearer(s), json={"new_password": NEW_PW}).status_code == 422
    assert e.client.post(CHANGE, headers=bearer(s), json={"current_password": password}).status_code == 422
    assert e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": "p" * 201}).status_code == 422
    for who in ("roads_op", "admin", "overlooker", "ward_officer", "roads_worker"):                        # every role may change its own password
        r = e.client.post(CHANGE, headers=e.headers(who), json={"current_password": password, "new_password": f"{who}-new-passphrase"})
        assert r.status_code == 200 and r.json()["user"]["role"] == e.users[who]["role"].upper(), who


# ------------------------------------------------------------------------------------------------ forced-change gate
def test_forced_change_blocks_everything_except_the_four_auth_endpoints(staffed, password):
    e = staffed
    s = login(e, "roads_op", password).json()
    assert s["user"]["must_change_password"] is False
    set_flag(e, "roads_op")
    login_again = login(e, "roads_op", password).json()
    assert login_again["user"]["must_change_password"] is True                                                # the login response says so
    h = bearer(login_again)
    for method, url in (("get", f"{API}/me"), ("get", f"{API}/cases"), ("get", f"{API}/analytics/overview"), ("get", f"{API}/admin/users"), ("get", f"{API}/me/notifications"),
                        ("patch", f"{API}/me")):
        r = getattr(e.client, method)(url, headers=h, **({"json": {}} if method != "get" else {}))
        assert r.status_code == 403 and r.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED", (url, r.status_code, r.text)
    me = e.client.get(f"{API}/auth/me", headers=h)
    assert me.status_code == 200 and me.json()["must_change_password"] is True
    rf = e.client.post(f"{API}/auth/refresh", json={"refresh_token": login_again["refresh_token"]})
    assert rf.status_code == 200
    assert e.client.post(f"{API}/auth/logout", json={"refresh_token": rf.json()["refresh_token"]}).status_code == 200
    assert e.client.get(f"{API}/me").status_code == 401                                                       # unauthenticated stays 401, not 403


def test_change_password_works_while_forced_and_lifts_the_gate(staffed, password):
    e = staffed
    set_flag(e, "roads_op")
    s = login(e, "roads_op", password).json()
    assert e.client.get(f"{API}/analytics/overview", headers=bearer(s)).status_code == 403
    r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": NEW_PW})
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is False
    assert row(e, "roads_op")["forced"] is False
    assert e.client.get(f"{API}/analytics/overview", headers=bearer(r.json())).status_code == 200
    assert e.client.get(f"{API}/analytics/overview", headers=bearer(s)).status_code == 200                    # the old access token is not gated any more either (flag cleared)
    ((_, _, before, after),) = audits(e, "user.password_changed")
    assert before == {"must_change_password": True} and after["must_change_password"] is False


def test_a_failed_change_keeps_the_gate_closed(staffed, password):
    e = staffed
    set_flag(e, "alice")
    s = login(e, "alice", password).json()
    assert e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": "short"}).status_code == 422
    assert e.client.get(f"{API}/me", headers=bearer(s)).status_code == 403 and row(e, "alice")["forced"] is True


# ------------------------------------------------------------------------------------------------ admin: create + reset
def test_new_staff_must_change_their_password_before_anything_else(staffed):
    e = staffed
    r = e.client.post(f"{API}/admin/users", headers=e.headers("admin"), json={"name": "New Op", "email": "new.op@example.test", "role": "OPERATOR", "department_id": "water_supply"})
    assert r.status_code == 201 and r.json()["user"]["must_change_password"] is True
    temp = r.json()["temporary_password"]
    s = e.client.post(f"{API}/auth/login", json={"identifier": "new.op@example.test", "password": temp}).json()
    assert s["user"]["must_change_password"] is True
    assert e.client.get(f"{API}/analytics/overview", headers=bearer(s)).json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    done = e.client.post(CHANGE, headers=bearer(s), json={"current_password": temp, "new_password": NEW_PW})
    assert done.status_code == 200
    assert e.client.get(f"{API}/analytics/overview", headers=bearer(done.json())).status_code == 200
    listed = {u["email"]: u for u in e.client.get(f"{API}/admin/users", headers=e.headers("admin")).json()["items"]}
    assert listed["new.op@example.test"]["must_change_password"] is False and listed["alice@example.test"]["must_change_password"] is False


def test_register_and_seeded_accounts_are_not_forced(env, staffed):
    from backend.services import seed
    r = env.client.post(f"{API}/auth/register", json={"name": "Citizen", "email": "c@example.test", "password": "a-long-enough-password"})
    assert r.json()["user"]["must_change_password"] is False
    with env.session_factory() as db:
        seed.seed_demo_city(db)
        db.commit()
        demo = db.query(User).filter(User.synthetic.is_(True)).all()
        assert len(demo) > 5 and not any(u.must_change_password for u in demo)
        assert not any(u.must_change_password for u in db.query(User).filter(User.email.like("%example.test")))


def reset(e, who, target_key, **kw):
    return e.client.post(f"{API}/admin/users/{e.users[target_key]['id']}/reset-password", headers=e.headers(who), **kw)


def test_reset_password_returns_a_one_time_password_forces_change_and_ends_sessions(staffed, password):
    e = staffed
    e.make_user("system_admin", "sysadmin")
    s = login(e, "roads_op", password).json()
    assert live_tokens(e, "roads_op") == 1
    r = reset(e, "admin", "roads_op")
    assert r.status_code == 200, r.text
    out = r.json()
    temp = out["temporary_password"]
    assert len(temp) >= 12 and out["user"]["id"] == e.users["roads_op"]["id"] and out["user"]["must_change_password"] is True and "hash" not in str(out["user"]).lower()
    assert row(e, "roads_op")["forced"] is True and live_tokens(e, "roads_op") == 0
    assert e.client.post(f"{API}/auth/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401
    assert login(e, "roads_op", password).status_code == 401                                                  # the old password is dead
    fresh = login(e, "roads_op", temp)
    assert fresh.status_code == 200 and fresh.json()["user"]["must_change_password"] is True
    assert e.client.get(f"{API}/analytics/overview", headers=bearer(fresh.json())).json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert e.client.post(CHANGE, headers=bearer(fresh.json()), json={"current_password": temp, "new_password": NEW_PW}).status_code == 200
    assert temp not in e.client.get(f"{API}/admin/users", headers=e.headers("admin")).text
    ((actor, entity, before, after),) = audits(e, "user.password_reset")
    assert actor == e.users["admin"]["id"] and entity == e.users["roads_op"]["id"] and before == {"must_change_password": False}
    assert after == {"must_change_password": True, "sessions_revoked": 1}
    blob = json.dumps([before, after])
    assert temp not in blob and row(e, "roads_op")["hash"] not in blob
    with e.session_factory() as db:
        assert db.query(AuditEvent).filter(AuditEvent.action == "user.password_reset", AuditEvent.after_json.isnot(None)).count() == 1


def test_reset_password_is_not_idempotency_keyed(staffed):
    e = staffed
    key = {"Idempotency-Key": "same-key-for-both"}
    a = e.client.post(f"{API}/admin/users/{e.users['bob']['id']}/reset-password", headers={**e.headers("admin"), **key})
    b = e.client.post(f"{API}/admin/users/{e.users['bob']['id']}/reset-password", headers={**e.headers("admin"), **key})
    assert a.status_code == b.status_code == 200 and a.json()["temporary_password"] != b.json()["temporary_password"] and "idempotent-replayed" not in b.headers
    assert len(audits(e, "user.password_reset")) == 2
    assert e.client.post(f"{API}/admin/users/{e.users['bob']['id']}/reset-password", headers=e.headers("admin")).status_code == 200   # no key needed


def test_only_city_and_system_admins_may_reset_passwords(staffed, password):
    e = staffed
    e.make_user("system_admin", "sysadmin")
    target = "bob"
    assert e.client.post(f"{API}/admin/users/{e.users[target]['id']}/reset-password").status_code == 401
    for who in ("alice", "roads_worker", "roads_op", "roads_mgr", "ward_officer", "overlooker"):
        r = reset(e, who, target)
        assert r.status_code == 403 and r.json()["error"]["code"] == "AUTH_FORBIDDEN", who
    assert audits(e, "user.password_reset") == [] and row(e, target)["forced"] is False and login(e, target, password).status_code == 200
    for who in ("admin", "sysadmin"):
        assert reset(e, who, target).status_code == 200, who
    assert len(audits(e, "user.password_reset")) == 2


def test_elevated_accounts_are_reset_by_a_system_admin_only_and_nobody_resets_themselves(staffed, password):
    e = staffed
    e.make_user("system_admin", "sysadmin")
    e.make_user("city_admin", "admin2")
    e.make_user("system_admin", "sysadmin2")
    for target in ("admin2", "sysadmin2"):
        r = reset(e, "admin", target)
        assert r.status_code == 403 and r.json()["error"]["code"] == "AUTH_FORBIDDEN", target
        assert row(e, target)["forced"] is False
    assert reset(e, "sysadmin", "admin2").status_code == 200 and reset(e, "sysadmin", "sysadmin2").status_code == 200
    assert reset(e, "admin", "admin").status_code == 403                                                      # a city admin is elevated: blocked by the same rule
    r = reset(e, "sysadmin", "sysadmin")
    assert r.status_code == 409 and r.json()["error"]["code"] == "CANNOT_MODIFY_SELF" and row(e, "sysadmin")["forced"] is False


def test_reset_for_an_unknown_user_is_404_and_an_inactive_user_can_be_reset(staffed):
    e = staffed
    r = e.client.post(f"{API}/admin/users/does-not-exist/reset-password", headers=e.headers("admin"))
    assert r.status_code == 404 and r.json()["error"]["code"] == "USER_NOT_FOUND" and audits(e, "user.password_reset") == []
    with e.session_factory() as db:
        db.get(User, e.users["bob"]["id"]).is_active = False
        db.commit()
    assert reset(e, "admin", "bob").status_code == 200
