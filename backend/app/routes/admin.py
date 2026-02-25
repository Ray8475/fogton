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


# --- Обновление цен рынков (для внешнего оракула) ---


class MarketPriceItem(BaseModel):
    gift_name: str | None = None
    market_id: int | None = None
    price_ton: str | None = None
    price_usdt: str | None = None


@router.post("/markets/prices/bulk")
def bulk_update_market_prices(
    items: list[MarketPriceItem],
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    """
    Пакетное обновление цен рынков.

    Предназначено для внешнего сервиса-оракула, который собирает цены с маркетплейсов
    (Portals, MRKT, Tonnel и т.п.) и пушит их сюда.

    Формат тела:
    [
      { "gift_name": "Plush Pepe", "price_ton": "1.23" },
      { "market_id": 1, "price_ton": "4.56", "price_usdt": "2.34" }
    ]

    - Если указан market_id — обновляется конкретный рынок.
    - Если указан gift_name — обновляются все активные рынки для этого подарка.
    """
    if not items:
        raise HTTPException(status_code=400, detail="Empty payload")

    updated = 0
    for item in items:
        if item.price_ton is None and item.price_usdt is None:
            continue

        # Парсим Decimal
        price_ton_dec: Decimal | None = None
        price_usdt_dec: Decimal | None = None
        try:
            if item.price_ton is not None:
                price_ton_dec = Decimal(item.price_ton)
            if item.price_usdt is not None:
                price_usdt_dec = Decimal(item.price_usdt)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid price format for item {item}")

        q = db.query(Market)
        if item.market_id is not None:
            q = q.filter(Market.id == item.market_id)
        elif item.gift_name:
            q = q.join(Gift, Gift.id == Market.gift_id).filter(Gift.name == item.gift_name)
        else:
            continue

        markets = q.all()
        if not markets:
            continue

        for m in markets:
            if price_ton_dec is not None:
                m.price_ton = price_ton_dec
            if price_usdt_dec is not None:
                m.price_usdt = price_usdt_dec
            updated += 1

    if updated == 0:
        return {"updated": 0}

    db.commit()
    logger.info(
        "Markets prices bulk updated",
        extra={
            "event": "admin_markets_price_bulk_updated",
            "updated": updated,
            "items_count": len(items),
        },
    )
    return {"updated": updated}
