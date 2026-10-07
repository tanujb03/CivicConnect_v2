"""Notification text for status events from fixed en / hi / mr templates, selected by the RECIPIENT's preferred_language, with no LLM involved; docs/I18N_REVIEW.md lists the
hi / mr strings for native-speaker review and is kept in sync with the templates by a test."""
from __future__ import annotations

import re

import pytest

from backend.scripts import generate_i18n_review as review
from backend.services import i18n
from backend.tests.helpers import create_case
from backend.tests.test_api_workflow import triage_and_assign

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
STATUS_KEYS = ["assigned", "work_order_created", "in_progress", "awaiting_verification", "resolved", "reopened", "rejected"]
STABLE_KEYS = ["case.status.assigned", "case.status.work_order_created", "case.status.in_progress", "case.status.awaiting_verification", "case.status.resolved",
               "case.status.reopened", "case.status.rejected", "case.contributor_added", "staff.case.reopened_by_verification", "staff.case.partial_fix", "incident.created",
               "work_order.assigned"]


# ---- the templates themselves ---------------------------------------------------------------------------------------------------------------------------------
def test_the_template_keys_are_a_stable_contract():
    assert list(i18n.TEMPLATES) == STABLE_KEYS                  # renaming or dropping a key breaks clients: add new keys instead


def test_every_key_has_en_hi_and_mr_with_the_same_placeholders():
    for key, by_lang in i18n.TEMPLATES.items():
        assert set(by_lang) == set(i18n.SUPPORTED), key
        for part in (0, 1):
            assert len({frozenset(i18n.placeholders(by_lang[lang][part])) for lang in i18n.SUPPORTED}) == 1, (key, part)
        for lang in i18n.SUPPORTED:
            title, message = by_lang[lang]
            assert title.strip() and message.strip(), (key, lang)
            assert bool(DEVANAGARI.search(title)) == (lang != "en"), (key, lang)            # hi / mr are Devanagari, en is not
            assert bool(DEVANAGARI.search(message)) == (lang != "en") or message == "{instructions}", (key, lang)     # the work-order message is the instructions as typed
        for lang in ("hi", "mr"):
            assert by_lang[lang] != by_lang["en"]


def test_every_status_that_notifies_the_reporter_has_a_template():
    from backend.services.workflow import NOTIFY_STATES
    assert {f"case.status.{s.lower()}" for s in NOTIFY_STATES} <= set(i18n.TEMPLATES)


@pytest.mark.parametrize("code,expected", [("en", "en"), ("hi", "hi"), ("mr", "mr"), ("hi-IN", "hi"), ("MR_in", "mr"), ("Hi", "hi"), ("ta", "en"), ("hi-Latn", "hi"), ("", "en"), (None, "en"), ("xx-yy", "en")])
def test_language_selection_falls_back_to_english(code, expected):
    assert i18n.normalize_language(code) == expected


def test_render_fills_placeholders_adds_the_reason_in_the_recipients_language_and_never_raises():
    assert i18n.render("case.status.rejected", "hi", {"case_number": "CC-1", "reason": "डुप्लिकेट"}) == ("शिकायत CC-1: अस्वीकृत", "आपकी शिकायत स्वीकार नहीं की जा सकी। कारण: डुप्लिकेट", "hi")
    assert i18n.render("case.status.rejected", "mr", {"case_number": "CC-1"}) == ("तक्रार CC-1: नाकारली", "तुमची तक्रार स्वीकारता आली नाही.", "mr")
    assert i18n.render("case.status.rejected", "ta", {"case_number": "CC-1", "reason": "dup"}) == ("Case CC-1: Rejected", "Your report could not be accepted. Reason: dup", "en")
    assert i18n.render("no.such.key", "hi", {}) is None
    title, message, _ = i18n.render("work_order.assigned", "mr", {"case_number": "CC-2"})                          # a missing parameter renders empty, not as "{instructions}"
    assert "{" not in title + message
    tricky = i18n.render("incident.created", "hi", {"title": "Flood {case_number} {0} {x.y}"})                      # user text is a VALUE, never re-interpreted as a template
    assert tricky[0] == "घटना: Flood {case_number} {0} {x.y}"


def test_the_review_document_section_is_current_and_lists_every_hindi_and_marathi_string():
    from backend.services.i18n import TEMPLATES
    text = review.OUT.read_text(encoding="utf-8")
    block = review.block_of(text)
    assert block is not None and block == review.render_block(), "docs/I18N_REVIEW.md is stale: run python -m backend.scripts.generate_i18n_review"
    assert review.merged(text) == text                                                              # idempotent
    assert "NOT REVIEWED" in block and "native speaker" in block
    for key, by_lang in TEMPLATES.items():
        for lang in ("hi", "mr"):
            assert f"| `{key}` |" in block and by_lang[lang][0] in block and by_lang[lang][1] in block
    assert block.count("☐") == len(TEMPLATES) * 2


def test_regenerating_replaces_only_its_own_block_and_keeps_the_rest_of_the_shared_document():
    other = "# Native-speaker review of the gold set\n\n- [ ] row 1 fix:\n"
    first = review.merged(other)
    assert first.startswith(other) and review.block_of(first) == review.render_block()                # appended after the existing content
    edited = first.replace("# Native-speaker review of the gold set", "# Edited title") + "\nNotes added later.\n"
    again = review.merged(edited)
    assert again.startswith("# Edited title") and again.endswith("Notes added later.\n") and again.count(review.BEGIN) == 1       # their edits survive, ours is refreshed in place
    assert review.merged("") == review.render_block()


# ---- end to end: the recipient's language decides ---------------------------------------------------------------------------------------------------------------
def set_language(e, who, code):
    from backend.models import User
    with e.session_factory() as db:
        db.get(User, e.users[who]["id"]).preferred_language = code
        db.commit()


