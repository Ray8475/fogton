from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.core.jwt import decode_jwt
from app.db.database import get_db
from app.db.models import Balance, User


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
    connected_ton_address: str | None = None


@router.get("", response_model=MeOut)
def get_me(
    response: Response,
    user_id: int = Depends(require_user_id),
    db: Session = Depends(get_db),
) -> MeOut:
    """Данные текущего пользователя. connected_ton_address хранится в БД и синхронизируется между устройствами."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    response.headers["Cache-Control"] = "no-store"
    return MeOut(
        id=user.id,
        telegram_user_id=user.telegram_user_id,
        connected_ton_address=user.connected_ton_address,
    )


@router.get("/balances")
def my_balances(
    user_id: int = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    """Балансы пользователя из БД (обновляются при зачислении депозитов через TON webhook)."""
    rows = db.query(Balance).filter(Balance.user_id == user_id).all()
    by_currency = {r.currency: str(r.available) for r in rows}
    balances = [
        {"currency": "TON", "available": by_currency.get("TON", "0")},
        {"currency": "USDT", "available": by_currency.get("USDT", "0")},
    ]
    return {"user_id": user_id, "balances": balances}


class DepositInstructionOut(BaseModel):
    address: str
    comment: str


@router.get("/deposit-instruction", response_model=DepositInstructionOut)
def deposit_instruction(
    user_id: int = Depends(require_user_id),
) -> DepositInstructionOut:
    """Адрес кошелька проекта и уникальный comment для атрибуции депозита (vision: один кошелёк + comment)."""
    address = settings.deposit_wallet_address or ""
    comment = f"u{user_id}"
    return DepositInstructionOut(address=address, comment=comment)


def _is_ton_address(s: str) -> bool:
    s = (s or "").strip()
    if not s or len(s) > 67:
        return False
    return (
        s.startswith("EQ") or s.startswith("UQ")
        or s.startswith("0:") or s.startswith("-1:")
    )


class WalletConnectIn(BaseModel):
    address: str


@router.post("/wallet")
def connect_wallet(
    body: WalletConnectIn,
    user_id: int = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    """Привязать TON-кошелёк (адрес получен через TON Connect на клиенте)."""
    if not _is_ton_address(body.address):
        raise HTTPException(status_code=400, detail="Invalid TON address")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.connected_ton_address = body.address.strip()
    db.commit()
    return {"ok": True, "address": user.connected_ton_address}


@router.delete("/wallet")
def disconnect_wallet(
    user_id: int = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    """Отвязать TON-кошелёк."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.connected_ton_address = None
    db.commit()
    return {"ok": True}

