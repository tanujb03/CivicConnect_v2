"""Access tokens carry ``iat``; one issued before the user's last password change / admin reset is refused (401 AUTH_INVALID_TOKEN) by ``current_user`` and by the AI gateway's
``get_actor``. Whole seconds, UTC: the pair returned by change-password (issued in the same second, after the change) stays valid. Deterministic: tokens are forged with chosen
``iat`` values or the clock of the two token-issuing modules is frozen."""
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from backend.core.config import settings
from backend.core.exceptions import CivicConnectException
from backend.core.security import create_access_token, decode_token, ensure_session_current
from backend.models import User

API = "/api/v1"
CHANGE = f"{API}/auth/change-password"
NEW_PW = "a-brand-new-passphrase"
AI_BODY = {"text": "There is a big pothole near the school gate on Station Road"}
MSG = "The session predates a password change; sign in again."


def now_s() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def forge(e, key, iat="now", *, role=None) -> dict:
    """An access token for ``key`` signed like ours; ``iat`` an int, None (claim absent) or "now"."""
    u = e.users[key]
    claims = {"exp": datetime.now(timezone.utc) + timedelta(minutes=30), "sub": u["id"], "role": role or u["role"], "typ": "access"}
    if iat is not None:
        claims["iat"] = now_s() if iat == "now" else iat
    return {"Authorization": "Bearer " + jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}


def set_changed(e, key, when):
    with e.session_factory() as db:
        db.get(User, e.users[key]["id"]).password_changed_at = when
        db.commit()


def at(epoch_s: float) -> datetime:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc)


def login(e, key, password):
    return e.client.post(f"{API}/auth/login", json={"identifier": e.users[key]["email"], "password": password}).json()


def bearer(session):
    return {"Authorization": f"Bearer {session['access_token']}"}


def refused(r):
    return r.status_code == 401 and r.json()["error"]["code"] == "AUTH_INVALID_TOKEN" and r.json()["error"]["message"] == MSG


class Clock:
    """Freezes ``datetime.now`` in the modules that stamp ``iat`` (security) and ``password_changed_at`` (services.auth); ``t`` is epoch seconds (a float)."""

    def __init__(self, monkeypatch):
        self.t = datetime.now(timezone.utc).timestamp()
        outer = self

        class _DT:
            @staticmethod
            def now(tz=None):
                return datetime.fromtimestamp(outer.t, tz=tz or timezone.utc) if tz else datetime.fromtimestamp(outer.t, tz=timezone.utc).replace(tzinfo=None)

        for mod in ("backend.core.security", "backend.services.auth"):
            monkeypatch.setattr(f"{mod}.datetime", _DT)


# ------------------------------------------------------------------------------------------------ the claim
def test_access_tokens_carry_an_integer_iat_and_decode_exposes_it(env):
    env.make_user("citizen", "alice")
    before = now_s()
    tok = create_access_token("u1", "citizen")
    raw = jwt.get_unverified_claims(tok)
    assert isinstance(raw["iat"], int) and before <= raw["iat"] <= now_s() and raw["typ"] == "access"
    assert decode_token(tok)["iat"] == raw["iat"]
    legacy = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(minutes=5), "sub": "u1", "role": "citizen", "typ": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert decode_token(legacy)["iat"] is None


class _U:
    def __init__(self, changed):
        self.password_changed_at = changed


def test_ensure_session_current_rules_and_naive_datetimes():
    ensure_session_current(_U(None), {"iat": None})                                    # never changed: a legacy token is fine
    ensure_session_current(_U(None), {"iat": 5})
    with pytest.raises(CivicConnectException) as ex:
        ensure_session_current(_U(at(1000)), {"iat": None})                            # changed + no iat: refused
    assert ex.value.status_code == 401 and ex.value.code == "AUTH_INVALID_TOKEN"
    with pytest.raises(CivicConnectException):
        ensure_session_current(_U(at(1000)), {"iat": 999})
    for changed in (at(1000), at(1000).replace(tzinfo=None), at(1000.9), at(1000.9).replace(tzinfo=None)):      # naive (SQLite) = UTC; fractional seconds are floored
        ensure_session_current(_U(changed), {"iat": 1000})
        ensure_session_current(_U(changed), {"iat": 1001})
    with pytest.raises(CivicConnectException):
        ensure_session_current(_U(at(1001).replace(tzinfo=None)), {"iat": 1000})


