from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.auth import TOKEN_TTL_SECONDS, create_access_token, decode_access_token
from tests.conftest import assert_error
from tests.samples import TEST_JWT_SECRET

SECRET = TEST_JWT_SECRET
OTHER_SECRET = f"other-{SECRET}"


def register(client, email="new@example.com", password="password123"):
    return client.post("/auth/register", json={"email": email, "password": password})


def test_register_returns_token_and_user(client):
    response = register(client, email="  New.User@Example.COM ")

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 86400
    assert set(body["user"]) == {"id", "email", "role", "created_at"}
    assert body["user"]["email"] == "new.user@example.com"
    assert body["user"]["role"] == "user"
    assert body["user"]["created_at"].endswith("Z")


def test_password_is_stored_hashed(harness):
    register(harness.client)
    user = harness.store.get_user_by_email("new@example.com")
    assert user.password_hash != "password123"
    assert user.password_hash.startswith("$argon2")


def test_token_is_hs256_with_24_hour_lifetime(client):
    token = register(client).json()["access_token"]

    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    claims = jwt.decode(token, SECRET, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == TOKEN_TTL_SECONDS


def test_duplicate_email_conflicts_after_normalization(client):
    register(client)
    assert_error(register(client, email="NEW@example.com "), 409, "EMAIL_ALREADY_EXISTS")


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "password123"},
        {"email": "a@example.com", "password": "short77"},
        {"email": "a@example.com"},
        {"email": f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 63}.com", "password": "password123"},
        {"email": "a@example.com", "password": "password123", "role": "admin"},
    ],
)
def test_register_validation_errors(client, payload):
    assert_error(client.post("/auth/register", json=payload), 422, "VALIDATION_ERROR")


def test_short_password_message(client):
    error = assert_error(register(client, password="short"), 422, "VALIDATION_ERROR")
    assert error["message"] == "Password must be at least 8 characters."


def test_login_with_normalized_email(client):
    register(client)
    response = client.post("/auth/login", json={"email": " NEW@example.com", "password": "password123"})

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "new@example.com"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "new@example.com", "password": "wrong-password"},
        {"email": "nobody@example.com", "password": "password123"},
    ],
)
def test_login_with_wrong_credentials(client, payload):
    register(client)
    error = assert_error(client.post("/auth/login", json=payload), 401, "INVALID_CREDENTIALS")
    assert error["message"] == "Invalid email or password."


def test_login_validation_error(client):
    assert_error(client.post("/auth/login", json={"email": "", "password": "x"}), 422, "VALIDATION_ERROR")


def test_me_returns_current_user_without_password_hash(client):
    token = register(client).json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"
    assert "password_hash" not in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": f"Bearer {create_access_token(uuid4(), SECRET, datetime.now(UTC))}"},
        {"Authorization": f"Bearer {create_access_token(uuid4(), OTHER_SECRET, datetime.now(UTC))}"},
    ],
)
def test_me_rejects_missing_invalid_or_unknown_tokens(client, headers):
    error = assert_error(client.get("/auth/me", headers=headers), 401, "UNAUTHORIZED")
    assert error["message"] == "Your session has expired. Please log in again."


def test_expired_token_is_rejected(harness):
    register(harness.client)
    user = harness.store.get_user_by_email("new@example.com")
    issued = datetime.now(UTC) - timedelta(seconds=TOKEN_TTL_SECONDS + 1)
    token = create_access_token(user.id, SECRET, issued)

    assert decode_access_token(token, SECRET) is None
    assert_error(harness.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}), 401, "UNAUTHORIZED")


def test_token_with_other_algorithm_is_rejected():
    token = jwt.encode({"sub": str(uuid4()), "iat": 0, "exp": 2**31}, SECRET * 2, algorithm="HS512")
    assert decode_access_token(token, SECRET) is None
