"""Redis Streams publisher (events architecture, plan phase D). Entirely unit-level: Redis is mocked, no live server is needed.

(Originally Parth's test_phase_d.py; the sync-endpoint tests moved to test_api_sync.py when /sync became the real §51A.16 endpoint, and the module level
``dependency_overrides`` was removed because it leaked into every other test.)
"""
import logging
import os
import threading
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest
import redis as redis_lib


@pytest.fixture(autouse=True)
def _fresh_redis_state():
    """The publisher remembers a failed connection for 30 s (so requests do not each wait for the timeout); every test here starts from a clean slate."""
    import backend.events.publisher as pub
    import backend.events.workers as workers
    pub._redis_client, pub._redis_down_until, workers._worker_client = None, 0.0, None
    yield
    pub._redis_client, pub._redis_down_until, workers._worker_client = None, 0.0, None


# ══════════════════════════════════════════════════════════════════════════════
# 1. publisher.get_redis — graceful degradation
# ══════════════════════════════════════════════════════════════════════════════
class TestGetRedis:
    def test_returns_none_when_redis_unavailable(self):
        """If Redis is unreachable, get_redis() must return None, not raise."""
        import backend.events.publisher as pub
        pub._redis_client = None  # reset singleton

        with patch("backend.events.publisher.redis_lib.from_url") as mock_from_url:
            mock_from_url.return_value.ping.side_effect = Exception("Connection refused")
            result = pub.get_redis()

        assert result is None

    def test_returns_client_when_redis_available(self):
        import backend.events.publisher as pub
        pub._redis_client = None

        fake_client = MagicMock()
        fake_client.ping.return_value = True

        with patch("backend.events.publisher.redis_lib.from_url", return_value=fake_client):
            result = pub.get_redis()

        assert result is fake_client


# ══════════════════════════════════════════════════════════════════════════════
# 2. publish() — core serialisation and error handling
# ══════════════════════════════════════════════════════════════════════════════
class TestPublish:
    def test_publish_returns_none_when_redis_unavailable(self):
        from backend.events.publisher import publish
        with patch("backend.events.publisher.get_redis", return_value=None):
            result = publish("civic:test", {"key": "value"})
        assert result is None

    def test_publish_calls_xadd_with_flat_payload(self):
        from backend.events.publisher import publish
        fake_redis = MagicMock()
        fake_redis.xadd.return_value = "1234-0"

        with patch("backend.events.publisher.get_redis", return_value=fake_redis):
            result = publish("civic:test", {"event_type": "test", "data": {"a": 1}})

        assert result == "1234-0"
        assert fake_redis.xadd.called
        call_args = fake_redis.xadd.call_args[0]
        assert call_args[0] == "civic:test"
        payload_sent = call_args[1]
        assert payload_sent["event_type"] == "test"
        # dict values must be JSON-serialised
        assert payload_sent["data"] == '{"a": 1}'

    def test_publish_degrades_on_xadd_failure(self):
        from backend.events.publisher import publish
        fake_redis = MagicMock()
        fake_redis.xadd.side_effect = Exception("Stream error")

        with patch("backend.events.publisher.get_redis", return_value=fake_redis):
            result = publish("civic:test", {"x": "y"})

        assert result is None  # must not raise


