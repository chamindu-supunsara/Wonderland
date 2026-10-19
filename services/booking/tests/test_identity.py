import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from booking_app import auth
from booking_app.main import create_app


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"token_use": "id"},
        {"client_id": "wrong"},
        {"iss": "https://wrong.example"},
        {"exp": 1},
        {"cognito:groups": "Administrators"},
    ],
)
def test_booking_verifies_real_signed_access_tokens(monkeypatch, changes):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = auth.CognitoVerifier(
        "https://test.example/pool",
        "client",
        SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key())),
    )
    monkeypatch.setattr(auth, "get_verifier", lambda: verifier)
    timestamp = int(time.time())
    token = jwt.encode(
        {
            "sub": "alice",
            "username": "alice",
            "iss": verifier.issuer,
            "iat": timestamp,
            "exp": timestamp + 300,
            "token_use": "access",
            "client_id": "client",
            **changes,
        },
        key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/booking-policy", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == (401 if changes else 200)
