from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.db.models import Market, Gift, Expiry


router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("")
def list_markets(db: Session = Depends(get_db)):
    """Список активных рынков из справочников gifts, expiries, markets (vision)."""
    rows = (
        db.query(Market)
        .options(
            joinedload(Market.gift),
            joinedload(Market.expiry),
        )
        .filter(Market.is_active.is_(True))
        .all()
    )
    markets = []
    for m in rows:
        gift = m.gift
        expiry = m.expiry
        if gift and gift.is_active and expiry and expiry.is_active:
            name = gift.name
            days = expiry.days
            symbol = f"{name.upper().replace(' ', '_')[:16]}-{days}D"
            price_ton = str(m.price_ton) if m.price_ton is not None else None
            price_usdt = str(m.price_usdt) if m.price_usdt is not None else None
            markets.append({
                "id": m.id,
                "gift": name,
                "expiry_days": days,
                "symbol": symbol,
                "price_ton": price_ton,
                "price_usdt": price_usdt,
                "active": True,
            })
    return {"markets": markets}

