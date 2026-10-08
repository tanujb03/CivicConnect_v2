"""§51A.2 / §51A.3: accounts, sessions, refresh rotation, profile, notifications."""
from datetime import datetime, timedelta, timezone


def register(env, **kw):
    body = {"name": "Asha Patil", "email": "asha@example.test", "preferred_language": "mr", "password": "a-long-enough-password", **kw}
    return env.client.post("/api/v1/auth/register", json=body)


def test_register_returns_a_session_and_the_citizen_role(env):
    r = register(env)
    assert r.status_code == 201
    b = r.json()
    assert b["user"]["role"] == "CITIZEN" and b["user"]["name"] == "Asha Patil" and b["access_token"] and b["refresh_token"]
    me = env.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {b['access_token']}"}).json()
    assert me["email"] == "asha@example.test" and me["preferred_language"] == "mr" and me["access_scope"]["capabilities"] and me["role"] == "CITIZEN"
    assert "hashed_password" not in me
    assert b["user"]["must_change_password"] is False and me["must_change_password"] is False          # additive fields: citizens are never forced


def test_register_validation_and_duplicates(env):
    assert register(env, email=None, phone=None).status_code == 422                      # contact needed
    assert register(env, password="short").status_code == 422
    assert register(env, email="not-an-email").status_code == 422
    assert register(env).status_code == 201
    dup = register(env, email="ASHA@example.test")                                         # case-insensitive
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "USER_ALREADY_EXISTS"
    assert register(env, email=None, phone="+91 98765 43210").status_code == 201
    assert register(env, email=None, phone="+919876543210", name="Other").status_code == 409   # same number, spaces ignored


