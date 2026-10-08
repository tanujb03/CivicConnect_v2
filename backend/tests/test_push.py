"""Expo push delivery against a fake Expo server (httpx.MockTransport): no real push is ever sent."""
import logging
import threading
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.core.config import settings

SECRET = "expo-access-token-SECRET-value"


def tok(i) -> str:
    return f"ExponentPushToken[{i:022d}]"


class Expo:
    """A fake Expo: records every request; ``push`` / ``receipts`` are callables (json body -> (status, json[, headers])) or None for the all-ok default."""

    def __init__(self, push=None, receipts=None):
        self.push, self.receipts, self.sent, self.polled, self.headers = push, receipts, [], [], []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        import json
        data = json.loads(request.content)
        self.headers.append(dict(request.headers))
        if str(request.url) == settings.EXPO_RECEIPTS_URL:
            self.polled.append(data["ids"])
            fn = self.receipts or (lambda b: (200, {"data": {i: {"status": "ok"} for i in b["ids"]}}))
            res = fn(data)
        else:
            self.sent.append(data)
            fn = self.push or (lambda b: (200, {"data": [{"status": "ok", "id": f"rcpt-{m['data']['notification_id'][:8]}-{m['to'][-6:-1]}"} for m in b]}))
            res = fn(data)
        return httpx.Response(res[0], json=res[1], headers=res[2] if len(res) > 2 else None)

    @property
    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))

    @property
    def messages(self) -> list:
        return [m for batch in self.sent for m in batch]


@pytest.fixture
def world(env, monkeypatch):
    """Two citizens; alice has two devices, bob one. Helpers create notifications in a given push_status."""
    from backend.models import DeviceToken, Notification
    monkeypatch.setattr(settings, "EXPO_ACCESS_TOKEN", None)
    monkeypatch.setattr("backend.events.push_worker._last_receipts", None)
    alice, bob = env.make_user("citizen", "alice"), env.make_user("citizen", "bob")
    env.alice, env.bob = alice["id"], bob["id"]
    with env.session_factory() as db:
        for uid, i in ((alice["id"], 1), (alice["id"], 2), (bob["id"], 3)):
            db.add(DeviceToken(user_id=uid, platform="android", expo_push_token=tok(i)))
        db.commit()

    def add(user=None, n=1, status="PENDING", **payload):
        with env.session_factory() as db:
            ids = []
            for _ in range(n):
                row = Notification(user_id=user or env.bob, type="CASE_UPDATED", payload={"case_id": "c1", "title": "Title", "message": "Message", **payload}, push_status=status)
                db.add(row)
                db.flush()
                ids.append(row.id)
            db.commit()
            return ids

    def get(nid):
        with env.session_factory() as db:
            n = db.get(Notification, nid)
            return n.push_status, n.push_attempts, n.push_receipt_id, n.pushed_at

    def run(fn, *a, **kw):
        with env.session_factory() as db:
            out = fn(db, *a, **kw)
            db.commit()
            return out

    def revoked():
        with env.session_factory() as db:
            return {t.expo_push_token for t in db.query(DeviceToken).filter(DeviceToken.revoked_at.is_not(None))}

    env.add, env.get, env.run, env.revoked = add, get, run, revoked
    return env


def deliver(w, expo, **kw):
    from backend.services import push
    return w.run(push.deliver_pending, client=expo.client, **kw)


def test_success_sends_the_documented_message_and_stores_the_receipt(world):
    nid, = world.add(case_id="c9", title="Assigned", message="Your case moved")
    expo = Expo()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    stats = deliver(world, expo, now=now)
    assert stats["sent"] == 1 and stats["requests"] == 1 and stats["deferred"] == 0
    status, attempts, receipt, pushed_at = world.get(nid)
    assert status == "SENT" and attempts == 1 and receipt.startswith("rcpt-") and pushed_at == now
    m, = expo.messages
    assert m == {"to": tok(3), "title": "Assigned", "body": "Your case moved", "data": {"case_id": "c9", "type": "CASE_UPDATED", "notification_id": nid}, "sound": "default",
                 "channelId": "default"}
    h = expo.headers[0]
    assert h["accept"] == "application/json" and "gzip" in h["accept-encoding"] and h["content-type"] == "application/json" and "authorization" not in h
    assert deliver(world, expo)["selected"] == 0                                             # SENT rows are not picked again


