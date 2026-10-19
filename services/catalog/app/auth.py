"""Verify Cognito access tokens before trusting identity or administrator membership."""

from functools import lru_cache
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError
from pydantic import BaseModel

from app.config import get_settings

bearer = HTTPBearer(auto_error=False)


class Principal(BaseModel):
    user_id: str
    username: str
    role: Literal["visitor", "administrator"]


class CognitoVerifier:
    def __init__(self, issuer: str, client_id: str, jwks_client: PyJWKClient | None = None):
        self.issuer = issuer
        self.client_id = client_id
        self.jwks = jwks_client or PyJWKClient(
            f"{issuer}/.well-known/jwks.json", cache_jwk_set=True, lifespan=300, timeout=5
        )

    def verify(self, token: str) -> Principal:
        try:
            if len(token) > 16384:
                raise jwt.InvalidTokenError("Token is too large")
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise jwt.InvalidTokenError("Unexpected signing algorithm or key identifier")
            # Keys are fetched only from our configured pool, never from the token's issuer/jku.
            key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={
                    "verify_aud": False,  # Cognito access tokens identify the app with client_id.
                    "require": ["exp", "iat", "iss", "sub", "token_use", "client_id"],
                },
            )
            if claims["token_use"] != "access" or claims["client_id"] != self.client_id:
                raise jwt.InvalidTokenError("Wrong token purpose or client")
            subject = claims["sub"]
            username = claims.get("username", subject)
            groups = claims.get("cognito:groups", [])
            if not isinstance(subject, str) or not subject:
                raise jwt.InvalidTokenError("Missing subject")
            if not isinstance(username, str) or not username:
                raise jwt.InvalidTokenError("Invalid username")
            if not isinstance(groups, list) or not all(isinstance(group, str) for group in groups):
                raise jwt.InvalidTokenError("Invalid groups")
            return Principal(
                user_id=subject,
                username=username,
                role="administrator" if "Administrators" in groups else "visitor",
            )
        except PyJWKClientConnectionError as exc:
            raise HTTPException(
                status_code=503, detail="Identity verification is unavailable"
            ) from exc
        except (jwt.InvalidTokenError, PyJWKClientError, ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=401,
                detail="A valid Cognito access token is required",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc


@lru_cache
def get_verifier() -> CognitoVerifier:
    settings = get_settings()
    if not settings.auth_configured:
        raise HTTPException(status_code=503, detail="Cognito authentication is not configured")
    issuer = (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}"
    )
    return CognitoVerifier(issuer, settings.cognito_app_client_id)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Sign in to continue",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_verifier().verify(credentials.credentials)


CurrentUser = Annotated[Principal, Depends(current_user)]


def administrator(user: CurrentUser) -> Principal:
    if user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator access is required")
    return user


Administrator = Annotated[Principal, Depends(administrator)]
