from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.exc import OperationalError

from fastapi.testclient import TestClient
import structlog

from backend.app.core.logging import redact_sensitive_data
from backend.app.core.middleware import REQUEST_ID_PATTERN
from backend.app.main import create_app


def create_app_with_error_route():
    app = create_app()

    @app.get("/trigger-error")
    async def trigger_error():
        raise RuntimeError("Database failure at /var/secrets/db_password.txt")

    return app


def test_liveness():
    with TestClient(create_app()) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "alive"}


def test_readiness():
    with TestClient(create_app()) as client:
        response = client.get("/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"
        assert response.json()["checks"]["database"] is True
        assert response.json()["checks"]["asset_storage"] is True


def test_request_id_generated():
    with TestClient(create_app()) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers.get("x-request-id")


def test_request_id_preserved():
    request_id = "movieai-test-001"

    with TestClient(create_app()) as client:
        response = client.get(
            "/health",
            headers={"X-Request-ID": request_id},
        )

        assert response.headers["x-request-id"] == request_id


def test_invalid_request_id_replaced():
    with TestClient(create_app()) as client:
        response = client.get(
            "/health",
            headers={"X-Request-ID": "invalid request id"},
        )

        assert response.status_code == 200
        assert response.headers["x-request-id"] != "invalid request id"


def test_unknown_host_rejected():
    with TestClient(create_app()) as client:
        response = client.get(
            "/health",
            headers={"Host": "attacker.invalid"},
        )

        assert response.status_code == 400


def test_unhandled_500_generates_request_id_and_sanitizes_body():
    app = create_app_with_error_route()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/trigger-error")

        assert response.status_code == 500
        req_id = response.headers.get("x-request-id")
        assert req_id is not None
        assert REQUEST_ID_PATTERN.fullmatch(req_id)
        assert response.json() == {
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred.",
            }
        }
        assert "db_password.txt" not in response.text
        assert "RuntimeError" not in response.text


def test_unhandled_500_preserves_valid_client_request_id():
    app = create_app_with_error_route()
    client_req_id = "trace-err-500-client-01"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/trigger-error",
            headers={"X-Request-ID": client_req_id},
        )

        assert response.status_code == 500
        assert response.headers.get("x-request-id") == client_req_id
        assert response.json() == {
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred.",
            }
        }


def test_unhandled_500_replaces_invalid_client_request_id():
    app = create_app_with_error_route()
    invalid_req_id = "invalid request id with spaces!!!"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/trigger-error",
            headers={"X-Request-ID": invalid_req_id},
        )

        assert response.status_code == 500
        req_id = response.headers.get("x-request-id")
        assert req_id is not None
        assert req_id != invalid_req_id
        assert REQUEST_ID_PATTERN.fullmatch(req_id)
        assert response.json() == {
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred.",
            }
        }


def test_request_id_context_isolation_across_requests():
    app = create_app_with_error_route()
    with TestClient(app, raise_server_exceptions=False) as client:
        res1 = client.get(
            "/trigger-error",
            headers={"X-Request-ID": "req-isolation-1"},
        )
        assert res1.status_code == 500
        assert res1.headers.get("x-request-id") == "req-isolation-1"

        res2 = client.get("/trigger-error")
        assert res2.status_code == 500
        req_id_2 = res2.headers.get("x-request-id")
        assert req_id_2 is not None
        assert req_id_2 != "req-isolation-1"
        assert REQUEST_ID_PATTERN.fullmatch(req_id_2)

        res3 = client.get(
            "/health",
            headers={"X-Request-ID": "req-isolation-3"},
        )
        assert res3.status_code == 200
        assert res3.headers.get("x-request-id") == "req-isolation-3"

        assert structlog.contextvars.get_contextvars() == {}


def test_readiness_database_failure():
    app = create_app()
    with TestClient(app) as client:
        # Simulate active database engine failure by assigning mock engine
        mock_engine = MagicMock()
        mock_connect = AsyncMock()
        mock_connect.__aenter__.side_effect = OperationalError(
            "connection failed",
            None,
            Exception("disk I/O error"),
        )
        mock_engine.connect.return_value = mock_connect
        app.state.db_engine = mock_engine

        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] is False
        assert data["checks"]["asset_storage"] is True
        # Verify no connection or credential leakage
        assert "connection failed" not in response.text
        assert "disk I/O error" not in response.text


def test_readiness_database_missing_engine():
    app = create_app()
    with TestClient(app) as client:
        app.state.db_engine = None
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] is False


def test_readiness_custom_database_url(tmp_path: Path, monkeypatch):
    custom_db = tmp_path / "custom_test.db"
    app = create_app()
    monkeypatch.setattr(
        app.state.settings,
        "database_url",
        f"sqlite+aiosqlite:///{custom_db}",
    )
    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] is True
        assert data["checks"]["asset_storage"] is True


def test_readiness_asset_storage_failure(monkeypatch):
    app = create_app()
    with TestClient(app) as client:
        monkeypatch.setattr(
            app.state.settings,
            "asset_storage_path",
            Path("/nonexistent/movieai/assets"),
        )
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] is True
        assert data["checks"]["asset_storage"] is False


def test_sensitive_log_redaction():
    raw_event = {
        "event": "user_action",
        "password": "supersecretpassword123",
        "api_key": "secret-api-key-value",
        "token": "secret-token-xyz",
        "authorization": "Bearer eyJhbGciOi...",
        "nested": {
            "credentials": "top_secret_credential",
            "normal_field": "hello world",
        },
        "safe_data": "movie_project_alpha",
    }
    redacted = redact_sensitive_data(None, "info", raw_event)
    assert redacted["password"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["credentials"] == "[REDACTED]"
    assert redacted["nested"]["normal_field"] == "hello world"
    assert redacted["safe_data"] == "movie_project_alpha"
    assert "supersecretpassword123" not in str(redacted)
    assert "secret-api-key-value" not in str(redacted)
    assert "top_secret_credential" not in str(redacted)