# ══════════════════════════════════════════════════════════════════════════════
# 3. Typed emitters
# ══════════════════════════════════════════════════════════════════════════════
class TestTypedEmitters:
    def _mock_publish(self):
        return patch("backend.events.publisher.publish", return_value="mock-entry-id")

    def test_emit_notification_calls_publish_with_correct_stream(self):
        from backend.events.publisher import emit_notification, STREAM_NOTIFICATIONS
        with self._mock_publish() as mock_pub:
            result = emit_notification("user-1", "Title", "Body", "case", "CC-1")
        mock_pub.assert_called_once()
        assert mock_pub.call_args[0][0] == STREAM_NOTIFICATIONS
        payload = mock_pub.call_args[0][1]
        assert payload["user_id"] == "user-1"
        assert payload["event_type"] == "notification"

    def test_emit_ai_job_calls_publish_with_correct_stream(self):
        from backend.events.publisher import emit_ai_job, STREAM_AI_JOBS
        with self._mock_publish() as mock_pub:
            emit_ai_job("intake", "CC-1", None, {"text": "pothole"})
        assert mock_pub.call_args[0][0] == STREAM_AI_JOBS
        payload = mock_pub.call_args[0][1]
        assert payload["job_type"] == "intake"
        assert payload["case_id"] == "CC-1"

    def test_emit_audit_calls_publish_with_correct_stream(self):
        from backend.events.publisher import emit_audit, STREAM_AUDIT
        with self._mock_publish() as mock_pub:
            emit_audit("user-1", "case.status_updated", "CC-1", {"old": "reported"})
        assert mock_pub.call_args[0][0] == STREAM_AUDIT
        payload = mock_pub.call_args[0][1]
        assert payload["action"] == "case.status_updated"

    def test_emit_sync_mutation_calls_publish_with_correct_stream(self):
        from backend.events.publisher import emit_sync_mutation, STREAM_SYNC
        with self._mock_publish() as mock_pub:
            emit_sync_mutation("key-abc", "create_case", "user-1", {"title": "Pothole"})
        assert mock_pub.call_args[0][0] == STREAM_SYNC
        payload = mock_pub.call_args[0][1]
        assert payload["idempotency_key"] == "key-abc"
        assert payload["mutation_type"] == "create_case"


# ══════════════════════════════════════════════════════════════════════════════
# 4. ensure_consumer_groups — fault tolerance
# ══════════════════════════════════════════════════════════════════════════════
class TestConsumerGroups:
    def test_skips_gracefully_when_redis_unavailable(self):
        from backend.events.publisher import ensure_consumer_groups
        with patch("backend.events.publisher.get_redis", return_value=None):
            ensure_consumer_groups()  # must not raise

    def test_handles_busygroup_without_crashing(self):
        import redis as redis_lib
        from backend.events.publisher import ensure_consumer_groups
        fake_redis = MagicMock()
        fake_redis.xgroup_create.side_effect = redis_lib.exceptions.ResponseError("BUSYGROUP Consumer Group already exists")

        with patch("backend.events.publisher.get_redis", return_value=fake_redis):
            ensure_consumer_groups()  # must not raise

    def test_creates_all_four_groups(self):
        from backend.events.publisher import ensure_consumer_groups
        fake_redis = MagicMock()
        fake_redis.xgroup_create.return_value = True

        with patch("backend.events.publisher.get_redis", return_value=fake_redis):
            ensure_consumer_groups()

        assert fake_redis.xgroup_create.call_count == 4


# ══════════════════════════════════════════════════════════════════════════════
# 5. workers: the blocking read must not trip the client's socket timeout (redis-py >= 8 defaults it to 5 s = the block time)
# ══════════════════════════════════════════════════════════════════════════════
def _reads(*items):
    """``xreadgroup`` stand-in: yields ``items`` in order (exceptions are raised), then empty reads forever (an idle stream)."""
    queue = list(items)

    def read(*_a, **_k):
        if queue:
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        time.sleep(0.005)
        return []
    return read


def _run_worker(fake_client, handler, *, until, timeout=5.0):
    """Run one stream worker against ``fake_client`` until ``until()`` is true; returns after the thread stopped."""
    import backend.events.workers as workers
    stop = threading.Event()
    with patch("backend.events.workers.get_worker_redis", return_value=fake_client):
        t = threading.Thread(target=workers._stream_worker, args=("s", "g", "c", handler, stop), daemon=True)
        t.start()
        deadline = time.monotonic() + timeout
        while not until() and time.monotonic() < deadline:
            time.sleep(0.01)
        stop.set()
        t.join(timeout=5)
    assert not t.is_alive()


