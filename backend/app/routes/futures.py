from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth_deps import require_user_id_dep
from app.db.database import get_db
from app.db.models import Balance, FuturesContract, LedgerEntry, Market


router = APIRouter(prefix="/futures", tags=["futures"])


class OfferCreateIn(BaseModel):
    market_id: int
    side: str = Field(pattern="^(long|short)$")
    qty: str = Field(..., description="Количество базового актива (подарков) в виде строки Decimal")


class OfferOut(BaseModel):
    id: int
    market_id: int
    side: str
    qty: str
    entry_price: str
    status: str


class TakeOfferIn(BaseModel):
    pass


class SettleIn(BaseModel):
    close_price: str | None = None


def _get_ton_balance(db: Session, user_id: int) -> Balance:
    bal = db.query(Balance).filter(Balance.user_id == user_id, Balance.currency == "TON").first()
    if bal is None:
        bal = Balance(user_id=user_id, currency="TON", available=Decimal("0"), reserved=Decimal("0"))
        db.add(bal)
        db.flush()
    return bal


@router.post("/offers", response_model=OfferOut)
def create_offer(
    body: OfferCreateIn,
    user_id: int = Depends(require_user_id_dep),
    db: Session = Depends(get_db),
) -> OfferOut:
    """Создать предложение по фьючерсу (эмитент размещает контракт).

    MVP: маржа считается как qty * price_ton в TON.
    """
    market = db.get(Market, body.market_id)
    if market is None or not market.is_active:
        raise HTTPException(status_code=400, detail="Market is not active or not found")
    if market.price_ton is None:
        raise HTTPException(status_code=400, detail="Market has no TON price configured")

    try:
        qty = Decimal(body.qty)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid qty")
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Qty must be positive")

    entry_price: Decimal = market.price_ton
    notional = qty * entry_price  # сколько TON замораживаем у эмитента

    bal = _get_ton_balance(db, user_id)
    if bal.available < notional:
        raise HTTPException(status_code=400, detail="Недостаточно средств для маржи эмитента")

    bal.available -= notional
    db.add(
        LedgerEntry(
            user_id=user_id,
            currency="TON",
            delta=-notional,
            reason="futures_margin",
            ref_type="futures_offer",
            ref_id=None,
        )
    )

    contract = FuturesContract(
        market_id=market.id,
        emitter_id=user_id,
        side=body.side,
        qty=qty,
        entry_price=entry_price,
        status="open",
        margin_emitter=notional,
        margin_buyer=Decimal("0"),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    return OfferOut(
        id=contract.id,
        market_id=contract.market_id,
        side=contract.side,
        qty=str(contract.qty),
        entry_price=str(contract.entry_price),
        status=contract.status,
    )


@router.get("/offers", response_model=list[OfferOut])
def list_offers(
    db: Session = Depends(get_db),
) -> list[OfferOut]:
    """Список открытых предложений (status=open, без buyer_id)."""
    rows = (
        db.query(FuturesContract)
        .filter(FuturesContract.status == "open")
        .all()
    )
    return [
        OfferOut(
            id=c.id,
            market_id=c.market_id,
            side=c.side,
            qty=str(c.qty),
            entry_price=str(c.entry_price),
            status=c.status,
        )
        for c in rows
    ]


@router.post("/offers/{offer_id}/take", response_model=OfferOut)
def take_offer(
    offer_id: int,
    _: TakeOfferIn,
    user_id: int = Depends(require_user_id_dep),
    db: Session = Depends(get_db),
) -> OfferOut:
    """Принять (купить) существующее предложение.

    Покупатель также замораживает notional TON как маржу.
    """
    contract = db.get(FuturesContract, offer_id)
    if contract is None or contract.status != "open":
        raise HTTPException(status_code=404, detail="Offer not found or not open")
    if contract.emitter_id == user_id:
        raise HTTPException(status_code=400, detail="Emitter cannot take own offer")

    notional = contract.qty * contract.entry_price
    bal = _get_ton_balance(db, user_id)
    if bal.available < notional:
        raise HTTPException(status_code=400, detail="Недостаточно средств для маржи покупателя")

    bal.available -= notional
    db.add(
        LedgerEntry(
            user_id=user_id,
            currency="TON",
            delta=-notional,
            reason="futures_margin",
            ref_type="futures_take",
            ref_id=contract.id,
        )
    )

    contract.buyer_id = user_id
    contract.margin_buyer = notional
    contract.status = "taken"
    db.commit()
    db.refresh(contract)

    return OfferOut(
        id=contract.id,
        market_id=contract.market_id,
        side=contract.side,
        qty=str(contract.qty),
        entry_price=str(contract.entry_price),
        status=contract.status,
    )


@router.post("/{contract_id}/settle", response_model=OfferOut)
def settle_contract(
    contract_id: int,
    body: SettleIn,
    db: Session = Depends(get_db),
) -> OfferOut:
    """Закрыть/рассчитать контракт по текущей или заданной цене.

    MVP: PnL считается по простой формуле, разница распределяется на счета эмитента/покупателя.
    """
    contract = db.get(FuturesContract, contract_id)
    if contract is None or contract.status not in ("taken", "open"):
        raise HTTPException(status_code=404, detail="Contract not found or not settleable")

    market = db.get(Market, contract.market_id)
    if market is None:
        raise HTTPException(status_code=400, detail="Market not found")

    if body.close_price is not None:
        try:
            close_price = Decimal(body.close_price)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid close_price")
    else:
        if market.price_ton is None:
            raise HTTPException(status_code=400, detail="Market has no TON price for settlement")
        close_price = market.price_ton

    entry = contract.entry_price
    qty = contract.qty
    move = (close_price - entry) / entry if entry != 0 else Decimal("0")

    emitter_bal = _get_ton_balance(db, contract.emitter_id)
    buyer_bal = _get_ton_balance(db, contract.buyer_id) if contract.buyer_id is not None else None

    pnl_emitter = Decimal("0")
    pnl_buyer = Decimal("0")

    if close_price > entry:
        # Цена выросла → разница идёт эмитенту
        pnl = (close_price - entry) * qty
        pnl_emitter = pnl
    elif close_price < entry:
        # Цена упала → разница идёт покупателю
        pnl = (entry - close_price) * qty
        pnl_buyer = pnl

    # Разморозка маржи и зачисление PnL
    emitter_bal.available += contract.margin_emitter + pnl_emitter
    db.add(
        LedgerEntry(
            user_id=contract.emitter_id,
            currency="TON",
            delta=contract.margin_emitter + pnl_emitter,
            reason="futures_settle",
            ref_type="futures_contract",
            ref_id=contract.id,
        )
    )

    if contract.buyer_id is not None and buyer_bal is not None:
        buyer_bal.available += contract.margin_buyer + pnl_buyer
        db.add(
            LedgerEntry(
                user_id=contract.buyer_id,
                currency="TON",
                delta=contract.margin_buyer + pnl_buyer,
                reason="futures_settle",
                ref_type="futures_contract",
                ref_id=contract.id,
            )
        )

    contract.status = "closed"
    contract.close_price = close_price
    contract.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(contract)

    return OfferOut(
        id=contract.id,
        market_id=contract.market_id,
        side=contract.side,
        qty=str(contract.qty),
        entry_price=str(contract.entry_price),
        status=contract.status,
    )

