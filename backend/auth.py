"""Verify Supabase access tokens before using their subject as an owner ID.

Asymmetric signing keys are checked against the project's public JWKS. Legacy
HS256 access tokens are checked by Supabase Auth; the JWT secret is never used
or loaded by this application.
"""

from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse
import uuid

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, Request
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError

from .config import Settings, get_settings


class InvalidAccessToken(Exception):
    """The token is absent, invalid, expired, or is not a user access token."""


class AuthUnavailable(Exception):
    """The configured identity provider could not be reached."""


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    claims: dict[str, Any]


class SupabaseTokenVerifier:
    """Verify user access tokens with a configured Supabase signing mode.

    ``signing_mode`` must match the project's active signing mode. During a
    migration the API can use ``auto`` to accept both asymmetric and legacy
    tokens, with each algorithm constrained to its separate verification path.
    """

    ASYMMETRIC_ALGORITHMS = frozenset({"RS256", "ES256", "EdDSA"})

    def __init__(
        self,
        supabase_url: str,
        publishable_key: str,
        signing_mode: Literal["asymmetric", "legacy", "auto"] = "asymmetric",
        *,
        http_client: httpx.Client | None = None,
        jwks_client: PyJWKClient | None = None,
    ) -> None:
        url = supabase_url.rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("SUPABASE_URL must be an HTTPS project origin.")
        if not publishable_key:
            raise ValueError("A Supabase publishable key is required.")
        if signing_mode not in {"asymmetric", "legacy", "auto"}:
            raise ValueError("Unsupported Supabase signing mode.")
        self.issuer = f"{url}/auth/v1"
        self.publishable_key = publishable_key
        self.signing_mode = signing_mode
        self.http_client = http_client or httpx.Client(timeout=5.0)
        self.jwks_client = jwks_client or PyJWKClient(
            f"{self.issuer}/.well-known/jwks.json",
            cache_jwk_set=True,
            lifespan=600,
            timeout=5,
        )

    def verify(self, token: str) -> AuthenticatedUser:
        if not token or len(token) > 16384:
            raise InvalidAccessToken()
        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
        except InvalidTokenError as exc:
            raise InvalidAccessToken() from exc
        if algorithm in self.ASYMMETRIC_ALGORITHMS and self.signing_mode in {"asymmetric", "auto"}:
            return self._verify_asymmetric(token, algorithm)
        if algorithm == "HS256" and self.signing_mode in {"legacy", "auto"}:
            return self._verify_legacy(token)
        raise InvalidAccessToken()

    def _verify_asymmetric(self, token: str, algorithm: str) -> AuthenticatedUser:
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            # The configured allowlist remains independent of token header and
            # JWK metadata. Also require the selected JWK to match the header.
            if signing_key.algorithm_name != algorithm:
                raise InvalidAccessToken()
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self.ASYMMETRIC_ALGORITHMS),
                audience="authenticated",
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except PyJWKClientConnectionError as exc:
            raise AuthUnavailable() from exc
        except (InvalidTokenError, PyJWKClientError, ValueError) as exc:
            raise InvalidAccessToken() from exc
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or claims.get("role") != "authenticated":
            raise InvalidAccessToken()
        if claims.get("is_anonymous") is True:
            raise InvalidAccessToken()
        return AuthenticatedUser(user_id=subject, claims=claims)

    def _verify_legacy(self, token: str) -> AuthenticatedUser:
        # Supabase's JWKS never exposes legacy shared secrets. The Auth server
        # validates this token and returns its canonical user ID.
        try:
            response = self.http_client.get(
                f"{self.issuer}/user",
                headers={"apikey": self.publishable_key, "Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as exc:
            raise AuthUnavailable() from exc
        if response.status_code >= 500:
            raise AuthUnavailable()
        if response.status_code != 200:
            raise InvalidAccessToken()
        try:
            user = response.json()
        except ValueError as exc:
            raise AuthUnavailable() from exc
        subject = user.get("id") if isinstance(user, dict) else None
        if not isinstance(subject, str) or not subject or user.get("is_anonymous") is True:
            raise InvalidAccessToken()
        return AuthenticatedUser(user_id=subject, claims={"sub": subject, "role": "authenticated"})


def require_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency for authenticated, owner-scoped routes."""
    authorization = request.headers.get("authorization", "")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Sign in is required."})
    verifier = getattr(request.app.state, "auth_verifier", None)
    if verifier is None:
        raise HTTPException(status_code=503, detail={"code": "AUTH_UNAVAILABLE", "message": "Authentication is unavailable."})
    try:
        return verifier.verify(parts[1])
    except InvalidAccessToken as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Sign in again."}) from exc
    except AuthUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "AUTH_UNAVAILABLE", "message": "Authentication is unavailable."}) from exc


def current_user_id(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """Resolve the owner for v1 routes through the Supabase Auth user endpoint."""
    if not authorization or not authorization.startswith("Bearer ") or not authorization[7:].strip():
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Authentication required."})
    if not settings.authentication_enabled:
        raise HTTPException(status_code=503, detail={"code": "AUTH_NOT_CONFIGURED", "message": "Authentication is unavailable."})
    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"apikey": settings.supabase_auth_api_key, "Authorization": authorization},
            timeout=5,
        )
        if response.status_code != 200:
            raise ValueError("Invalid session")
        return str(uuid.UUID(response.json()["id"]))
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Invalid authentication."}) from exc
