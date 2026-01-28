from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.settings import settings
from app.core.jwt import decode_jwt


router = APIRouter(prefix="/me", tags=["me"])
security = HTTPBearer()


def require_user_id(creds: HTTPAuthorizationCredentials = Depends(security)) -> int:
    try:
        payload = decode_jwt(creds.credentials, secret=settings.jwt_secret)
        return int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/balances")
def my_balances(user_id: int = Depends(require_user_id)):
    # MVP stub: will be backed by balances/ledger later
    return {"user_id": user_id, "balances": [{"currency": "TON", "available": "0"}, {"currency": "USDT", "available": "0"}]}

