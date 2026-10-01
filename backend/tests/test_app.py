"""Cross-cutting behavior: health probes, error envelope, CORS."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store import InMemoryStore
from tests.conftest import assert_error


class UnreachableStore(InMemoryStore):
    def ping(self) -> bool:
        raise ConnectionError("database is down")


def test_health_is_ok_without_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_is_ok_when_store_is_reachable(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_is_503_when_store_is_unreachable():
    app = create_app(Settings(jwt_secret="x", seed_demo_data=False), store=UnreachableStore())
    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_invalid_json_uses_error_envelope(client):
    response = client.post(
        "/auth/login", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert_error(response, 422, "VALIDATION_ERROR")


def test_unknown_route_uses_error_envelope(client):
    assert_error(client.get("/does-not-exist"), 404, "NOT_FOUND")


def test_wrong_method_uses_error_envelope_and_keeps_allow_header(client):
    response = client.put("/auth/me")

    assert_error(response, 405, "METHOD_NOT_ALLOWED")
    assert response.headers["allow"] == "GET"


def test_unexpected_error_returns_internal_error_envelope(harness):
    @harness.app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    response = TestClient(harness.app, raise_server_exceptions=False).get("/boom")

    error = assert_error(response, 500, "INTERNAL_ERROR")
    assert "secret" not in error["message"]


def test_cors_allows_configured_origin(client):
    response = client.options(
        "/auth/me",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"


def test_settings_from_env():
    settings = Settings.from_env(
        {
            "JWT_SECRET": "s",
            "ANALYSIS_STALE_AFTER_SECONDS": "30",
            "CORS_ORIGINS": "https://a.example, https://b.example",
            "SEED_DEMO_DATA": "false",
        }
    )
    assert settings.jwt_secret == "s"
    assert settings.analysis_stale_after_seconds == 30
    assert settings.cors_origins == ("https://a.example", "https://b.example")
    assert settings.seed_demo_data is False


def test_settings_defaults_and_random_secret():
    first, second = Settings.from_env({}), Settings.from_env({})
    assert first.jwt_secret and first.jwt_secret != second.jwt_secret
    assert first.analysis_stale_after_seconds == 600
    assert first.seed_demo_data is True
