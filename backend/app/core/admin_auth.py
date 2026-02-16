from __future__ import annotations

import logging
from fastapi import Depends, HTTPException, Header

from app.core.settings import settings


logger = logging.getLogger("api")


def require_admin_token(authorization: str | None = Header(None)) -> None:
    """
    Dependency для проверки ADMIN_TOKEN в заголовке Authorization.
    Формат: Authorization: Bearer <ADMIN_TOKEN>
    """
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="Admin functionality is disabled")
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing admin token")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization[7:].strip()
    if token != settings.admin_token:
        logger.warning("Admin auth failed", extra={"event": "admin_auth_failed"})
        raise HTTPException(status_code=401, detail="Invalid admin token")