class TestWorkerLoop:
    def test_worker_client_timeouts_exceed_the_blocking_read(self):
        import backend.events.workers as workers
        with patch("backend.events.publisher.redis_lib.from_url") as from_url:
            assert workers.get_worker_redis() is from_url.return_value
        kw = from_url.call_args.kwargs
        assert kw["socket_timeout"] > workers.WORKER_BLOCK_MS / 1000 and kw["socket_connect_timeout"] > workers.WORKER_BLOCK_MS / 1000
        assert kw["health_check_interval"] > 0 and kw["decode_responses"] is True

    def test_publish_client_keeps_a_short_connect_timeout(self):
        """Requests must not wait long for a dead Redis: the longer worker timeouts apply to the worker client only."""
        import backend.events.publisher as pub
        with patch("backend.events.publisher.redis_lib.from_url") as from_url:
            assert pub.get_redis() is from_url.return_value
        kw = from_url.call_args.kwargs
        assert kw["socket_connect_timeout"] == pub.PUBLISH_CONNECT_TIMEOUT_S == 2.0 and kw["socket_timeout"] == pub.PUBLISH_SOCKET_TIMEOUT_S

    def test_worker_client_is_none_and_warns_when_redis_is_down(self, caplog):
        import backend.events.workers as workers
        with patch("backend.events.publisher.redis_lib.from_url") as from_url, caplog.at_level(logging.WARNING, logger="civicconnect.workers"):
            from_url.return_value.ping.side_effect = redis_lib.exceptions.ConnectionError("refused")
            assert workers.get_worker_redis() is None
        assert workers._worker_client is None and "unavailable" in caplog.text

    def test_a_read_timeout_is_quiet_and_the_next_message_is_still_handled(self, caplog):
        seen, fake = [], MagicMock()
        fake.xreadgroup.side_effect = _reads(redis_lib.exceptions.TimeoutError("Timeout reading from socket"), [("s", [("1-0", {"a": "b"})])])
        with caplog.at_level(logging.DEBUG, logger="civicconnect.workers"), patch("backend.events.workers._pause") as pause:
            _run_worker(fake, seen.append, until=lambda: fake.xack.called)
        assert seen == [{"a": "b"}] and fake.xack.call_args.args == ("s", "g", "1-0") and not pause.called          # no back-off after a timeout
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]                      # no log noise for a timeout

    def test_a_real_connection_error_still_warns_and_backs_off(self, caplog):
        fake = MagicMock()
        fake.xreadgroup.side_effect = redis_lib.exceptions.ConnectionError("connection lost")
        with caplog.at_level(logging.WARNING, logger="civicconnect.workers"):
            _run_worker(fake, lambda m: None, until=lambda: fake.xreadgroup.called)
        assert fake.xreadgroup.call_count == 1                                                      # backed off (stop interrupted the pause) instead of spinning
        assert [r for r in caplog.records if r.levelno == logging.WARNING and "Stream read error" in r.getMessage()]


def _live_redis_url() -> str:
    return os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


def _live_redis_or_skip():
    try:
        client = redis_lib.from_url(_live_redis_url(), decode_responses=True, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception as exc:
        pytest.skip(f"no Redis reachable at TEST_REDIS_URL (default redis://localhost:6379/15): {exc}")


def test_live_redis_idle_polls_are_silent_and_events_are_consumed(caplog, monkeypatch):
    """Against a real Redis: the worker idles for longer than the 5 s block (the old code logged a socket timeout per poll), then consumes two events."""
    import backend.events.publisher as pub
    import backend.events.workers as workers
    admin = _live_redis_or_skip()
    monkeypatch.setattr(pub.settings, "REDIS_URL", _live_redis_url())
    stream, group, handled = f"civic:test:{uuid.uuid4().hex}", "test-workers", []
    admin.xgroup_create(stream, group, id="$", mkstream=True)
    client = workers.make_client(connect_timeout=workers.WORKER_CONNECT_TIMEOUT_S, socket_timeout=workers.WORKER_SOCKET_TIMEOUT_S)
    stop = threading.Event()
    try:
        with caplog.at_level(logging.DEBUG, logger="civicconnect.workers"), patch("backend.events.workers.get_worker_redis", return_value=client):
            t = threading.Thread(target=workers._stream_worker, args=(stream, group, "t-1", handled.append, stop), daemon=True)
            t.start()
            time.sleep(workers.WORKER_BLOCK_MS / 1000 + 1.5)                                       # at least one full idle poll
            admin.xadd(stream, {"n": "1"})
            admin.xadd(stream, {"n": "2"})
            deadline = time.monotonic() + 8
            while len(handled) < 2 and time.monotonic() < deadline:
                time.sleep(0.05)
            stop.set()
            t.join(timeout=workers.WORKER_BLOCK_MS / 1000 + 3)
        assert [m["n"] for m in handled] == ["1", "2"] and not t.is_alive()
        assert admin.xpending(stream, group)["pending"] == 0                                        # both acknowledged
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING], caplog.text
    finally:
        stop.set()
        admin.delete(stream)
