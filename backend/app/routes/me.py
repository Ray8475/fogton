from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.core.jwt import decode_jwt
from app.db.database import get_db
from app.db.models import User


router = APIRouter(prefix="/me", tags=["me"])
security = HTTPBearer()


def require_user_id(creds: HTTPAuthorizationCredentials = Depends(security)) -> int:
    try:
        payload = decode_jwt(creds.credentials, secret=settings.jwt_secret)
        return int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


class MeOut(BaseModel):
    id: int
    telegram_user_id: str


@router.get("", response_model=MeOut)
def get_me(user_id: int = Depends(require_user_id), db: Session = Depends(get_db)) -> MeOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return MeOut(id=user.id, telegram_user_id=user.telegram_user_id)


@router.get("/balances")
def my_balances(user_id: int = Depends(require_user_id)):
    # MVP stub: will be backed by balances/ledger later
    return {
        "user_id": user_id,
        "balances": [
            {"currency": "TON", "available": "0"},
            {"currency": "USDT", "available": "0"},
        ],
    }

