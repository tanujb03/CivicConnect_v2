"""
Phase D Test Suite — Redis/Events Architecture.

Tests are entirely unit-level and do NOT require a live Redis instance.
Redis calls are mocked so the test suite runs offline.

Covers:
  - publish() degrades gracefully when Redis is None
  - publish() serialises dict fields to JSON
  - emit_notification, emit_ai_job, emit_audit, emit_sync_mutation all call publish
  - ensure_consumer_groups handles BUSYGROUP without crashing
  - ensure_consumer_groups handles Redis-unavailable without crashing
  - /api/v1/sync/mutations enforces Idempotency-Key (missing → 422 with code)
  - /api/v1/sync/mutations rejects unauthenticated requests
  - /api/v1/sync/mutations accepts valid mutations and queues them
  - /api/v1/sync/status returns pending count
"""
import sys
import os
import json
from unittest.mock import MagicMock, patch, call

# ── path fix ──────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.security import create_access_token
from backend.db.session import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# SQLite override (no Postgres needed)
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app, raise_server_exceptions=False)

def auth_headers(role: str = "citizen") -> dict:
    token = create_access_token(subject="user-1", role=role)
    return {"Authorization": f"Bearer {token}"}


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
# 5. /api/v1/sync — HTTP endpoint tests
# ══════════════════════════════════════════════════════════════════════════════
class TestSyncEndpoint:
    def test_mutations_no_auth_returns_401(self):
        r = client.post("/api/v1/sync/mutations", json={"mutation_type": "create_case", "data": {}})
        assert r.status_code == 401

    def test_mutations_missing_idempotency_key_returns_422(self):
        r = client.post(
            "/api/v1/sync/mutations",
            json={"mutation_type": "create_case", "data": {"title": "Pothole"}},
            headers=auth_headers("citizen"),
        )
        assert r.status_code == 422
        detail = r.json().get("detail", {})
        assert detail.get("code") == "sync.missing_idempotency_key"

    def test_mutations_missing_body_returns_422(self):
        r = client.post(
            "/api/v1/sync/mutations",
            json={},
            headers={**auth_headers("citizen"), "Idempotency-Key": "key-123"},
        )
        assert r.status_code == 422

    def test_mutations_valid_queued_response(self):
        with patch("backend.events.publisher.publish", return_value="1234-0"):
            r = client.post(
                "/api/v1/sync/mutations",
                json={"mutation_type": "create_case", "data": {"title": "Pothole on MG road"}},
                headers={**auth_headers("citizen"), "Idempotency-Key": "idem-key-001"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "queued"
        assert body["idempotency_key"] == "idem-key-001"
        assert body["mutation_type"] == "create_case"

    def test_mutations_different_roles_all_allowed(self):
        """All authenticated roles may submit sync mutations."""
        for role in ("citizen", "operator", "field_worker"):
            with patch("backend.events.publisher.publish", return_value="ok"):
                r = client.post(
                    "/api/v1/sync/mutations",
                    json={"mutation_type": "support", "data": {"case_id": "CC-1"}},
                    headers={**auth_headers(role), "Idempotency-Key": f"key-{role}"},
                )
            assert r.status_code == 200, f"Failed for role {role}"

    def test_sync_status_no_auth_returns_401(self):
        r = client.get("/api/v1/sync/status")
        assert r.status_code == 401

    def test_sync_status_valid_returns_pending(self):
        r = client.get("/api/v1/sync/status", headers=auth_headers("citizen"))
        assert r.status_code == 200
        assert "pending" in r.json()


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=ROOT
    )
    sys.exit(result.returncode)
