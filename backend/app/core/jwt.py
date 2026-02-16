from __future__ import annotations

from datetime import datetime, timedelta, timezone
import jwt


def issue_access_token(*, subject: str, secret: str, ttl_seconds: int) -> str:
    """Генерация access токена (короткоживущий)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def issue_refresh_token(*, subject: str, secret: str, ttl_seconds: int) -> str:
    """Генерация refresh токена (долгоживущий)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_jwt(token: str, *, secret: str) -> dict:
    """Декодирование JWT токена."""
    return jwt.decode(token, secret, algorithms=["HS256"])


# Обратная совместимость (deprecated)
def issue_jwt(*, subject: str, secret: str, ttl_seconds: int) -> str:
    return issue_access_token(subject=subject, secret=secret, ttl_seconds=ttl_seconds)

