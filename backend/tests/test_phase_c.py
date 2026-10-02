"""
Phase C Comprehensive Test Suite — tests all routes WITHOUT a live database.
Uses FastAPI's TestClient with an in-memory SQLite override.

Tests are NOT happy-path only — they cover:
  - Schema validation failures (422)
  - Auth enforcement (401/403)
  - RBAC role boundary (wrong role → 403)
  - 404 on missing resources
  - Idempotency-Key presence
  - Stable error envelope shape
  - Mock token generation and decoding
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# ── sys.path fix ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

# ── Must patch DB engine BEFORE importing anything that touches SQLAlchemy ────
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.session import Base, get_db

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── Now import the app and apply overrides ────────────────────────────────────
from backend.main import app
from backend.core.security import create_access_token

app.dependency_overrides[get_db] = override_get_db

from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)

# ── Token helpers ─────────────────────────────────────────────────────────────
def token_for(role: str, user_id: str = "test-user-1") -> dict:
    t = create_access_token(subject=user_id, role=role)
    return {"Authorization": f"Bearer {t}"}

CITIZEN_HEADERS   = token_for("citizen")
OPERATOR_HEADERS  = token_for("operator")
ADMIN_HEADERS     = token_for("system_admin")
WARD_HEADERS      = token_for("ward_officer")

# ══════════════════════════════════════════════════════════════════════════════
# 1. HEALTH
# ══════════════════════════════════════════════════════════════════════════════
class TestHealth:
    def test_health_ok(self):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_no_auth_needed(self):
        r = client.get("/api/v1/health")
        assert r.status_code == 200

# ══════════════════════════════════════════════════════════════════════════════
# 2. AUTH
# ══════════════════════════════════════════════════════════════════════════════
class TestAuth:
    def test_login_mock_admin_ok(self):
        r = client.post("/api/v1/auth/login", data={"username": "admin", "password": "admin"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_login_mock_citizen_ok(self):
        r = client.post("/api/v1/auth/login", data={"username": "citizen", "password": "citizen"})
        assert r.status_code == 200

    def test_login_wrong_credentials(self):
        r = client.post("/api/v1/auth/login", data={"username": "nobody", "password": "wrong"})
        assert r.status_code == 400

    def test_login_empty_body(self):
        r = client.post("/api/v1/auth/login", data={})
        assert r.status_code == 422  # FastAPI validation error

# ══════════════════════════════════════════════════════════════════════════════
# 3. /ME — bearer auth enforcement
# ══════════════════════════════════════════════════════════════════════════════
class TestMe:
    def test_get_me_no_token_returns_401(self):
        r = client.get("/api/v1/me/")
        assert r.status_code == 401

    def test_get_me_invalid_token_returns_401(self):
        r = client.get("/api/v1/me/", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401

    def test_get_me_valid_citizen_token(self):
        r = client.get("/api/v1/me/", headers=CITIZEN_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "citizen"
        assert "id" in body

    def test_patch_me_no_token_returns_401(self):
        r = client.patch("/api/v1/me/", json={"name": "Parth"})
        assert r.status_code == 401

    def test_get_notifications_no_token(self):
        r = client.get("/api/v1/me/notifications")
        assert r.status_code == 401

    def test_get_notifications_valid_token(self):
        r = client.get("/api/v1/me/notifications", headers=CITIZEN_HEADERS)
        assert r.status_code == 200
        assert "items" in r.json()

# ══════════════════════════════════════════════════════════════════════════════
# 4. CASES — CRUD, schema validation, 404
# ══════════════════════════════════════════════════════════════════════════════
class TestCases:
    def test_list_cases_no_auth_returns_data(self):
        """GET /cases/ does not require auth per spec (public browse)."""
        r = client.get("/api/v1/cases/")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_create_case_missing_required_fields_422(self):
        r = client.post("/api/v1/cases/", json={"title": "Pothole"})  # category is required
        assert r.status_code == 422

    def test_create_case_empty_body_422(self):
        r = client.post("/api/v1/cases/", json={})
        assert r.status_code == 422

    def test_create_case_valid_mock_response(self):
        payload = {
            "title": "Large pothole",
            "category": "roads",
            "subcategory": "pothole",
            "severity": "high"
        }
        r = client.post("/api/v1/cases/", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "Large pothole"
        assert body["category"] == "roads"
        assert body["status"] == "reported"
        assert "id" in body

    def test_get_case_nonexistent_returns_404(self):
        r = client.get("/api/v1/cases/CC-DOESNOTEXIST")
        assert r.status_code == 404

    def test_get_case_timeline_returns_events_key(self):
        r = client.get("/api/v1/cases/CC-ANY/timeline")
        assert r.status_code == 200
        assert "events" in r.json()

    def test_verify_case_returns_verified(self):
        r = client.post("/api/v1/cases/CC-ANY/verification")
        assert r.status_code == 200
        assert r.json()["status"] == "verified"

    def test_create_case_severity_invalid_value_passes_as_string(self):
        """Severity is a free string field — bad values degrade gracefully."""
        payload = {"title": "T", "category": "water", "severity": "unknown_value"}
        r = client.post("/api/v1/cases/", json=payload)
        assert r.status_code == 200

# ══════════════════════════════════════════════════════════════════════════════
# 5. WORK ORDERS — 404, RBAC, Idempotency header
# ══════════════════════════════════════════════════════════════════════════════
class TestWorkOrders:
    def test_list_work_orders_returns_items_key(self):
        r = client.get("/api/v1/work-orders/")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_get_nonexistent_work_order_404(self):
        r = client.get("/api/v1/work-orders/WO-DOESNOTEXIST")
        assert r.status_code == 404

    def test_create_work_order_missing_required_fields_422(self):
        r = client.post("/api/v1/work-orders/", json={"notes": "fix it"})
        assert r.status_code == 422

    def test_create_work_order_valid_mock(self):
        payload = {"case_id": "CC-MOCK-1", "department_id": "DEPT-1"}
        r = client.post("/api/v1/work-orders/", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["case_id"] == "CC-MOCK-1"
        assert "id" in body

    def test_create_work_order_with_idempotency_key(self):
        payload = {"case_id": "CC-MOCK-1", "department_id": "DEPT-1"}
        headers = {"Idempotency-Key": "unique-key-abc123"}
        r = client.post("/api/v1/work-orders/", json=payload, headers=headers)
        assert r.status_code == 200

# ══════════════════════════════════════════════════════════════════════════════
# 6. EVIDENCE — Upload endpoint
# ══════════════════════════════════════════════════════════════════════════════
class TestEvidence:
    def test_upload_evidence_missing_fields_422(self):
        r = client.post("/api/v1/evidence/", files={}, data={})
        assert r.status_code == 422

    def test_upload_evidence_mock_ok(self):
        r = client.post(
            "/api/v1/evidence/",
            data={"case_id": "CC-MOCK-1"},
            files={"file": ("photo.jpg", b"fake-binary-data", "image/jpeg")},
        )
        assert r.status_code == 200
        body = r.json()
        assert "file_url" in body
        assert "case_id" in body
        assert body["case_id"] == "CC-MOCK-1"

# ══════════════════════════════════════════════════════════════════════════════
# 7. MAP — geospatial queries
# ══════════════════════════════════════════════════════════════════════════════
class TestMap:
    def test_map_cases_missing_lat_lng_422(self):
        r = client.get("/api/v1/map/cases")
        assert r.status_code == 422

    def test_map_cases_with_params(self):
        r = client.get("/api/v1/map/cases?lat=18.5&lng=73.8")
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "FeatureCollection"

    def test_map_hotspots_returns_geojson(self):
        r = client.get("/api/v1/map/hotspots")
        assert r.status_code == 200
        assert r.json()["type"] == "FeatureCollection"

# ══════════════════════════════════════════════════════════════════════════════
# 8. INCIDENTS — RBAC enforcement
# ══════════════════════════════════════════════════════════════════════════════
class TestIncidents:
    def test_list_incidents_no_auth_returns_401(self):
        r = client.get("/api/v1/incidents/")
        assert r.status_code == 401

    def test_list_incidents_citizen_role_403(self):
        """Citizens must NOT see the incidents management surface."""
        r = client.get("/api/v1/incidents/", headers=CITIZEN_HEADERS)
        assert r.status_code == 403

    def test_list_incidents_ward_officer_allowed(self):
        r = client.get("/api/v1/incidents/", headers=WARD_HEADERS)
        assert r.status_code == 200

    def test_list_incidents_admin_allowed(self):
        r = client.get("/api/v1/incidents/", headers=ADMIN_HEADERS)
        assert r.status_code == 200

    def test_create_incident_citizen_403(self):
        r = client.post("/api/v1/incidents/", json={"title": "Big flood"}, headers=CITIZEN_HEADERS)
        assert r.status_code == 403

    def test_get_nonexistent_incident_404(self):
        r = client.get("/api/v1/incidents/INC-DOESNOTEXIST", headers=ADMIN_HEADERS)
        assert r.status_code == 404

# ══════════════════════════════════════════════════════════════════════════════
# 9. ANALYTICS — RBAC enforcement
# ══════════════════════════════════════════════════════════════════════════════
class TestAnalytics:
    def test_analytics_summary_no_auth_401(self):
        r = client.get("/api/v1/analytics/summary")
        assert r.status_code == 401

    def test_analytics_summary_citizen_403(self):
        r = client.get("/api/v1/analytics/summary", headers=CITIZEN_HEADERS)
        assert r.status_code == 403

    def test_analytics_summary_operator_allowed(self):
        r = client.get("/api/v1/analytics/summary", headers=OPERATOR_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "total_cases" in body

    def test_analytics_hotspots_citizen_403(self):
        r = client.get("/api/v1/analytics/hotspots", headers=CITIZEN_HEADERS)
        assert r.status_code == 403

    def test_analytics_hotspots_ward_allowed(self):
        r = client.get("/api/v1/analytics/hotspots", headers=WARD_HEADERS)
        assert r.status_code == 200

# ══════════════════════════════════════════════════════════════════════════════
# 10. ERROR ENVELOPE shape
# ══════════════════════════════════════════════════════════════════════════════
class TestErrorEnvelope:
    def test_404_case_error_detail_is_string(self):
        r = client.get("/api/v1/cases/CC-DOESNOTEXIST")
        assert r.status_code == 404
        # FastAPI built-in detail format is acceptable
        assert "detail" in r.json()

    def test_401_error_has_www_authenticate_header(self):
        r = client.get("/api/v1/me/")
        assert r.status_code == 401
        # WWW-Authenticate header must be present per RFC 6750
        assert "www-authenticate" in {k.lower() for k in r.headers}

    def test_403_error_has_code_field(self):
        r = client.get("/api/v1/incidents/", headers=CITIZEN_HEADERS)
        assert r.status_code == 403
        detail = r.json().get("detail", {})
        # Our custom RBAC error returns {"code": "auth.forbidden", ...}
        assert detail.get("code") == "auth.forbidden"

    def test_x_request_id_header_present_in_every_response(self):
        """Every response must carry X-Request-ID for request correlation."""
        r = client.get("/api/v1/health")
        assert "x-request-id" in {k.lower() for k in r.headers}

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=ROOT
    )
    sys.exit(result.returncode)
