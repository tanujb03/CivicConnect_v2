"""CORS: the local dev servers of every app are allowed by default, credentials are on, and no origin is ever '*' with credentials (WP11)."""
import pytest
from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.main import app


def preflight(origin: str):
    return TestClient(app).options("/api/v1/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,idempotency-key,content-type"})


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://localhost:8080", "http://localhost:8081", "http://localhost:19006"])
def test_the_dev_servers_of_the_apps_are_allowed_with_credentials(origin):
    r = preflight(origin)
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == origin and r.headers["access-control-allow-credentials"] == "true"
    assert "idempotency-key" in r.headers["access-control-allow-headers"].lower()


def test_an_unlisted_origin_gets_no_allow_origin_header():
    assert "access-control-allow-origin" not in preflight("https://evil.example").headers


def test_the_default_list_has_no_wildcard_and_cors_origins_is_parsed_from_the_environment(monkeypatch):
    assert "*" not in Settings().cors_origins
    monkeypatch.setenv("CORS_ORIGINS", "https://a.vercel.app, https://b.vercel.app ")
    assert Settings().cors_origins == ["https://a.vercel.app", "https://b.vercel.app"]
