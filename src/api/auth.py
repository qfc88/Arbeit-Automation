"""
Minimal JWT admin auth.

Public routes do not call ``require_admin``. Admin routes declare it as a
FastAPI dependency; the VPS nginx also refuses admin paths so this is the
second line of defence.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

JWT_SECRET = os.getenv("API_JWT_SECRET")
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("API_JWT_EXPIRE_HOURS", "12"))

_bearer = HTTPBearer(auto_error=False)


def issue_admin_token(subject: str) -> str:
    if not JWT_SECRET:
        raise RuntimeError("API_JWT_SECRET not set")
    payload = {
        "sub": subject,
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin auth disabled: API_JWT_SECRET not configured",
        )
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin token")
    return payload
