from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_token
from app.core.settings import settings
from app.db.database import get_db
from app.db.models import Balance, Expiry, Gift, LedgerEntry, Market


router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger("api")


# --- Управление справочниками ---


class ToggleActiveIn(BaseModel):
    is_active: bool


@router.patch("/gifts/{gift_id}")
def toggle_gift(
    gift_id: int,
    body: ToggleActiveIn,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    """Включить/выключить gift (is_active)."""
    gift = db.get(Gift, gift_id)
    if gift is None:
        raise HTTPException(status_code=404, detail="Gift not found")
    
    old_value = gift.is_active
    gift.is_active = body.is_active
    db.commit()
    
    logger.info(
        "Gift toggled",
        extra={
            "event": "admin_gift_toggled",
            "gift_id": gift_id,
            "gift_name": gift.name,
            "old_value": old_value,
            "new_value": body.is_active,
        },
    )
    return {"id": gift.id, "name": gift.name, "is_active": gift.is_active}


@router.patch("/expiries/{expiry_id}")
def toggle_expiry(
    expiry_id: int,
    body: ToggleActiveIn,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    """Включить/выключить expiry (is_active)."""
    expiry = db.get(Expiry, expiry_id)
    if expiry is None:
        raise HTTPException(status_code=404, detail="Expiry not found")
    
    old_value = expiry.is_active
    expiry.is_active = body.is_active
    db.commit()
    
    logger.info(
        "Expiry toggled",
        extra={
            "event": "admin_expiry_toggled",
            "expiry_id": expiry_id,
            "expiry_days": expiry.days,
            "old_value": old_value,
            "new_value": body.is_active,
        },
    )
    return {"id": expiry.id, "days": expiry.days, "is_active": expiry.is_active}


@router.patch("/markets/{market_id}")
def toggle_market(
    market_id: int,
    body: ToggleActiveIn,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    """Включить/выключить market (is_active)."""
    market = db.get(Market, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")
    
    old_value = market.is_active
    market.is_active = body.is_active
    db.commit()
    
    logger.info(
        "Market toggled",
        extra={
            "event": "admin_market_toggled",
            "market_id": market_id,
            "gift_id": market.gift_id,
            "expiry_id": market.expiry_id,
            "old_value": old_value,
            "new_value": body.is_active,
        },
    )
    return {"id": market.id, "gift_id": market.gift_id, "expiry_id": market.expiry_id, "is_active": market.is_active}


# --- Корректировка баланса ---


class BalanceAdjustIn(BaseModel):
    user_id: int
    currency: str
    delta: str  # Decimal как строка для валидации
    reason: str  # Обязательно


@router.post("/balances/adjust")
def adjust_balance(
    body: BalanceAdjustIn,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    """
    Корректировка баланса пользователя.
    Обязательно указывать reason (записывается в ledger_entries с reason="adjustment").
    Проверка: баланс не должен стать отрицательным после корректировки.
    """
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required for balance adjustment")
    
    currency = (body.currency or "").strip().upper()
    if currency not in ("TON", "USDT"):
        raise HTTPException(status_code=400, detail="Currency must be TON or USDT")
    
    try:
        delta = Decimal(body.delta)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid delta format")
    
    if delta == 0:
        raise HTTPException(status_code=400, detail="Delta cannot be zero")
    
    # Проверяем существование пользователя
    from app.db.models import User
    user = db.get(User, body.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Получаем или создаём баланс
    balance = db.query(Balance).filter(Balance.user_id == body.user_id, Balance.currency == currency).first()
    if balance is None:
        balance = Balance(user_id=body.user_id, currency=currency, available=Decimal("0"), reserved=Decimal("0"))
        db.add(balance)
        db.flush()
    
    # Проверяем, что баланс не станет отрицательным
    new_available = balance.available + delta
    if new_available < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance: current={balance.available}, delta={delta}, result would be {new_available}",
        )
    
    # Создаём запись в ledger
    ledger_entry = LedgerEntry(
        user_id=body.user_id,
        currency=currency,
        delta=delta,
        reason="adjustment",
        ref_type="admin_adjustment",
        ref_id=None,
    )
    db.add(ledger_entry)
    
    # Обновляем баланс
    balance.available = new_available
    db.commit()
    
    logger.info(
        "Balance adjusted",
        extra={
            "event": "admin_balance_adjusted",
            "user_id": body.user_id,
            "currency": currency,
            "delta": str(delta),
            "old_available": str(balance.available - delta),
            "new_available": str(balance.available),
            "reason": body.reason,
        },
    )
    
    return {
        "user_id": body.user_id,
        "currency": currency,
        "delta": str(delta),
        "old_available": str(balance.available - delta),
        "new_available": str(balance.available),
        "reason": body.reason,
    }
