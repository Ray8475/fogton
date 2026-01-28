from __future__ import annotations

from datetime import datetime, timedelta, timezone
import jwt


def issue_jwt(*, subject: str, secret: str, ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_jwt(token: str, *, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"])