def test_the_access_token_is_sent_only_when_configured(world, monkeypatch):
    world.add()
    monkeypatch.setattr(settings, "EXPO_ACCESS_TOKEN", SECRET)
    expo = Expo()
    deliver(world, expo)
    assert expo.headers[0]["authorization"] == f"Bearer {SECRET}"


def test_one_message_per_active_token_and_revoked_tokens_are_left_out(world):
    from backend.models import DeviceToken
    nid, = world.add(user=world.alice)
    with world.session_factory() as db:
        db.query(DeviceToken).filter(DeviceToken.expo_push_token == tok(2)).update({"revoked_at": datetime.now(timezone.utc)})
        db.commit()
    expo = Expo()
    assert deliver(world, expo)["sent"] == 1
    assert [m["to"] for m in expo.messages] == [tok(1)]
    both = world.add(user=world.alice)[0]
    with world.session_factory() as db:
        db.query(DeviceToken).update({"revoked_at": None})
        db.commit()
    expo2 = Expo()
    deliver(world, expo2)
    assert sorted(m["to"] for m in expo2.messages if m["data"]["notification_id"] == both) == [tok(1), tok(2)]
    assert len(world.get(both)[2].split(",")) == 2


def test_batches_hold_at_most_the_configured_size_up_to_100(world, monkeypatch):
    world.add(n=250)
    expo = Expo()
    stats = deliver(world, expo)
    assert stats["sent"] == 250 and [len(b) for b in expo.sent] == [100, 100, 50]
    world.add(n=7)
    monkeypatch.setattr(settings, "PUSH_BATCH_SIZE", 3)
    expo2 = Expo()
    deliver(world, expo2)
    assert [len(b) for b in expo2.sent] == [3, 3, 1]
    monkeypatch.setattr(settings, "PUSH_BATCH_SIZE", 500)                                    # never above Expo's limit of 100
    world.add(n=120)
    expo3 = Expo()
    deliver(world, expo3)
    assert [len(b) for b in expo3.sent] == [100, 20]


def test_the_oldest_rows_go_first_and_limit_applies(world):
    first = world.add()[0]
    world.add(n=3)
    expo = Expo()
    assert deliver(world, expo, limit=1)["selected"] == 1
    assert expo.messages[0]["data"]["notification_id"] == first


def test_partial_failure_keeps_the_failed_one_pending_then_fails_it_after_three_attempts(world):
    good, bad = world.add()[0], world.add()[0]
    state = {"fail": True}

    def push(batch):
        return 200, {"data": [{"status": "error", "message": "x", "details": {"error": "MessageRateExceeded"}}
                              if state["fail"] and m["data"]["notification_id"] == bad else {"status": "ok", "id": "r-" + m["data"]["notification_id"][:6]} for m in batch]}

    expo = Expo(push=push)
    s1 = deliver(world, expo)
    assert s1["sent"] == 1 and s1["deferred"] == 1 and world.get(good)[0] == "SENT" and world.get(bad)[:2] == ("PENDING", 1)
    assert deliver(world, expo)["deferred"] == 1 and world.get(bad)[:2] == ("PENDING", 2)
    s3 = deliver(world, expo)
    assert s3["failed"] == 1 and world.get(bad)[:2] == ("FAILED", 3)
    assert deliver(world, expo)["selected"] == 0                                             # FAILED is final
    other = world.add()[0]
    state["fail"] = False                                                                    # and recovery works for a fresh row
    deliver(world, expo)
    assert world.get(other)[0] == "SENT"


def test_a_row_with_one_ok_ticket_is_sent_even_if_its_other_device_failed(world):
    nid, = world.add(user=world.alice)
    expo = Expo(push=lambda b: (200, {"data": [{"status": "ok", "id": "r1"}, {"status": "error", "details": {"error": "MessageTooBig"}}]}))
    stats = deliver(world, expo)
    assert stats["sent"] == 1 and world.get(nid)[0] == "SENT" and world.get(nid)[2].startswith("r1~")


