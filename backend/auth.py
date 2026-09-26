import uuid

import httpx
from fastapi import Depends, Header, HTTPException

from .config import Settings, get_settings


def current_user_id(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    if not authorization or not authorization.startswith("Bearer ") or not authorization[7:].strip():
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Authentication required."})
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=503, detail={"code": "AUTH_NOT_CONFIGURED", "message": "Authentication is unavailable."})
    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"apikey": settings.supabase_anon_key.get_secret_value(), "Authorization": authorization},
            timeout=5,
        )
        if response.status_code != 200:
            raise ValueError("Invalid session")
        return str(uuid.UUID(response.json()["id"]))
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Invalid authentication."}) from exc