# ------------------------------------------------------------------------------------------------ change-password
def test_old_access_token_is_refused_after_change_password_while_the_returned_pair_works(staffed, password):
    e = staffed
    old = forge(e, "alice", now_s() - 30)
    s = login(e, "alice", password)
    assert e.client.get(f"{API}/auth/me", headers=old).status_code == 200                 # never changed: still fine
    r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": NEW_PW})
    assert r.status_code == 200
    new = r.json()
    assert refused(e.client.get(f"{API}/auth/me", headers=old)) and refused(e.client.get(f"{API}/me", headers=old))
    assert refused(e.client.post(CHANGE, headers=old, json={"current_password": NEW_PW, "new_password": "yet-another-passphrase"}))
    assert e.client.get(f"{API}/auth/me", headers=bearer(new)).status_code == 200 and e.client.get(f"{API}/me", headers=bearer(new)).status_code == 200
    again = e.client.post(f"{API}/auth/refresh", json={"refresh_token": new["refresh_token"]})      # refresh tokens are unaffected, and rotate into a valid access token
    assert again.status_code == 200 and e.client.get(f"{API}/auth/me", headers=bearer(again.json())).status_code == 200
    assert e.client.get(f"{API}/auth/me", headers=bearer(login(e, "alice", NEW_PW))).status_code == 200
    assert e.client.get(f"{API}/auth/me", headers=e.headers("bob")).status_code == 200      # other users untouched


def test_frozen_clock_old_token_dies_when_a_second_has_passed_new_pair_survives(staffed, password, monkeypatch):
    e = staffed
    clock = Clock(monkeypatch)
    s = login(e, "alice", password)                                                       # iat = T
    clock.t += 2
    r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": NEW_PW})      # changed at T+2, new pair iat = T+2
    assert r.status_code == 200
    assert refused(e.client.get(f"{API}/auth/me", headers=bearer(s)))
    assert e.client.get(f"{API}/auth/me", headers=bearer(r.json())).status_code == 200


def test_same_second_pair_returned_by_change_password_stays_valid(staffed, password, monkeypatch):
    e = staffed
    clock = Clock(monkeypatch)
    clock.t = int(clock.t) + 0.2                                                          # early in a second
    s = login(e, "alice", password)
    clock.t += 0.5                                                                        # same whole second: change and new tokens
    r = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": NEW_PW})
    assert r.status_code == 200
    assert jwt.get_unverified_claims(r.json()["access_token"])["iat"] == jwt.get_unverified_claims(s["access_token"])["iat"]
    assert e.client.get(f"{API}/auth/me", headers=bearer(r.json())).status_code == 200
    assert e.client.get(f"{API}/auth/me", headers=bearer(s)).status_code == 200            # documented: a token from the same second may survive that second
    clock.t += 1
    assert e.client.get(f"{API}/auth/me", headers=bearer(s)).status_code == 200            # the clock moving on changes nothing: the comparison is iat vs the change time
    assert e.client.get(f"{API}/auth/me", headers=bearer(r.json())).status_code == 200


def test_boundary_iat_equal_to_the_change_second_passes_one_less_is_refused(staffed):
    e = staffed
    t = now_s() - 100
    set_changed(e, "alice", at(t + 0.9))
    assert e.client.get(f"{API}/auth/me", headers=forge(e, "alice", t)).status_code == 200
    assert e.client.get(f"{API}/auth/me", headers=forge(e, "alice", t + 5)).status_code == 200
    assert refused(e.client.get(f"{API}/auth/me", headers=forge(e, "alice", t - 1)))