def test_device_not_registered_revokes_the_token_immediately(world):
    both, = world.add(user=world.alice)
    only, = world.add()
    expo = Expo(push=lambda b: (200, {"data": [{"status": "error", "message": "gone", "details": {"error": "DeviceNotRegistered"}}
                                               if m["to"] in (tok(2), tok(3)) else {"status": "ok", "id": "r-" + m["to"][-4:]} for m in b]}))
    stats = deliver(world, expo)
    assert stats["revoked"] == 2 and world.revoked() == {tok(2), tok(3)}
    assert world.get(both)[0] == "SENT"                                                      # alice's other device took it
    assert world.get(only)[:2] == ("SKIPPED", 1)                                             # bob has nobody left
    nxt = world.add()[0]
    expo2 = Expo()
    deliver(world, expo2)
    assert expo2.sent == [] and world.get(nxt)[0] == "SKIPPED"                               # no active token any more: nothing is sent


def test_no_active_tokens_and_a_switched_off_policy_skip_without_any_request(world):
    from backend.models import SystemSetting
    ghost = world.make_user("citizen", "ghost")["id"]
    nid, = world.add(user=ghost)
    expo = Expo()
    assert deliver(world, expo)["skipped"] == 1 and expo.sent == [] and world.get(nid)[0] == "SKIPPED"
    kept = world.add()[0]
    with world.session_factory() as db:
        db.add(SystemSetting(key="notification_policy", value_json={"email": False, "sms": False, "push": False, "escalation_emails": False}))
        db.commit()
    assert deliver(world, expo)["skipped"] == 1 and expo.sent == [] and world.get(kept)[0] == "SKIPPED"


def test_a_transient_failure_stops_the_pass_reports_retry_after_and_charges_nothing(world):
    world.add(n=250)
    expo = Expo(push=lambda b: (429, {"errors": []}, {"Retry-After": "7"}))
    stats = deliver(world, expo)
    assert len(expo.sent) == 1 and stats["request_failures"] == 1 and stats["retry_after_s"] == 7.0 and stats["sent"] == 0 and stats["deferred"] == 100 and not stats["config_error"]
    from backend.models import Notification
    with world.session_factory() as db:
        assert {(n.push_status, n.push_attempts) for n in db.query(Notification)} == {("PENDING", 0)}


def test_a_fifteen_second_outage_never_fails_a_row(world):
    """Many passes in a short outage (503, 429, timeouts, connection errors, unreadable answers) cost no attempt; when Expo is back everything is sent."""
    ids = world.add(n=100)
    from backend.services import push

    def boom(request):
        raise httpx.ReadTimeout("slow")
    outage = [Expo(push=lambda b: (503, {})), Expo(push=lambda b: (429, {})), Expo(push=lambda b: (200, {"data": []})), Expo(push=lambda b: (200, {"nope": 1}))]
    for i in range(12):
        if i % 5 == 4:
            stats = world.run(push.deliver_pending, client=httpx.Client(transport=httpx.MockTransport(boom)))
        else:
            stats = deliver(world, outage[i % 4])
        assert stats["request_failures"] == 1 and "error" not in stats
    assert {world.get(n)[:2] for n in ids} == {("PENDING", 0)}
    ok = Expo()
    assert deliver(world, ok)["sent"] == 100
    assert {world.get(n)[0] for n in ids} == {"SENT"}


def test_bad_credentials_leave_rows_pending_log_one_error_and_back_off_five_minutes(world, monkeypatch, caplog):
    from backend.events import push_worker
    monkeypatch.setattr(settings, "EXPO_ACCESS_TOKEN", SECRET)
    ids = world.add(n=150)
    expo = Expo(push=lambda b: (401, {"errors": [{"code": "UNAUTHORIZED", "message": SECRET}]}))
    with caplog.at_level(logging.DEBUG):
        stats = deliver(world, expo)
    assert len(expo.sent) == 1 and stats["config_error"] is True and stats["request_failures"] == 0 and stats["sent"] == 0
    assert {world.get(n)[:2] for n in ids} == {("PENDING", 0)}
    assert len([r for r in caplog.records if r.levelno >= logging.ERROR]) == 1 and SECRET not in caplog.text and tok(3) not in caplog.text
    assert push_worker.next_delay({"deliver": stats}, 0)[0] == 300.0
    assert deliver(world, Expo(push=lambda b: (403, {})))["config_error"] is True


