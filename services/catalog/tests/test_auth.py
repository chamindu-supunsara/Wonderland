import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError

from app import auth
from app.main import create_app

ISSUER = "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_test"
CLIENT = "testclient"


@pytest.fixture(scope="module")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def auth_client(private_key, monkeypatch):
    keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())
    )
    verifier = auth.CognitoVerifier(ISSUER, CLIENT, keys)
    monkeypatch.setattr(auth, "get_verifier", lambda: verifier)
    with TestClient(create_app()) as client:
        yield client


def token(private_key, **changes):
    now = int(time.time())
    claims = {
        "sub": "visitor-123",
        "username": "visitor-123",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 300,
        "token_use": "access",
        "client_id": CLIENT,
    }
    claims.update(changes)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def headers(value):
    return {"Authorization": f"Bearer {value}"}


def test_visitor_can_read_identity_but_not_admin(auth_client, private_key):
    credentials = headers(token(private_key))
    response = auth_client.get("/api/v1/users/me", headers=credentials)
    assert response.status_code == 200
    assert response.json() == {
        "user_id": "visitor-123",
        "username": "visitor-123",
        "role": "visitor",
    }
    assert auth_client.get("/api/v1/admin/access-check", headers=credentials).status_code == 403


def test_administrator_access_is_verified(auth_client, private_key):
    credentials = headers(token(private_key, **{"cognito:groups": ["Administrators"]}))
    response = auth_client.get("/api/v1/admin/access-check", headers=credentials)
    assert response.status_code == 200
    assert response.json()["role"] == "administrator"


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://attacker.example/pool"},
        {"client_id": "another-client"},
        {"token_use": "id"},
        {"exp": 1},
        {"iat": 9999999999},
        {"sub": ""},
        {"cognito:groups": "Administrators"},
        {"cognito:groups": [123]},
    ],
)
def test_invalid_claims_are_rejected(auth_client, private_key, changes):
    response = auth_client.get("/api/v1/users/me", headers=headers(token(private_key, **changes)))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_forged_signature_rejected(auth_client):
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert (
        auth_client.get("/api/v1/users/me", headers=headers(token(attacker_key))).status_code == 401
    )


@pytest.mark.parametrize(
    "value", ["broken", "", jwt.encode({"sub": "x"}, "x" * 32, algorithm="HS256")]
)
def test_malformed_or_wrong_algorithm_rejected(auth_client, value):
    assert auth_client.get("/api/v1/users/me", headers=headers(value)).status_code == 401


def test_authentication_required(auth_client):
    assert auth_client.get("/api/v1/users/me").status_code == 401
    assert auth_client.get("/api/v1/admin/access-check").status_code == 401
    assert auth_client.get("/health/live").status_code == 200


def test_unavailable_keys_fail_closed(private_key):
    def unavailable(_token):
        raise PyJWKClientConnectionError("offline")

    verifier = auth.CognitoVerifier(
        ISSUER, CLIENT, SimpleNamespace(get_signing_key_from_jwt=unavailable)
    )
    with pytest.raises(auth.HTTPException) as error:
        verifier.verify(token(private_key))
    assert error.value.status_code == 503


def test_custom_role_cannot_grant_admin(auth_client, private_key):
    credentials = headers(token(private_key, **{"custom:role": "administrator"}))
    assert auth_client.get("/api/v1/admin/access-check", headers=credentials).status_code == 403
