from __future__ import annotations

import logging
from fastapi import HTTPException, Request, Response
import jwt

from app.core.settings import settings
from app.core.jwt import decode_jwt, issue_access_token, issue_refresh_token


logger = logging.getLogger("api")


def require_user_id_dep(request: Request, response: Response) -> int:
    """
    Dependency для проверки авторизации через http-only cookies (ACCESS_TOKEN, REFRESH_TOKEN).
    Автоматически обновляет токены при истечении access токена (если refresh валиден).
    Возвращает user_id из токена.
    """
    access_token = request.cookies.get("ACCESS_TOKEN")
    refresh_token = request.cookies.get("REFRESH_TOKEN")

    if not access_token or not refresh_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Пытаемся проверить access токен
    try:
        payload = decode_jwt(access_token, secret=settings.jwt_secret)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        # Access токен истек, пытаемся обновить через refresh
        pass
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid access token")

    # Access токен истек, проверяем refresh токен
    try:
        payload = decode_jwt(refresh_token, secret=settings.jwt_refresh_secret)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token type")
        user_id = int(payload["sub"])

        # Генерируем новую пару токенов
        new_access_token = issue_access_token(
            subject=str(user_id),
            secret=settings.jwt_secret,
            ttl_seconds=settings.jwt_ttl_seconds,
        )
        new_refresh_token = issue_refresh_token(
            subject=str(user_id),
            secret=settings.jwt_refresh_secret,
            ttl_seconds=settings.jwt_refresh_ttl_seconds,
        )

        # Устанавливаем новые токены в cookies
        cookie_options = {
            "httponly": True,
            "secure": True,
            "samesite": "strict",
            "path": "/",
        }
        response.set_cookie("ACCESS_TOKEN", new_access_token, max_age=settings.jwt_ttl_seconds, **cookie_options)
        response.set_cookie("REFRESH_TOKEN", new_refresh_token, max_age=settings.jwt_refresh_ttl_seconds, **cookie_options)

        logger.debug("Tokens refreshed", extra={"event": "token_refreshed", "user_id": user_id})
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