def test_a_400_is_bisected_so_only_the_rejected_message_counts_an_attempt(world):
    ids = world.add(n=99) + world.add(n=1, title="BAD")

    def push(batch):
        if any(m["title"] == "BAD" for m in batch):
            return 400, {"errors": [{"code": "VALIDATION_ERROR"}]}
        return 200, {"data": [{"status": "ok", "id": "r-" + m["data"]["notification_id"][:8]} for m in batch]}

    expo = Expo(push=push)
    stats = deliver(world, expo)
    assert stats["sent"] == 99 and stats["deferred"] == 1 and stats["request_failures"] == 0 and 1 < stats["requests"] < 30
    assert [world.get(n)[0] for n in ids[:99]] == ["SENT"] * 99 and world.get(ids[99])[:2] == ("PENDING", 1)
    deliver(world, expo)
    assert deliver(world, expo)["failed"] == 1 and world.get(ids[99])[:2] == ("FAILED", 3)
    assert {world.get(n)[1] for n in ids[:99]} == {1}                                        # the healthy ones were not re-sent


def test_tokens_of_two_expo_projects_in_one_request_are_split_by_bisection(world):
    from backend.models import DeviceToken, Notification
    users = [world.make_user("citizen", f"u{i}")["id"] for i in range(20)]                   # half of them on another Expo "project"
    with world.session_factory() as db:
        ids = []
        for i, u in enumerate(users):
            db.add(DeviceToken(user_id=u, platform="ios", expo_push_token=f"ExponentPushToken[{'AB'[i % 2]}{i:021d}]"))
            n = Notification(user_id=u, type="CASE_UPDATED", payload={"title": "T", "message": "M"}, push_status="PENDING")
            db.add(n)
            db.flush()
            ids.append(n.id)
        db.commit()

    def push(batch):
        if len({m["to"][len("ExponentPushToken["):][0] for m in batch}) > 1:
            return 400, {"errors": [{"code": "PUSH_TOO_MANY_EXPERIENCE_IDS", "message": "mixed projects"}]}
        return 200, {"data": [{"status": "ok", "id": "r-" + m["data"]["notification_id"][:8]} for m in batch]}

    stats = deliver(world, Expo(push=push))
    assert stats["sent"] == 20 and {world.get(n)[:2] for n in ids} == {("SENT", 1)}


def test_a_row_with_one_ok_device_and_one_transient_failure_stays_pending_at_no_cost(world):
    nid, = world.add(user=world.alice)

    def push(batch):
        if len(batch) > 1:
            return 400, {"errors": []}                                                       # force bisection so the two devices are sent apart
        return (200, {"data": [{"status": "ok", "id": "r1"}]}) if batch[0]["to"] == tok(1) else (503, {})

    stats = deliver(world, Expo(push=push))
    assert stats["sent"] == 0 and stats["deferred"] == 1 and stats["request_failures"] == 1 and world.get(nid)[:3] == ("PENDING", 0, None)


def test_all_messages_of_one_notification_share_a_batch_and_each_batch_is_committed_before_the_next(world, monkeypatch):
    from backend.models import Notification
    monkeypatch.setattr(settings, "PUSH_BATCH_SIZE", 3)
    ids = world.add(user=world.alice, n=3)                                                   # two devices each: batches of 2 messages, never split
    seen_states = []

    def push(batch):
        with world.session_factory() as other:                                              # another connection sees only committed data
            seen_states.append(sorted(n.push_status for n in other.query(Notification).filter(Notification.id.in_(ids))))
        return 200, {"data": [{"status": "ok", "id": "r-" + m["data"]["notification_id"][:6] + m["to"][-4:-1]} for m in batch]}

    expo = Expo(push=push)
    stats = deliver(world, expo)
    assert stats["sent"] == 3 and [len(b) for b in expo.sent] == [2, 2, 2]
    for b in expo.sent:
        assert len({m["data"]["notification_id"] for m in b}) == 1 and len({m["to"] for m in b}) == 2
    assert seen_states == [["PENDING"] * 3, ["PENDING", "PENDING", "SENT"], ["PENDING", "SENT", "SENT"]]