def notes(e, who):
    return e.client.get("/api/v1/me/notifications?limit=50", headers=e.headers(who)).json()["items"]


def test_each_reporter_is_told_about_a_rejection_in_their_own_language(staffed):
    e = staffed
    for who, code in (("alice", "hi"), ("bob", "mr")):
        set_language(e, who, code)
    e.make_user("citizen", "carol")                                                          # default: en
    e.make_user("citizen", "dina")
    set_language(e, "dina", "ta")                                                            # no templates: English
    got = {}
    for who in ("alice", "bob", "carol", "dina"):
        c = create_case(e, who, client_case_id=f"c-{who}")
        r = e.client.post(f"/api/v1/cases/{c['id']}/reject", headers=e.idem("roads_op"), json={"reason": "duplicate of an open complaint"})
        assert r.status_code == 200
        [n] = [n for n in notes(e, who) if n["payload"].get("status") == "REJECTED"]
        got[who] = (c["case_number"], n)
    no, n = got["alice"]
    assert n["type"] == "CASE_UPDATED" and n["payload"]["template"] == "case.status.rejected" and n["payload"]["language"] == "hi"
    assert n["payload"]["title"] == f"शिकायत {no}: अस्वीकृत" and n["payload"]["message"] == "आपकी शिकायत स्वीकार नहीं की जा सकी। कारण: duplicate of an open complaint"
    assert n["payload"]["params"] == {"case_number": no, "reason": "duplicate of an open complaint"} and n["payload"]["status"] == "REJECTED"      # existing payload keys kept
    no, n = got["bob"]
    assert n["payload"]["language"] == "mr" and n["payload"]["title"] == f"तक्रार {no}: नाकारली"
    for who in ("carol", "dina"):
        no, n = got[who]
        assert n["payload"]["language"] == "en" and n["payload"]["title"] == f"Case {no}: Rejected" and n["payload"]["message"].endswith("Reason: duplicate of an open complaint")


def test_every_status_event_renders_in_each_language_with_nothing_left_to_fill(staffed):
    from backend.models import CivicCase
    from backend.services.workflow import transition
    e = staffed
    expected = {}
    for who, code in (("alice", "hi"), ("bob", "mr")):
        set_language(e, who, code)
    e.make_user("citizen", "carol")
    for who, code in (("alice", "hi"), ("bob", "mr"), ("carol", "en")):
        c = create_case(e, who, client_case_id=f"k-{who}")
        with e.session_factory() as db:
            case = db.get(CivicCase, c["id"])
            for state in ("ASSIGNED", "WORK_ORDER_CREATED", "IN_PROGRESS", "RESOLUTION_SUBMITTED", "AWAITING_VERIFICATION", "VERIFIED", "RESOLVED", "REOPENED"):
                transition(db, case, state, actor_id=None, actor_role="SYSTEM", reason="please check again" if state == "REOPENED" else None)
            db.commit()
        expected[who] = (code, c["case_number"])
    for who, (code, number) in expected.items():
        shown = {n["payload"]["status"]: n["payload"] for n in notes(e, who) if "template" in n["payload"]}
        assert set(shown) == {"ASSIGNED", "WORK_ORDER_CREATED", "IN_PROGRESS", "AWAITING_VERIFICATION", "RESOLVED", "REOPENED"}      # RESOLUTION_SUBMITTED / VERIFIED are not news
        for status, p in shown.items():
            want = i18n.render(f"case.status.{status.lower()}", code, {"case_number": number, "reason": "please check again" if status == "REOPENED" else ""})
            assert (p["title"], p["message"], p["language"]) == want and "{" not in p["title"] + p["message"] and number in p["title"]
        assert bool(DEVANAGARI.search(shown["RESOLVED"]["title"])) == (code != "en")


def test_other_notifications_use_the_recipients_language_too(staffed):
    e = staffed
    set_language(e, "roads_worker", "mr")
    c = create_case(e, "alice")
    triage_and_assign(e, c)
    r = e.client.post(f"/api/v1/cases/{c['id']}/work-orders", headers=e.idem("roads_op"), json={"assignee_id": e.users["roads_worker"]["id"], "instructions": "Fill the pothole today"})
    assert r.status_code == 201, r.text
    [n] = [n for n in notes(e, "roads_worker") if n["type"] == "WORK_ORDER_ASSIGNED"]
    assert n["payload"]["language"] == "mr" and n["payload"]["title"] == f"तक्रार {c['case_number']} साठी नवीन कामाचा आदेश" and n["payload"]["message"] == "Fill the pothole today"
    e.make_user("citizen", "carol")
    set_language(e, "carol", "hi")
    r = e.client.post(f"/api/v1/cases/{c['id']}/contributors", headers=e.idem("alice"), json={"user_id": e.users["carol"]["id"]})
    assert r.status_code in (200, 201), r.text
    [n] = [n for n in notes(e, "carol") if n["payload"].get("template") == "case.contributor_added"]
    assert n["payload"]["title"] == f"आपको शिकायत {c['case_number']} में जोड़ा गया"


def test_notifications_never_call_a_model(staffed):
    from ai.inference.providers.fake import FakeProvider
    from backend.tests.ai_helpers import install
    e = staffed
    p = FakeProvider()
    install(p)
    set_language(e, "alice", "hi")
    c = create_case(e, "alice")
    e.client.post(f"/api/v1/cases/{c['id']}/reject", headers=e.idem("roads_op"), json={"reason": "duplicate"})
    assert [n for n in notes(e, "alice") if n["payload"].get("language") == "hi"]
    assert not [call for call in p.calls if call[0] in ("structured", "transcribe", "plan_tools")]               # no completion / translation call