# ------------------------------------------------------------------------------------------------ admin reset
def test_admin_reset_sets_password_changed_at_and_old_tokens_stay_dead_after_the_next_change(staffed, password):
    e = staffed
    old = forge(e, "roads_op", now_s() - 30)
    assert e.client.get(f"{API}/auth/me", headers=old).status_code == 200
    r = e.client.post(f"{API}/admin/users/{e.users['roads_op']['id']}/reset-password", headers=e.headers("admin"))
    assert r.status_code == 200
    with e.session_factory() as db:
        assert db.get(User, e.users["roads_op"]["id"]).password_changed_at is not None
    assert refused(e.client.get(f"{API}/auth/me", headers=old))                            # dead at once (before, only the forced-change gate stopped it)
    temp = r.json()["temporary_password"]
    fresh = login(e, "roads_op", temp)
    assert fresh["user"]["must_change_password"] is True and e.client.get(f"{API}/auth/me", headers=bearer(fresh)).status_code == 200
    done = e.client.post(CHANGE, headers=bearer(fresh), json={"current_password": temp, "new_password": NEW_PW})
    assert done.status_code == 200 and e.client.get(f"{API}/analytics/overview", headers=bearer(done.json())).status_code == 200
    assert refused(e.client.get(f"{API}/analytics/overview", headers=old))                 # still dead after the user's own change
    assert e.client.get(f"{API}/auth/me", headers=e.headers("bob")).status_code == 200


# ------------------------------------------------------------------------------------------------ legacy tokens without iat
def test_token_without_iat_is_accepted_for_a_never_changed_user_and_refused_for_a_changed_one(staffed):
    e = staffed
    legacy = forge(e, "alice", None)
    assert e.client.get(f"{API}/auth/me", headers=legacy).status_code == 200 and e.client.get(f"{API}/me", headers=legacy).status_code == 200
    assert e.client.post(f"{API}/cases/intake/analyze", headers=legacy, json=AI_BODY).status_code == 200
    set_changed(e, "alice", at(now_s() - 3600))
    assert refused(e.client.get(f"{API}/auth/me", headers=legacy)) and refused(e.client.get(f"{API}/me", headers=legacy))
    assert refused(e.client.post(f"{API}/cases/intake/analyze", headers=legacy, json=AI_BODY))
    assert e.client.get(f"{API}/auth/me", headers=e.headers("alice")).status_code == 200      # a token with iat after the change is fine
    assert e.client.get(f"{API}/auth/me", headers=forge(e, "bob", None)).status_code == 200    # another user without iat: unaffected


# ------------------------------------------------------------------------------------------------ AI gateway (get_actor)
def test_ai_gateway_route_applies_the_same_rule(staffed, password):
    e = staffed
    url = f"{API}/cases/intake/analyze"
    old = forge(e, "alice", now_s() - 30)
    s = login(e, "alice", password)
    assert e.client.post(url, headers=old, json=AI_BODY).status_code == 200
    new = e.client.post(CHANGE, headers=bearer(s), json={"current_password": password, "new_password": NEW_PW}).json()
    assert refused(e.client.post(url, headers=old, json=AI_BODY))
    r = e.client.post(f"{API}/copilot/query", headers=forge(e, "alice", now_s() - 30), json={"query": "how many open cases", "language": "en"})
    assert refused(r)
    assert e.client.post(url, headers=bearer(new), json=AI_BODY).status_code == 200      # the returned pair, same second or not
    set_changed(e, "bob", at(now_s() + 0.0))
    assert e.client.post(url, headers=forge(e, "bob", now_s()), json=AI_BODY).status_code == 200          # same second: passes
    assert refused(e.client.post(url, headers=forge(e, "bob", now_s() - 5), json=AI_BODY))
    set_changed(e, "roads_op", at(now_s() - 3600))
    assert e.client.post(url, headers=e.headers("roads_op"), json=AI_BODY).status_code == 200


def test_ai_gateway_reset_user_with_an_old_token_gets_401_not_403(staffed):
    e = staffed
    old = forge(e, "roads_op", now_s() - 30)
    assert e.client.post(f"{API}/admin/users/{e.users['roads_op']['id']}/reset-password", headers=e.headers("admin")).status_code == 200
    assert refused(e.client.post(f"{API}/cases/intake/analyze", headers=old, json=AI_BODY))