def test_a_second_pass_after_the_first_does_not_send_a_row_twice(world):
    world.add(n=5)
    first, second = Expo(), Expo()
    deliver(world, first)
    deliver(world, second)
    assert len(first.messages) == 5 and second.messages == []


def test_pending_rows_are_locked_with_skip_locked_on_postgresql_only():
    from sqlalchemy.dialects import postgresql, sqlite

    from backend.services import push
    assert "FOR UPDATE SKIP LOCKED" in str(push.pending_query("postgresql", 10, {"x"}).compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" not in str(push.pending_query("sqlite", 10).compile(dialect=sqlite.dialect()))


def test_inactive_users_are_skipped_and_their_tokens_unused(world):
    from backend.models import User
    nid, = world.add()
    with world.session_factory() as db:
        db.get(User, world.bob).is_active = False
        db.commit()
    expo = Expo()
    stats = deliver(world, expo)
    assert stats["skipped"] == 1 and expo.sent == [] and world.get(nid)[0] == "SKIPPED"


def test_receipt_ids_are_kept_whole_and_the_oldest_are_dropped_with_one_warning(world, caplog):
    from backend.models import DeviceToken
    with world.session_factory() as db:
        for i in (4, 5):
            db.add(DeviceToken(user_id=world.alice, platform="ios", expo_push_token=tok(i)))
        db.commit()
    nid, = world.add(user=world.alice)
    uuid_ids = [f"{i:08d}-aaaa-bbbb-cccc-dddddddddddd" for i in range(4)]                  # 36 characters like Expo's
    expo = Expo(push=lambda b: (200, {"data": [{"status": "ok", "id": uuid_ids[i]} for i in range(len(b))]}))
    with caplog.at_level(logging.DEBUG):
        stats = deliver(world, expo)
    value = world.get(nid)[2]
    entries = value.split(",")
    assert stats["sent"] == 1 and len(value) <= 128 and len(entries) == 3 and stats["receipt_overflow"] == 1
    assert [e.split("~")[0] for e in entries] == uuid_ids[1:]                                # ids intact, the OLDEST one dropped
    assert len([r for r in caplog.records if "did not fit" in r.getMessage()]) == 1


def test_a_long_title_is_cut_to_100_characters(world):
    world.add(title="T" * 300)
    expo = Expo()
    deliver(world, expo)
    assert len(expo.messages[0]["title"]) == 100 and expo.messages[0]["title"].endswith("...")


def test_title_and_body_fall_back_and_the_body_is_truncated(world):
    from backend.models import Notification
    with world.session_factory() as db:
        db.add(Notification(user_id=world.bob, type="CASE_RESOLVED", payload={}, push_status="PENDING"))
        db.add(Notification(user_id=world.bob, type="CASE_RESOLVED", payload={"title": "T", "message": "x" * 400, "case_id": None}, push_status="PENDING"))
        db.commit()
    expo = Expo()
    deliver(world, expo)
    plain, long = [next(m for m in expo.messages if m["title"] == t) for t in ("CivicConnect", "T")]
    assert plain["title"] == "CivicConnect" and plain["body"] == "You have a new update." and plain["data"]["case_id"] is None
    assert long["title"] == "T" and len(long["body"]) == 178 and long["body"].endswith("...")


def test_a_crash_inside_the_pass_changes_nothing_and_is_logged_without_secrets(world, monkeypatch, caplog):
    from backend.services import push
    monkeypatch.setattr(settings, "EXPO_ACCESS_TOKEN", SECRET)
    nid, = world.add()
    monkeypatch.setattr(push, "_send", lambda *a, **k: (_ for _ in ()).throw(RuntimeError(f"{SECRET} {tok(3)}")))
    with caplog.at_level(logging.DEBUG):
        stats = deliver(world, Expo())
    assert stats["error"] == "RuntimeError" and world.get(nid)[:2] == ("PENDING", 0)
    assert SECRET not in caplog.text and tok(3) not in caplog.text


def test_logs_never_hold_the_access_token_or_a_full_push_token(world, monkeypatch, caplog):
    monkeypatch.setattr(settings, "EXPO_ACCESS_TOKEN", SECRET)
    world.add(), world.add(user=world.alice)
    with caplog.at_level(logging.DEBUG):
        deliver(world, Expo(push=lambda b: (500, {})))                                       # whole request fails
        deliver(world, Expo(push=lambda b: (200, {"data": [{"status": "error", "details": {"error": "InvalidCredentials"}} for _ in b]})))
        deliver(world, Expo(push=lambda b: (200, {"data": [{"status": "error", "details": {"error": "DeviceNotRegistered"}} for _ in b]})))
    assert caplog.text and SECRET not in caplog.text
    assert all(tok(i) not in caplog.text for i in (1, 2, 3)) and tok(3)[:14] in caplog.text


# ------------------------------------------------------------------------------------------------ receipts
def sent(world, user=None, receipt="r1", age_min=60, token_idx=3, **kw):
    """A SENT notification whose receipt id carries the fingerprint of tok(token_idx)."""
    from backend.models import Notification
    from backend.services import push
    with world.session_factory() as db:
        n = Notification(user_id=user or world.bob, type="CASE_UPDATED", payload={}, push_status="SENT", pushed_at=datetime.now(timezone.utc) - timedelta(minutes=age_min),
                         push_receipt_id=f"{receipt}~{push._tag(tok(token_idx))}", **kw)
        db.add(n)
        db.commit()
        return n.id


def poll(world, expo, **kw):
    from backend.services import push
    return world.run(push.check_receipts, client=expo.client, **kw)


def test_receipt_device_not_registered_revokes_only_the_matching_token_and_clears_the_id(world):
    nid = sent(world, user=world.alice, receipt="r-gone", token_idx=2)
    ok = sent(world, receipt="r-ok")
    expo = Expo(receipts=lambda b: (200, {"data": {"r-gone": {"status": "error", "message": "m", "details": {"error": "DeviceNotRegistered"}}, "r-ok": {"status": "ok"}}}))
    stats = poll(world, expo)
    assert stats["resolved"] == 2 and stats["revoked"] == 1 and world.revoked() == {tok(2)}
    assert world.get(nid)[2] is None and world.get(ok)[2] is None and world.get(nid)[0] == "SENT"
    assert poll(world, expo)["checked"] == 0                                                 # nothing left to ask


def test_receipts_younger_than_the_minimum_age_are_not_requested(world):
    sent(world, age_min=5)
    expo = Expo()
    assert poll(world, expo)["checked"] == 0 and expo.polled == []                           # default: 15 minutes
    assert poll(world, expo, min_age=timedelta(0))["checked"] == 1


def test_receipt_requests_hold_at_most_300_ids(world):
    from backend.models import Notification
    with world.session_factory() as db:
        db.add_all(Notification(user_id=world.bob, type="CASE_UPDATED", payload={}, push_status="SENT", pushed_at=datetime.now(timezone.utc) - timedelta(hours=1), push_receipt_id=f"r{i}")
                   for i in range(650))
        db.commit()
    expo = Expo()
    stats = poll(world, expo, limit=1000)
    assert [len(c) for c in expo.polled] == [300, 300, 50] and stats["resolved"] == 650


def test_receipts_not_ready_yet_stay_and_forgotten_ones_are_dropped_after_24_hours(world):
    fresh, old = sent(world, receipt="r-new", age_min=60), sent(world, receipt="r-old", age_min=60 * 25)
    expo = Expo(receipts=lambda b: (200, {"data": {}}))
    stats = poll(world, expo)
    assert stats["expired"] == 1 and world.get(fresh)[2].startswith("r-new~") and world.get(old)[2] is None


def test_a_failed_receipt_request_keeps_every_id_and_other_receipt_errors_do_not_revoke(world):
    old = sent(world, receipt="r-old", age_min=60 * 25)
    stats = poll(world, Expo(receipts=lambda b: (500, {})))
    assert stats["request_failures"] == 1 and world.get(old)[2].startswith("r-old~")         # unknown is not expired
    odd = sent(world, receipt="r-odd")
    stats = poll(world, Expo(receipts=lambda b: (200, {"data": {"r-odd": {"status": "error", "details": {"error": "MessageRateExceeded"}}, "r-old": {"status": "ok"}}})))
    assert stats["receipt_errors"] == 1 and world.revoked() == set() and world.get(odd)[2] is None


def test_receipt_pass_never_raises_and_logs_no_secret(world, monkeypatch, caplog):
    monkeypatch.setattr(settings, "EXPO_ACCESS_TOKEN", SECRET)
    sent(world)
    raising = Expo(receipts=lambda b: (_ for _ in ()).throw(RuntimeError(SECRET)))
    with caplog.at_level(logging.DEBUG):
        stats = poll(world, raising)
        stats2 = poll(world, Expo(receipts=lambda b: (200, {"data": {"r1": {"status": "error", "details": {"error": "DeviceNotRegistered"}}}})))
    assert stats["request_failures"] == 1 and "error" not in stats and stats2["revoked"] == 1
    assert SECRET not in caplog.text and tok(3) not in caplog.text


# ------------------------------------------------------------------------------------------------ worker
def test_run_once_delivers_checks_receipts_and_commits_in_its_own_session(world):
    from backend.events import push_worker
    nid, = world.add()
    result = push_worker.run_once(world.session_factory, Expo().client)
    assert result["deliver"]["sent"] == 1 and "error" not in result and world.get(nid)[0] == "SENT"


def test_receipts_are_polled_at_most_once_per_five_minutes(world, monkeypatch):
    from backend.events import push_worker
    sent(world)
    expo = Expo(receipts=lambda b: (200, {"data": {}}))
    first = push_worker.run_once(world.session_factory, expo.client)
    second = push_worker.run_once(world.session_factory, expo.client)
    assert first["receipts"]["checked"] == 1 and second["receipts"] == {"skipped": True} and len(expo.polled) == 1
    monkeypatch.setattr(push_worker, "_last_receipts", push_worker.time.monotonic() - push_worker.RECEIPT_EVERY_S - 1)
    assert push_worker.run_once(world.session_factory, expo.client)["receipts"]["checked"] == 1


def test_run_once_swallows_every_exception(world, caplog):
    from backend.events import push_worker

    def broken():
        raise RuntimeError(f"db down {SECRET}")
    with caplog.at_level(logging.DEBUG):
        assert push_worker.run_once(broken, Expo().client) == {"error": "RuntimeError"}
    assert SECRET not in caplog.text


def test_backoff_doubles_on_request_failures_honours_retry_after_and_resets(monkeypatch):
    from backend.events import push_worker
    monkeypatch.setattr(settings, "PUSH_WORKER_INTERVAL_S", 1.0)
    bad = {"deliver": {"request_failures": 1, "retry_after_s": 0.0}}
    delays, n = [], 0
    for _ in range(11):
        d, n = push_worker.next_delay(bad, n)
        delays.append(d)
    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 300.0, 300.0] and n == 11
    assert push_worker.next_delay({"deliver": {"request_failures": 1, "retry_after_s": 90.0}}, 0)[0] == 90.0
    assert push_worker.next_delay({"error": "X"}, 0) == (1.0, 1)
    assert push_worker.next_delay({"deliver": {"sent": 3}}, 5) == (1.0, 0)


def test_the_worker_thread_is_a_daemon_that_loops_run_once_until_stopped(monkeypatch):
    from backend.events import push_worker
    stop, calls = threading.Event(), []
    monkeypatch.setattr(settings, "PUSH_WORKER_INTERVAL_S", 0.01)
    monkeypatch.setattr(push_worker, "run_once", lambda *a, **k: (calls.append(1), stop.set() if len(calls) >= 3 else None, {})[2])
    monkeypatch.setattr(push_worker, "_thread", None)
    t = push_worker.start_push_worker(stop)
    assert t.daemon
    t.join(5)
    assert len(calls) >= 3 and not t.is_alive()


def test_starting_the_worker_twice_keeps_one_thread(monkeypatch):
    from backend.events import push_worker
    gate = threading.Event()
    running = threading.Thread(target=gate.wait, daemon=True)
    running.start()
    monkeypatch.setattr(push_worker, "_thread", running)
    try:
        assert push_worker.start_push_worker() is running
    finally:
        gate.set()
