"""Forced password change (WP2) must also close the AI gateway routes, which authenticate through ``ai_gateway.deps.get_actor`` instead of ``current_user``."""


def _force(env, key: str, value: bool = True) -> None:
    from backend.models import User
    with env.session_factory() as db:
        db.get(User, env.users[key]["id"]).must_change_password = value
        db.commit()


def test_ai_routes_refuse_an_account_that_must_change_its_password(env):
    env.make_user("citizen", "alice")
    body = {"text": "There is a big pothole near the school gate on Station Road"}
    assert env.client.post("/api/v1/cases/intake/analyze", headers=env.headers("alice"), json=body).status_code == 200
    _force(env, "alice")
    r = env.client.post("/api/v1/cases/intake/analyze", headers=env.headers("alice"), json=body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    r = env.client.post("/api/v1/copilot/query", headers=env.headers("alice"), json={"query": "how many open cases", "language": "en"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    _force(env, "alice", False)
    assert env.client.post("/api/v1/cases/intake/analyze", headers=env.headers("alice"), json=body).status_code == 200


def test_the_signin_lockout_uses_the_shared_failure_counter(env, password):
    from backend.services import auth as auth_service
    env.make_user("citizen", "carol")
    for _ in range(auth_service.MAX_FAILURES):
        assert env.client.post("/api/v1/auth/login", json={"identifier": "carol@example.test", "password": "wrong-password"}).status_code == 401
    r = env.client.post("/api/v1/auth/login", json={"identifier": "carol@example.test", "password": password})
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED" and r.json()["error"]["details"]["retry_after_seconds"] >= 1
    assert auth_service._counter.count("carol@example.test") >= auth_service.MAX_FAILURES
    auth_service.reset_throttle()
    assert env.client.post("/api/v1/auth/login", json={"identifier": "carol@example.test", "password": password}).status_code == 200


# ---------------------------------------------------------------- review follow-ups (WP2 review, 2026-10-08)
def test_every_ai_route_is_gated_not_only_intake_and_copilot(env):
    env.make_user("citizen", "alice")
    env.make_user("operator", "roads_op", department_id="road_maintenance")
    _force(env, "roads_op")
    h = env.headers("roads_op")
    for path, body in (("/api/v1/cases/c1/fusion/analyze", {}), ("/api/v1/cases/c1/triage/analyze", {}), ("/api/v1/analytics/explain", {}), ("/api/v1/copilot/query", {"query": "x"})):
        r = env.client.post(path, headers=h, json=body)
        assert r.status_code == 403 and r.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED", (path, r.status_code, r.text[:120])


def test_a_crafted_signin_identifier_cannot_lock_a_password_change(env, password):
    env.make_user("citizen", "dave")
    uid = env.users["dave"]["id"]
    for _ in range(6):                                                   # the old key shape was "pwchange:<user id>" inside the sign-in namespace
        env.client.post("/api/v1/auth/login", json={"identifier": f"pwchange:{uid}", "password": "x"})
    r = env.client.post("/api/v1/auth/change-password", headers=env.headers("dave"), json={"current_password": password, "new_password": "a-brand-new-passphrase"})
    assert r.status_code == 200, r.text


def test_lockout_answers_carry_retry_after_on_login_and_change_password(env, password):
    env.make_user("citizen", "erin")
    for _ in range(5):
        env.client.post("/api/v1/auth/login", json={"identifier": "erin@example.test", "password": "wrong"})
    r = env.client.post("/api/v1/auth/login", json={"identifier": "erin@example.test", "password": password})
    assert r.status_code == 429 and int(r.headers["retry-after"]) == r.json()["error"]["details"]["retry_after_seconds"] >= 1
    for _ in range(5):
        assert env.client.post("/api/v1/auth/change-password", headers=env.headers("erin"), json={"current_password": "wrong", "new_password": "a-brand-new-passphrase"}).status_code == 400
    r2 = env.client.post("/api/v1/auth/change-password", headers=env.headers("erin"), json={"current_password": password, "new_password": "a-brand-new-passphrase"})
    assert r2.status_code == 429 and int(r2.headers["retry-after"]) >= 1


def test_wrong_current_password_wins_over_a_weak_new_one_and_inactive_users_are_refused(env, password):
    env.make_user("citizen", "frank")
    r = env.client.post("/api/v1/auth/change-password", headers=env.headers("frank"), json={"current_password": "wrong", "new_password": "short"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "CURRENT_PASSWORD_INCORRECT"
    r = env.client.post("/api/v1/auth/change-password", headers=env.headers("frank"), json={"current_password": password, "new_password": ""})
    assert r.status_code == 422 and r.json()["error"]["code"] in ("WEAK_PASSWORD", "VALIDATION_ERROR")
    from backend.models import User
    with env.session_factory() as db:
        db.get(User, env.users["frank"]["id"]).is_active = False
        db.commit()
    assert env.client.post("/api/v1/auth/change-password", headers=env.headers("frank"), json={"current_password": password, "new_password": "a-brand-new-passphrase"}).status_code == 401


def test_responses_with_a_one_time_password_are_not_cacheable(env):
    env.make_user("city_admin", "admin")
    env.make_user("citizen", "gina")
    h = env.idem("admin")
    r = env.client.post("/api/v1/admin/users", headers=h, json={"name": "New Worker", "email": "newworker@example.test", "role": "FIELD_WORKER", "department_id": "road_maintenance"})
    assert r.status_code == 201 and r.headers["cache-control"] == "no-store" and r.json()["temporary_password"]
    r = env.client.post(f"/api/v1/admin/users/{env.users['gina']['id']}/reset-password", headers=env.headers("admin"))
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
