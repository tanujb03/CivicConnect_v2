"""Redis Streams publisher (events architecture, plan phase D). Entirely unit-level: Redis is mocked, no live server is needed.

(Originally Parth's test_phase_d.py; the sync-endpoint tests moved to test_api_sync.py when /sync became the real §51A.16 endpoint, and the module level
``dependency_overrides`` was removed because it leaked into every other test.)
"""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _fresh_redis_state():
    """The publisher remembers a failed connection for 30 s (so requests do not each wait for the timeout); every test here starts from a clean slate."""
    import backend.events.publisher as pub
    pub._redis_client, pub._redis_down_until = None, 0.0
    yield
    pub._redis_client, pub._redis_down_until = None, 0.0


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