def test_login_by_email_or_phone_and_wrong_password(env):
    register(env, phone="+91 98765 43210")
    ok = env.client.post("/api/v1/auth/login", json={"identifier": "asha@example.test", "password": "a-long-enough-password"})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "CITIZEN"
    by_phone = env.client.post("/api/v1/auth/login", json={"identifier": "+919876543210", "password": "a-long-enough-password"})
    assert by_phone.status_code == 200
    bad = env.client.post("/api/v1/auth/login", json={"identifier": "asha@example.test", "password": "nope"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    unknown = env.client.post("/api/v1/auth/login", json={"identifier": "nobody@example.test", "password": "x"})
    assert unknown.status_code == 401 and unknown.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"      # same answer: no user enumeration
    assert env.client.post("/api/v1/auth/login", json={}).status_code == 422


def test_repeated_failures_lock_the_identifier_for_a_while(env):
    register(env)
    for _ in range(5):
        env.client.post("/api/v1/auth/login", json={"identifier": "asha@example.test", "password": "wrong"})
    r = env.client.post("/api/v1/auth/login", json={"identifier": "asha@example.test", "password": "a-long-enough-password"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED" and r.json()["error"]["details"]["retry_after_seconds"] > 0


def test_refresh_rotates_and_a_reused_token_ends_every_session(env):
    s = register(env).json()
    first = env.client.post("/api/v1/auth/refresh", json={"refresh_token": s["refresh_token"]})
    assert first.status_code == 200 and first.json()["refresh_token"] != s["refresh_token"]
    new_access = {"Authorization": f"Bearer {first.json()['access_token']}"}
    assert env.client.get("/api/v1/auth/me", headers=new_access).status_code == 200
    replay = env.client.post("/api/v1/auth/refresh", json={"refresh_token": s["refresh_token"]})       # the old token comes back: theft signal
    assert replay.status_code == 401 and replay.json()["error"]["code"] == "AUTH_INVALID_TOKEN"
    again = env.client.post("/api/v1/auth/refresh", json={"refresh_token": first.json()["refresh_token"]})
    assert again.status_code == 401                                                                       # the legitimate descendant is revoked too
    assert env.client.post("/api/v1/auth/refresh", json={"refresh_token": "x" * 40}).status_code == 401


def test_logout_revokes_the_refresh_token(env):
    s = register(env).json()
    assert env.client.post("/api/v1/auth/logout", json={"refresh_token": s["refresh_token"]}).status_code == 200
    assert env.client.post("/api/v1/auth/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401


def test_expired_refresh_token_is_refused(env):
    from backend.models import RefreshToken
    s = register(env).json()
    with env.session_factory() as db:
        for t in db.query(RefreshToken).all():
            t.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert env.client.post("/api/v1/auth/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401


def test_missing_or_bad_bearer_token_uses_the_error_envelope(env):
    r = env.client.get("/api/v1/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "AUTH_REQUIRED" and r.headers["www-authenticate"] == "Bearer"
    r = env.client.get("/api/v1/me", headers={"Authorization": "Bearer garbage", "X-Request-ID": "req-1"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "AUTH_INVALID_TOKEN" and r.json()["error"]["request_id"] == "req-1" and r.headers["x-request-id"] == "req-1"


def test_a_refresh_token_is_not_an_access_token_and_a_forged_role_does_nothing(env, staffed):
    from backend.core.security import create_access_token
    s = register(env).json()
    assert env.client.get("/api/v1/me", headers={"Authorization": f"Bearer {s['refresh_token']}"}).status_code == 401
    # a token that CLAIMS city_admin for a citizen: the role is read from the database, so the claim is ignored
    forged = create_access_token(staffed.users["alice"]["id"], "city_admin")
    r = env.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.json()["role"] == "CITIZEN"
    assert env.client.get("/api/v1/analytics/overview", headers={"Authorization": f"Bearer {forged}"}).status_code == 403


def test_demoted_or_deactivated_accounts_lose_access_immediately(staffed):
    from backend.models import User
    e = staffed
    assert e.client.get("/api/v1/analytics/overview", headers=e.headers("roads_op")).status_code == 200
    with e.session_factory() as db:
        u = db.get(User, e.users["roads_op"]["id"])
        u.role = "citizen"
        db.commit()
    assert e.client.get("/api/v1/analytics/overview", headers=e.headers("roads_op")).status_code == 403
    with e.session_factory() as db:
        db.get(User, e.users["roads_op"]["id"]).is_active = False
        db.commit()
    assert e.client.get("/api/v1/me", headers=e.headers("roads_op")).status_code == 401


def test_profile_read_and_partial_update(staffed):
    e = staffed
    r = e.client.patch("/api/v1/me", headers=e.headers("alice"), json={"preferred_language": "hi", "accessibility": {"large_text": True}})
    assert r.status_code == 200 and r.json()["preferred_language"] == "hi" and r.json()["accessibility"] == {"large_text": True}
    r = e.client.patch("/api/v1/me", headers=e.headers("alice"), json={"accessibility": {"high_contrast": True}})
    assert r.json()["accessibility"] == {"large_text": True, "high_contrast": True}          # merged, not replaced
    assert e.client.patch("/api/v1/me", headers=e.headers("alice"), json={"role": "city_admin"}).json()["role"] == "CITIZEN"    # unknown fields never change the role
    assert e.client.patch("/api/v1/me", headers=e.headers("alice"), json={"name": ""}).status_code == 422


def test_oauth2_form_login_for_the_interactive_docs(env):
    register(env)
    r = env.client.post("/api/v1/auth/token", data={"username": "asha@example.test", "password": "a-long-enough-password"})
    assert r.status_code == 200 and r.json()["access_token"]


def test_notifications_are_private_paginated_and_marked_read_idempotently(staffed):
    from backend.models import Notification
    e = staffed
    with e.session_factory() as db:
        for i in range(5):
            db.add(Notification(user_id=e.users["alice"]["id"], type="CASE_UPDATED", payload={"title": f"n{i}"}))
        db.add(Notification(user_id=e.users["bob"]["id"], type="CASE_UPDATED", payload={"title": "secret"}))
        db.commit()
    p1 = e.client.get("/api/v1/me/notifications?limit=3", headers=e.headers("alice")).json()
    assert len(p1["items"]) == 3 and p1["next_cursor"]
    p2 = e.client.get(f"/api/v1/me/notifications?limit=3&cursor={p1['next_cursor']}", headers=e.headers("alice")).json()
    assert len(p2["items"]) == 2 and p2["next_cursor"] is None
    seen = {n["payload"]["title"] for n in p1["items"] + p2["items"]}
    assert seen == {f"n{i}" for i in range(5)}                                                   # nothing of bob's, nothing twice
    nid = p1["items"][0]["id"]
    first = e.client.post(f"/api/v1/me/notifications/{nid}/read", headers=e.headers("alice"))
    again = e.client.post(f"/api/v1/me/notifications/{nid}/read", headers=e.headers("alice"))
    assert first.status_code == again.status_code == 200 and first.json()["read_at"] == again.json()["read_at"] and first.json()["read_at"]
    assert e.client.post(f"/api/v1/me/notifications/{nid}/read", headers=e.headers("bob")).status_code == 404      # someone else's notification
    unread = e.client.get("/api/v1/me/notifications?unread=true", headers=e.headers("alice")).json()["items"]
    assert len(unread) == 4
    assert e.client.get("/api/v1/me/notifications?cursor=%%%", headers=e.headers("alice")).json()["error"]["code"] == "INVALID_CURSOR"
