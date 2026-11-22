from datetime import datetime, timedelta, timezone
import uuid
from fastapi.testclient import TestClient
import jwt

from backend.app.core.config import Settings
from backend.app.infrastructure.database.models.auth import UserModel


def test_google_login_redirect(client: TestClient):
    response = client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert "accounts.google.com" in location
    assert "response_type=code" in location
    assert "code_challenge=" in location
    assert "code_challenge_method=S256" in location
    assert "state=" in location

    # Check PKCE cookies
    assert "movieai_oauth_state" in response.cookies
    assert "movieai_oauth_verifier" in response.cookies


def test_google_login_json_mode(client: TestClient):
    response = client.get("/api/v1/auth/google/login?json=true")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "auth_url" in data
    assert "accounts.google.com" in data["auth_url"]
    assert "state" in data
    assert "movieai_oauth_state" in response.cookies
    assert "movieai_oauth_verifier" in response.cookies


def test_google_callback_missing_code(client: TestClient):
    response = client.get("/api/v1/auth/google/callback", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert "error=missing_code" in location


def test_google_callback_invalid_state(client: TestClient):
    client.cookies.set("movieai_oauth_state", "correct_state")
    response = client.get("/api/v1/auth/google/callback?code=somecode&state=wrong_state", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert "error=invalid_state" in location


def test_google_callback_whitelist_enforcement_rejected(client: TestClient):
    client.cookies.set("movieai_oauth_state", "valid_state")
    client.cookies.set("movieai_oauth_verifier", "valid_verifier")

    # test_code with non-whitelisted email
    response = client.get(
        "/api/v1/auth/google/callback?code=test_code_hacker@stranger.com&state=valid_state",
        follow_redirects=False,
    )
    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert "error=403" in location


def test_google_callback_whitelist_success(client: TestClient, settings: Settings):
    client.cookies.set("movieai_oauth_state", "valid_state")
    client.cookies.set("movieai_oauth_verifier", "valid_verifier")

    response = client.get(
        "/api/v1/auth/google/callback?code=test_code_needgenius19@gmail.com&state=valid_state",
        follow_redirects=False,
    )
    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert "/dashboard" in location
    assert settings.cookie_name in response.cookies


def test_me_unauthenticated_anti_loop(client: TestClient, settings: Settings):
    # Call without cookies
    client.cookies.clear()
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    # Anti-loop verification: Set-Cookie must delete session cookie
    set_cookie_header = response.headers.get("set-cookie", "")
    assert settings.cookie_name in set_cookie_header
    assert "max-age=0" in set_cookie_header.lower() or "expires=" in set_cookie_header.lower()


def test_me_invalid_token_anti_loop(client: TestClient, settings: Settings):
    # Call with garbage token
    client.cookies.set(settings.cookie_name, "invalid.jwt.token")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    set_cookie_header = response.headers.get("set-cookie", "")
    assert settings.cookie_name in set_cookie_header


def test_me_expired_token_anti_loop(client: TestClient, settings: Settings, test_user: UserModel):
    # Call with expired token
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "exp": int((now - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    client.cookies.set(settings.cookie_name, expired_token)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    set_cookie_header = response.headers.get("set-cookie", "")
    assert settings.cookie_name in set_cookie_header


def test_me_success_with_cookie(client: TestClient, auth_cookies: dict[str, str], test_user: UserModel):
    for k, v in auth_cookies.items():
        client.cookies.set(k, v)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == test_user.email
    assert data["id"] == str(test_user.id)
    assert data["role"] == "SHOWRUNNER"


def test_me_success_with_bearer_header(client: TestClient, auth_headers: dict[str, str], test_user: UserModel):
    client.cookies.clear()
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == test_user.email


def test_logout(client: TestClient, auth_cookies: dict[str, str], settings: Settings):
    for k, v in auth_cookies.items():
        client.cookies.set(k, v)

    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["data"]["message"] == "Successfully logged out"
    set_cookie_header = response.headers.get("set-cookie", "")
    assert settings.cookie_name in set_cookie_header
