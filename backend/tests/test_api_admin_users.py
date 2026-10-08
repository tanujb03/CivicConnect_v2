"""A12 user management: GET/POST /admin/users, PATCH /admin/users/{id}. Every role on every endpoint, validation, elevated-role rules, audit rows, session invalidation."""
import uuid

import pytest

from backend.models import AuditEvent, DeviceToken, IdempotencyKey, RefreshToken, User
from backend.tests.helpers import create_case

DENIED = ["alice", "roads_worker", "roads_op", "roads_mgr", "ward_officer", "overlooker"]      # every other role of the `staffed` cast
URL = "/api/v1/admin/users"


@pytest.fixture
def adm(staffed):
    staffed.make_user("system_admin", "sysadmin")
    return staffed


def new_user(**kw):
    n = uuid.uuid4().hex[:8]
    return {"name": f"New {n}", "email": f"new.{n}@example.test", "role": "OPERATOR", "department_id": "road_maintenance", **kw}


def audit(e, action, entity_id=None):
    with e.session_factory() as db:
        q = db.query(AuditEvent).filter(AuditEvent.action == action)
        if entity_id:
            q = q.filter(AuditEvent.entity_id == entity_id)
        return [(a.actor_id, a.entity_type, a.entity_id, a.before_json, a.after_json) for a in q.order_by(AuditEvent.created_at)]


def user_row(e, uid):
    with e.session_factory() as db:
        u = db.get(User, uid)
        return {"role": u.role, "department_id": u.department_id, "ward_id": u.ward_id, "is_active": u.is_active, "name": u.name}


# ------------------------------------------------------------------------------------------------ roles on every endpoint
def test_only_city_and_system_admins_may_use_the_user_endpoints(adm):
    e = adm
    target = e.users["alice"]["id"]
    assert e.client.get(URL).status_code == 401 and e.client.post(URL, json=new_user()).status_code == 401
    for who in DENIED:
        assert e.client.get(URL, headers=e.headers(who)).status_code == 403, who
        r = e.client.post(URL, headers=e.headers(who), json=new_user())
        assert r.status_code == 403 and r.json()["error"]["code"] == "AUTH_FORBIDDEN", who
        assert e.client.patch(f"{URL}/{target}", headers=e.idem(who), json={"name": "x"}).status_code == 403, who
    assert audit(e, "user.created") == [] and user_row(e, target)["name"] == "alice"                    # nothing happened
    for who in ("admin", "sysadmin"):
        assert e.client.get(URL, headers=e.headers(who)).status_code == 200, who
        assert e.client.post(URL, headers=e.headers(who), json=new_user()).status_code == 201, who
        assert e.client.patch(f"{URL}/{target}", headers=e.idem(who), json={"name": f"by {who}"}).status_code == 200, who


