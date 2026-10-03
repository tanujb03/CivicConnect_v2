"""A13 system settings: GET/PUT /admin/settings over system_settings; typed validation, audit rows, and the two thresholds really changing the AI behaviour."""
import uuid

import pytest

from ai.inference.config import load_fusion_policy
from backend.models import AuditEvent, SystemSetting
from backend.services import settings as settings_service
from backend.tests.helpers import create_case

URL = "/api/v1/admin/settings"
DENIED = ["alice", "roads_worker", "roads_op", "roads_mgr", "ward_officer", "overlooker"]
KEYS = ["ai_confidence_threshold", "duplicate_threshold", "sla_hours_by_priority", "supported_languages", "notification_policy", "flag_review_threshold"]


@pytest.fixture
def adm(staffed):
    staffed.make_user("system_admin", "sysadmin")
    return staffed


def put(e, who, values, reason=None, key=None):
    body = {"values": values, **({"reason": reason} if reason else {})}
    return e.client.put(URL, headers=e.idem(who, key), json=body)


def as_map(response):
    return {i["key"]: i for i in response.json()["items"]}


def audit_rows(e):
    with e.session_factory() as db:
        return [(a.actor_id, a.entity_type, a.entity_id, a.before_json, a.after_json) for a in db.query(AuditEvent).filter(AuditEvent.action == "settings.updated").order_by(AuditEvent.created_at)]


# ------------------------------------------------------------------------------------------------ roles
def test_only_city_and_system_admins_read_and_write_settings(adm):
    e = adm
    assert e.client.get(URL).status_code == 401 and e.client.put(URL, json={"values": {"flag_review_threshold": 4}}).status_code == 401
    for who in DENIED:
        assert e.client.get(URL, headers=e.headers(who)).status_code == 403, who
        r = put(e, who, {"flag_review_threshold": 9})
        assert r.status_code == 403 and r.json()["error"]["code"] == "AUTH_FORBIDDEN", who
    assert as_map(e.client.get(URL, headers=e.headers("admin")))["flag_review_threshold"]["value"] == 3 and audit_rows(e) == []
    for who, value in (("admin", 4), ("sysadmin", 5)):
        assert put(e, who, {"flag_review_threshold": value}).status_code == 200, who
    assert as_map(e.client.get(URL, headers=e.headers("sysadmin")))["flag_review_threshold"]["value"] == 5


# ------------------------------------------------------------------------------------------------ defaults and updates
def test_get_returns_every_key_with_the_code_defaults(adm):
    e = adm
    items = e.client.get(URL, headers=e.headers("admin")).json()["items"]
    assert [i["key"] for i in items] == KEYS
    m = {i["key"]: i for i in items}
    assert all(i["is_default"] and i["value"] == i["default"] and i["updated_by"] is None and i["updated_at"] is None and i["description"] for i in items)
    assert m["ai_confidence_threshold"]["value"] == 0.55 and m["duplicate_threshold"]["value"] == 0.8                              # the policy files' values
    assert m["sla_hours_by_priority"]["value"] == {"LOW": 168, "NORMAL": 72, "HIGH": 48, "URGENT": 24, "CRITICAL": 4}
    assert m["supported_languages"]["value"] == ["en", "hi", "mr", "hi-Latn"]
    assert m["notification_policy"]["value"] == {"email": False, "sms": False, "push": True, "escalation_emails": False}
    assert m["flag_review_threshold"]["value"] == 3


def test_put_stores_returns_and_audits_only_what_changed(adm):
    e = adm
    new = {"ai_confidence_threshold": 0.7, "sla_hours_by_priority": {"LOW": 240, "NORMAL": 96, "HIGH": 48, "URGENT": 12, "CRITICAL": 2},
           "supported_languages": ["en", "hi"], "notification_policy": {"email": True, "sms": False, "push": True, "escalation_emails": True}}
    r = put(e, "admin", {**new, "duplicate_threshold": 0.8}, reason="quarterly review")                  # duplicate_threshold equals the default: not a change
    assert r.status_code == 200, r.text
    m = as_map(r)
    assert [i["key"] for i in r.json()["items"]] == KEYS and all(m[k]["value"] == v and m[k]["is_default"] is False and m[k]["updated_by"] == e.users["admin"]["id"] for k, v in new.items())
    assert m["duplicate_threshold"]["is_default"] and m["duplicate_threshold"]["updated_at"] is None and m["flag_review_threshold"]["is_default"]
    assert as_map(e.client.get(URL, headers=e.headers("sysadmin")))["supported_languages"]["value"] == ["en", "hi"]                  # persisted, visible to the other admin role
    rows = audit_rows(e)
    assert sorted(r[2] for r in rows) == sorted(new) and all(r[0] == e.users["admin"]["id"] and r[1] == "system_settings" for r in rows)
    by_key = {r[2]: r for r in rows}
    assert by_key["ai_confidence_threshold"][3:] == ({"value": 0.55}, {"value": 0.7, "reason": "quarterly review"})
    assert by_key["supported_languages"][3]["value"] == ["en", "hi", "mr", "hi-Latn"] and by_key["supported_languages"][4]["value"] == ["en", "hi"]

    again = put(e, "admin", new)                                                                         # the same values again: no write, no audit
    assert again.status_code == 200 and len(audit_rows(e)) == len(rows)
    back = put(e, "sysadmin", {"ai_confidence_threshold": 0.55})                                        # back to the default value: stored, flagged as default
    assert as_map(back)["ai_confidence_threshold"]["is_default"] is True and as_map(back)["ai_confidence_threshold"]["updated_by"] == e.users["sysadmin"]["id"]
    assert audit_rows(e)[-1][3:] == ({"value": 0.7}, {"value": 0.55, "reason": None})
    with e.session_factory() as db:
        assert db.get(SystemSetting, "ai_confidence_threshold").value_json == 0.55


def test_integers_given_as_whole_floats_and_ints_as_thresholds_are_accepted(adm):
    e = adm
    r = put(e, "admin", {"duplicate_threshold": 1, "ai_confidence_threshold": 0, "flag_review_threshold": 7.0})
    assert r.status_code == 200 and (as_map(r)["duplicate_threshold"]["value"], as_map(r)["ai_confidence_threshold"]["value"], as_map(r)["flag_review_threshold"]["value"]) == (1.0, 0.0, 7)


# ------------------------------------------------------------------------------------------------ validation
BAD = [
    ("ai_confidence_threshold", 1.5), ("ai_confidence_threshold", -0.1), ("ai_confidence_threshold", "0.5"), ("ai_confidence_threshold", True), ("ai_confidence_threshold", None),
    ("duplicate_threshold", 0.49), ("duplicate_threshold", 1.01), ("duplicate_threshold", [0.8]),
    ("sla_hours_by_priority", {"LOW": 168, "NORMAL": 72, "HIGH": 48, "URGENT": 24}),                                              # CRITICAL missing
    ("sla_hours_by_priority", {"LOW": 168, "NORMAL": 72, "HIGH": 48, "URGENT": 24, "CRITICAL": 4, "EXTRA": 1}),
    ("sla_hours_by_priority", {"LOW": 168, "NORMAL": 72, "HIGH": 48, "URGENT": 72, "CRITICAL": 4}),                               # URGENT longer than HIGH
    ("sla_hours_by_priority", {"LOW": 168, "NORMAL": 72, "HIGH": 48, "URGENT": 24, "CRITICAL": 0}),
    ("sla_hours_by_priority", {"LOW": "168", "NORMAL": 72, "HIGH": 48, "URGENT": 24, "CRITICAL": 4}), ("sla_hours_by_priority", [168, 72]),
    ("supported_languages", []), ("supported_languages", ["hi", "mr"]), ("supported_languages", ["en", "en"]), ("supported_languages", ["en", "!!"]),
    ("supported_languages", ["en"] + [f"x{i}" for i in range(20)]), ("supported_languages", "en"),
    ("notification_policy", {"email": True, "sms": False, "push": True}), ("notification_policy", {"email": 1, "sms": False, "push": True, "escalation_emails": False}),
    ("notification_policy", {"email": True, "sms": False, "push": True, "escalation_emails": False, "whatsapp": True}),
    ("flag_review_threshold", 0), ("flag_review_threshold", 101), ("flag_review_threshold", 2.5), ("flag_review_threshold", True), ("flag_review_threshold", "3"),
]


@pytest.mark.parametrize("key, value", BAD, ids=[f"{k}={str(v)[:40]}" for k, v in BAD])
def test_invalid_values_are_rejected_with_the_offending_key_and_change_nothing(adm, key, value):
    e = adm
    r = put(e, "admin", {key: value})
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR" and [x["key"] for x in err["details"]["errors"]] == [key] and err["details"]["errors"][0]["message"]
    assert all(i["is_default"] for i in e.client.get(URL, headers=e.headers("admin")).json()["items"]) and audit_rows(e) == []