# ------------------------------------------------------------------------------------------------ list
def test_list_filters_search_pagination_and_report_counts(adm):
    e = adm
    create_case(e, "alice")
    r = e.client.get(URL, headers=e.headers("admin"))
    body = r.json()
    assert r.status_code == 200 and {"items", "next_cursor"} == set(body) and len(body["items"]) >= 10
    first = body["items"][0]
    assert {"id", "name", "email", "phone", "role", "department_id", "ward_id", "preferred_language", "is_active", "status", "synthetic", "created_at", "updated_at",
            "last_login_at", "cases_reported", "must_change_password"} == set(first)
    assert not any(("password" in k and k != "must_change_password") or "hash" in k for k in first)
    by_email = {u["email"]: u for u in body["items"]}
    assert by_email["alice@example.test"]["cases_reported"] == 1 and by_email["bob@example.test"]["cases_reported"] == 0
    assert by_email["alice@example.test"]["role"] == "CITIZEN" and by_email["alice@example.test"]["status"] == "active"

    ops = e.client.get(f"{URL}?role=operator", headers=e.headers("admin")).json()["items"]
    assert {u["role"] for u in ops} == {"OPERATOR"} and {u["department_id"] for u in ops} == {"road_maintenance", "water_supply"}
    assert [u["department_id"] for u in e.client.get(f"{URL}?department_id=water_supply&role=OPERATOR", headers=e.headers("admin")).json()["items"]] == ["water_supply"]
    assert [u["email"] for u in e.client.get(f"{URL}?q=ALICE", headers=e.headers("admin")).json()["items"]] == ["alice@example.test"]       # case-insensitive substring
    assert e.client.get(f"{URL}?q=%25", headers=e.headers("admin")).json()["items"] == []                                                  # LIKE wildcards are escaped
    assert e.client.get(f"{URL}?role=wizard", headers=e.headers("admin")).status_code == 422
    assert e.client.get(f"{URL}?is_active=false", headers=e.headers("admin")).json()["items"] == []

    seen, cursor = [], None
    for _ in range(20):
        page = e.client.get(f"{URL}?limit=3" + (f"&cursor={cursor}" if cursor else ""), headers=e.headers("sysadmin")).json()
        assert len(page["items"]) <= 3
        seen += [u["id"] for u in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == len(body["items"]) and e.client.get(f"{URL}?cursor=garbage", headers=e.headers("admin")).status_code == 422


# ------------------------------------------------------------------------------------------------ create
def test_create_staff_returns_a_one_time_password_that_works_and_is_audited(adm, password):
    e = adm
    body = new_user(role="DEPARTMENT_MANAGER", department_id="water_supply", phone="+91 98765-43210", preferred_language="hi")
    r = e.client.post(URL, headers=e.headers("admin"), json=body)
    assert r.status_code == 201, r.text
    out = r.json()
    user, pw = out["user"], out["temporary_password"]
    assert len(pw) >= 12 and user["role"] == "DEPARTMENT_MANAGER" and user["department_id"] == "water_supply" and user["ward_id"] is None
    assert user["phone"] == "+919876543210" and user["preferred_language"] == "hi" and user["is_active"] is True and pw not in str(user) and "hash" not in str(user).lower()
    login = e.client.post("/api/v1/auth/login", json={"identifier": body["email"], "password": pw})
    assert login.status_code == 200 and login.json()["user"]["role"] == "DEPARTMENT_MANAGER"
    assert user["must_change_password"] is True and login.json()["user"]["must_change_password"] is True       # staff change the one-time password at first sign-in
    assert pw not in e.client.get(URL, headers=e.headers("admin")).text                                   # shown once, never again
    ((actor, entity, eid, before, after),) = audit(e, "user.created")
    assert (actor, entity, eid, before) == (e.users["admin"]["id"], "user", user["id"], None)
    assert after["role"] == "department_manager" and after["department_id"] == "water_supply" and after["email"] == body["email"]
    assert not any(k in after for k in ("password", "hashed_password")) and pw not in str(after)
    with e.session_factory() as db:                                                                       # the password is stored only as a hash
        assert db.get(User, user["id"]).hashed_password not in (None, pw)
        assert db.query(IdempotencyKey).count() == 0                                                      # the create route stores no replayable response


def test_create_validates_role_scope_and_duplicates(adm):
    e, h = adm, adm.headers("admin")
    ward = e.ward_id
    ok = e.client.post(URL, headers=h, json=new_user(role="WARD_OFFICER", department_id=None, ward_id=ward))
    assert ok.status_code == 201 and ok.json()["user"]["ward_id"] == ward and ok.json()["user"]["department_id"] is None
    assert e.client.post(URL, headers=h, json=new_user(role="field_worker")).status_code == 201                 # roles are case-insensitive
    assert e.client.post(URL, headers=h, json=new_user(role="OVERLOOKER", department_id=None)).status_code == 201

    def bad(**kw):
        r = e.client.post(URL, headers=h, json=new_user(**kw))
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR", (kw, r.text)
        return r.json()["error"]
    assert bad(role="OPERATOR", department_id=None)["details"]["field"] == "department_id"
    assert bad(role="OPERATOR", department_id="no_such_department")["details"]["field"] == "department_id"
    assert bad(role="OPERATOR", ward_id=ward)["details"]["field"] == "ward_id"
    assert bad(role="WARD_OFFICER", department_id=None, ward_id=None)["details"]["field"] == "ward_id"
    assert bad(role="WARD_OFFICER", department_id=None, ward_id="no-such-ward")["details"]["field"] == "ward_id"
    assert bad(role="WARD_OFFICER", ward_id=ward)["details"]["field"] == "department_id"
    r = e.client.post(URL, headers=e.headers("sysadmin"), json=new_user(role="CITY_ADMIN"))                   # a SYSTEM_ADMIN may grant it, but it carries no department
    assert r.status_code == 422 and r.json()["error"]["details"]["field"] == "department_id"
    assert bad(role="CITIZEN", department_id=None)["details"]["field"] == "role"                              # citizens register themselves
    assert bad(role="WIZARD")["details"]["field"] == "role"
    assert bad(email=None)["details"]["fields"] == ["email", "phone"]
    assert bad(email="not-an-email") and bad(name="") and bad(phone="123", email=None)
    dup = new_user()
    assert e.client.post(URL, headers=h, json=dup).status_code == 201
    r = e.client.post(URL, headers=h, json={**new_user(), "email": dup["email"].upper()})
    assert r.status_code == 409 and r.json()["error"]["code"] == "USER_ALREADY_EXISTS"


def test_only_a_system_admin_grants_elevated_roles(adm):
    e = adm
    r = e.client.post(URL, headers=e.headers("admin"), json=new_user(role="CITY_ADMIN", department_id=None))
    assert r.status_code == 403 and r.json()["error"]["code"] == "AUTH_FORBIDDEN"
    assert e.client.post(URL, headers=e.headers("admin"), json=new_user(role="SYSTEM_ADMIN", department_id=None)).status_code == 403
    made = e.client.post(URL, headers=e.headers("sysadmin"), json=new_user(role="CITY_ADMIN", department_id=None))
    assert made.status_code == 201 and made.json()["user"]["role"] == "CITY_ADMIN"
    assert e.client.post(URL, headers=e.headers("sysadmin"), json=new_user(role="SYSTEM_ADMIN", department_id=None)).status_code == 201
    op = e.users["roads_op"]["id"]                                                                           # promoting an existing user is the same rule
    assert e.client.patch(f"{URL}/{op}", headers=e.idem("admin"), json={"role": "CITY_ADMIN", "department_id": None}).status_code == 403
    assert user_row(e, op)["role"] == "operator"
    assert e.client.patch(f"{URL}/{op}", headers=e.idem("sysadmin"), json={"role": "CITY_ADMIN", "department_id": None}).status_code == 200
    assert user_row(e, op) == {"role": "city_admin", "department_id": None, "ward_id": None, "is_active": True, "name": "roads_op"}
    boss = made.json()["user"]["id"]                                                                         # a city admin cannot touch an elevated account at all
    assert e.client.patch(f"{URL}/{boss}", headers=e.idem("admin"), json={"name": "x"}).status_code == 403
    assert e.client.patch(f"{URL}/{boss}", headers=e.idem("admin"), json={"is_active": False}).status_code == 403
    assert e.client.patch(f"{URL}/{boss}", headers=e.idem("sysadmin"), json={"name": "Renamed boss"}).status_code == 200


# ------------------------------------------------------------------------------------------------ patch
def test_patch_changes_role_department_ward_and_audits_before_and_after(adm):
    e = adm
    op = e.users["roads_op"]["id"]
    r = e.client.patch(f"{URL}/{op}", headers=e.idem("admin"), json={"department_id": "water_supply"})
    assert r.status_code == 200 and r.json()["department_id"] == "water_supply" and r.json()["role"] == "OPERATOR"
    assert audit(e, "user.updated", op)[-1][3:] == ({"department_id": "road_maintenance"}, {"department_id": "water_supply"})

    r = e.client.patch(f"{URL}/{op}", headers=e.idem("admin"), json={"role": "WARD_OFFICER", "ward_id": e.ward_id})          # the department no longer applies: cleared
    assert r.status_code == 200 and (r.json()["role"], r.json()["department_id"], r.json()["ward_id"]) == ("WARD_OFFICER", None, e.ward_id)
    ((actor, entity, eid, before, after),) = audit(e, "user.role_changed", op)
    assert (actor, entity) == (e.users["admin"]["id"], "user")
    assert before == {"role": "operator", "department_id": "water_supply", "ward_id": None} and after == {"role": "ward_officer", "department_id": None, "ward_id": e.ward_id}

    assert e.client.patch(f"{URL}/{op}", headers=e.idem("admin"), json={"role": "OPERATOR"}).status_code == 422             # a department is required again
    r = e.client.patch(f"{URL}/{op}", headers=e.idem("admin"), json={"role": "OPERATOR", "department_id": "road_maintenance"})
    assert r.status_code == 200 and r.json()["ward_id"] is None
    assert e.client.patch(f"{URL}/{op}", headers=e.idem("admin"), json={"department_id": None}).status_code == 422          # an operator keeps a department
    assert e.client.patch(f"{URL}/{op}", headers=e.idem("admin"), json={"ward_id": e.ward_id}).status_code == 422
    assert e.client.patch(f"{URL}/{op}", headers=e.idem("admin"), json={"department_id": "nope"}).status_code == 422
    assert user_row(e, op)["department_id"] == "road_maintenance"                                                            # failed patches changed nothing


def test_patch_validation_noop_and_not_found(adm):
    e = adm
    uid = e.users["bob"]["id"]
    n = len(audit(e, "user.updated"))
    assert e.client.patch(f"{URL}/{uid}", headers=e.idem("admin"), json={}).status_code == 200
    assert e.client.patch(f"{URL}/{uid}", headers=e.idem("admin"), json={"name": "bob"}).status_code == 200                 # unchanged value
    assert len(audit(e, "user.updated")) == n                                                                                # no change, no audit row
    for payload in ({"name": None}, {"role": None}, {"is_active": None}, {"role": "WIZARD"}, {"name": ""}, {"is_active": "maybe"}):
        assert e.client.patch(f"{URL}/{uid}", headers=e.idem("admin"), json=payload).status_code == 422, payload
    r = e.client.patch(f"{URL}/{uuid.uuid4()}", headers=e.idem("admin"), json={"name": "x"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "USER_NOT_FOUND"
    r = e.client.patch(f"{URL}/{uid}", headers=e.headers("admin"), json={"name": "no key"})                                  # mutations need an Idempotency-Key like all others
    assert r.status_code == 400 and r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_patch_is_idempotent_and_audited_once(adm):
    e = adm
    uid, key = e.users["bob"]["id"], str(uuid.uuid4())
    first = e.client.patch(f"{URL}/{uid}", headers=e.idem("admin", key), json={"name": "Bob Renamed"})
    again = e.client.patch(f"{URL}/{uid}", headers=e.idem("admin", key), json={"name": "Bob Renamed"})
    assert first.status_code == again.status_code == 200 and again.headers.get("idempotent-replayed") == "true" and first.json() == again.json()
    assert len(audit(e, "user.updated", uid)) == 1
    assert e.client.patch(f"{URL}/{uid}", headers=e.idem("admin", key), json={"name": "Other"}).status_code == 422          # same key, other body


def test_nobody_changes_their_own_role_or_deactivates_themselves(adm):
    e = adm
    sa = e.users["sysadmin"]["id"]
    for payload in ({"role": "CITIZEN"}, {"role": "OPERATOR", "department_id": "road_maintenance"}, {"is_active": False}):
        r = e.client.patch(f"{URL}/{sa}", headers=e.idem("sysadmin"), json=payload)
        assert r.status_code == 409 and r.json()["error"]["code"] == "CANNOT_MODIFY_SELF", payload
    assert e.client.patch(f"{URL}/{sa}", headers=e.idem("sysadmin"), json={"role": "SYSTEM_ADMIN", "name": "Sys Renamed"}).status_code == 200      # same role is fine
    assert user_row(e, sa) == {"role": "system_admin", "department_id": None, "ward_id": None, "is_active": True, "name": "Sys Renamed"}
    me = e.users["admin"]["id"]                                           # a city admin is an elevated account itself: only a SYSTEM_ADMIN edits it, nobody edits themselves
    for payload in ({"role": "CITIZEN"}, {"is_active": False}, {"name": "x"}):
        assert e.client.patch(f"{URL}/{me}", headers=e.idem("admin"), json=payload).status_code == 403, payload
    assert user_row(e, me)["role"] == "city_admin" and user_row(e, me)["is_active"] is True


# ------------------------------------------------------------------------------------------------ deactivation
def test_deactivating_a_user_ends_every_session_at_once(adm, password):
    e = adm
    uid, email = e.users["bob"]["id"], e.users["bob"]["email"]
    session = e.client.post("/api/v1/auth/login", json={"identifier": email, "password": password}).json()
    bearer = {"Authorization": f"Bearer {session['access_token']}"}
    assert e.client.get("/api/v1/me", headers=bearer).status_code == 200
    with e.session_factory() as db:
        db.add(DeviceToken(user_id=uid, platform="android", expo_push_token="ExponentPushToken[bob-device]"))
        db.commit()

    r = e.client.patch(f"{URL}/{uid}", headers=e.idem("admin"), json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False and r.json()["status"] == "inactive"
    assert e.client.get("/api/v1/me", headers=bearer).status_code == 401                                                     # the very next request
    assert e.client.get("/api/v1/me", headers=e.headers("bob")).status_code == 401                                           # a freshly minted token too
    assert e.client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}).status_code == 401
    assert e.client.post("/api/v1/auth/login", json={"identifier": email, "password": password}).status_code == 401
    with e.session_factory() as db:
        assert all(t.revoked_at is not None for t in db.query(RefreshToken).filter(RefreshToken.user_id == uid))
        assert all(t.revoked_at is not None for t in db.query(DeviceToken).filter(DeviceToken.user_id == uid))
    ((_, _, _, before, after),) = audit(e, "user.deactivated", uid)
    assert before == {"is_active": True} and after == {"is_active": False}
    assert e.client.get(f"{URL}?is_active=false", headers=e.headers("admin")).json()["items"][0]["id"] == uid

    r = e.client.patch(f"{URL}/{uid}", headers=e.idem("admin"), json={"is_active": True})
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert e.client.post("/api/v1/auth/login", json={"identifier": email, "password": password}).status_code == 200
    assert audit(e, "user.reactivated", uid)[0][3:] == ({"is_active": False}, {"is_active": True})