def test_one_bad_value_changes_nothing_and_unknown_keys_are_refused(adm):
    e = adm
    r = put(e, "admin", {"ai_confidence_threshold": 0.9, "flag_review_threshold": 0, "colour": "green"})
    errors = {x["key"]: x["message"] for x in r.json()["error"]["details"]["errors"]}
    assert r.status_code == 422 and set(errors) == {"flag_review_threshold", "colour"} and "unknown setting" in errors["colour"]
    assert as_map(e.client.get(URL, headers=e.headers("admin")))["ai_confidence_threshold"]["is_default"] and audit_rows(e) == []
    assert e.client.put(URL, headers=e.idem("admin"), json={"values": {}}).status_code == 422
    assert e.client.put(URL, headers=e.idem("admin"), json={}).status_code == 422
    assert e.client.put(URL, headers=e.headers("admin"), json={"values": {"flag_review_threshold": 4}}).json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_put_is_idempotent(adm):
    e, key = adm, str(uuid.uuid4())
    first, again = put(e, "admin", {"flag_review_threshold": 6}, key=key), put(e, "admin", {"flag_review_threshold": 6}, key=key)
    assert first.status_code == again.status_code == 200 and again.headers.get("idempotent-replayed") == "true" and first.json() == again.json()
    assert len(audit_rows(e)) == 1 and put(e, "admin", {"flag_review_threshold": 8}, key=key).status_code == 422                    # same key, other body


# ------------------------------------------------------------------------------------------------ the thresholds are really used
def test_ai_confidence_threshold_changes_what_intake_reports(adm):
    e = adm
    body = {"text": "Huge pothole outside the school gate, two bikes already fell", "location": e.where}

    def warnings():
        r = e.client.post("/api/v1/cases/intake/analyze", headers=e.headers("alice"), json=body)
        assert r.status_code == 200, r.text
        return [w for w in r.json()["warnings"] if w.startswith("LOW_CONFIDENCE")]
    assert warnings() == ["LOW_CONFIDENCE: confidence 0.00 below 0.55"]                                  # the default
    put(e, "admin", {"ai_confidence_threshold": 0.0})
    assert warnings() == []                                                                              # nothing is below 0 any more
    put(e, "admin", {"ai_confidence_threshold": 0.9})
    assert warnings() == ["LOW_CONFIDENCE: confidence 0.00 below 0.9"]                                   # applied at once, no restart


def test_duplicate_threshold_changes_the_fusion_recommendation(adm):
    e = adm
    first, second = create_case(e, "alice"), create_case(e, "bob")                                       # the same pothole reported twice: similarity 0.95

    def fusion():
        r = e.client.post(f"/api/v1/cases/{second['id']}/fusion/analyze", headers=e.headers("admin"))
        assert r.status_code == 200, r.text
        return r.json()["recommendation"], [m["case_id"] for m in r.json()["matches"]]
    assert fusion() == ("POSSIBLE_DUPLICATE", [first["id"]])                                             # default threshold 0.8
    put(e, "admin", {"duplicate_threshold": 0.99})
    assert fusion() == ("RELATED", [first["id"]])                                                        # stricter: the same match is only related
    put(e, "admin", {"duplicate_threshold": 0.9})
    assert fusion()[0] == "POSSIBLE_DUPLICATE"
    put(e, "admin", {"duplicate_threshold": 0.8})
    assert fusion()[0] == "POSSIBLE_DUPLICATE"


def test_applying_thresholds_never_leaks_into_the_shared_policy_or_other_gateways(adm):
    from backend.ai_gateway import get_gateway
    e = adm
    put(e, "admin", {"duplicate_threshold": 0.95, "ai_confidence_threshold": 0.3})
    create_case(e, "alice")
    gw = get_gateway()
    gw._apply_thresholds()
    assert gw.ai.fusion.policy["thresholds"]["possible_duplicate"] == 0.95 and gw.ai.policy.intake["low_confidence_threshold"] == 0.3
    assert load_fusion_policy()["thresholds"] == {"possible_duplicate": 0.8, "related": 0.5}              # the cached file contents are untouched
    assert gw.ai.fusion.policy is not load_fusion_policy()


def test_effective_thresholds_fall_back_to_the_defaults_when_the_database_cannot_be_read(adm, monkeypatch):
    e = adm
    put(e, "admin", {"duplicate_threshold": 0.9})
    assert settings_service.effective_thresholds()["duplicate_threshold"] == 0.9
    settings_service.invalidate_cache()

    def broken():
        raise RuntimeError("database down")
    monkeypatch.setattr("backend.db.session.session_scope", broken)
    assert settings_service.effective_thresholds() == {"ai_confidence_threshold": 0.55, "duplicate_threshold": 0.8}                 # the AI keeps answering


def test_a_changed_setting_reaches_a_process_that_cached_the_old_value_within_the_cache_time(adm, monkeypatch):
    e = adm
    assert settings_service.effective_thresholds()["duplicate_threshold"] == 0.8                          # cached
    with e.session_factory() as db:                                                                      # another process writes straight to the table
        db.add(SystemSetting(key="duplicate_threshold", value_json=0.97))
        db.commit()
    assert settings_service.effective_thresholds()["duplicate_threshold"] == 0.8                          # still inside the 5 s window
    monkeypatch.setattr(settings_service, "CACHE_SECONDS", 0.0)
    assert settings_service.effective_thresholds()["duplicate_threshold"] == 0.97
