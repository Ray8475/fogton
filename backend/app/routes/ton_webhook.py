"""
TON webhook: приём депозитов, атрибуция по comment, запись в deposits/ledger_entries, обновление balances.
vision.md — сценарий депозита; идемпотентность по tx_hash.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.database import get_db
from app.db.models import Balance, Deposit, LedgerEntry, User

router = APIRouter(prefix="/ton", tags=["ton"])
logger = logging.getLogger("api")


def _user_id_from_comment(comment: str | None) -> int | None:
    """Comment от GET /me/deposit-instruction: u{user_id}."""
    if not comment:
        return None
    s = (comment or "").strip()
    if s.startswith("u") and len(s) > 1 and s[1:].isdigit():
        return int(s[1:])
    return None


def _normalize_currency(raw: str | None) -> str:
    if not raw:
        return "TON"
    c = (raw or "").strip().upper()
    return c if c in ("TON", "USDT") else "TON"


@router.post("/webhook")
async def ton_webhook(
    request: Request,
    x_ton_webhook_secret: str | None = Header(default=None, alias="X-Ton-Webhook-Secret"),
    db: Session = Depends(get_db),
):
    """
    Webhook от провайдера TON API. Payload: tx_hash, amount, comment, currency (опц.).
    Валидация секрета, атрибуция по comment (u{user_id}), идемпотентность по tx_hash.
    """
    if settings.ton_webhook_secret:
        if not x_ton_webhook_secret or x_ton_webhook_secret != settings.ton_webhook_secret:
            logger.warning("ton_webhook_rejected", extra={"event": "ton_webhook_rejected", "reason": "invalid_secret"})
            raise HTTPException(status_code=401, detail="Invalid TON webhook secret")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    tx_hash = (payload.get("tx_hash") or payload.get("transaction_hash") or "").strip()
    comment = (payload.get("comment") or payload.get("payload") or payload.get("memo") or "").strip() or None
    raw_amount = payload.get("amount") or payload.get("value") or 0
    try:
        amount = Decimal(str(raw_amount))
    except Exception:
        amount = Decimal("0")
    currency = _normalize_currency(payload.get("currency"))

    if not tx_hash:
        logger.warning("ton_webhook_rejected", extra={"event": "ton_webhook_rejected", "reason": "missing_tx_hash"})
        raise HTTPException(status_code=400, detail="Missing tx_hash")

    if amount <= 0:
        logger.warning("ton_webhook_rejected", extra={"event": "ton_webhook_rejected", "tx_hash": tx_hash, "reason": "amount_not_positive"})
        raise HTTPException(status_code=400, detail="Amount must be positive")

    user_id = _user_id_from_comment(comment)
    if user_id is None:
        logger.warning(
            "ton_webhook_rejected",
            extra={"event": "ton_webhook_rejected", "tx_hash": tx_hash, "reason": "user_not_found_by_comment"},
        )
        return {"ok": True, "credited": False, "reason": "user_not_found"}

    user = db.get(User, user_id)
    if user is None:
        logger.warning(
            "ton_webhook_rejected",
            extra={"event": "ton_webhook_rejected", "tx_hash": tx_hash, "reason": "user_not_found"},
        )
        return {"ok": True, "credited": False, "reason": "user_not_found"}

    existing = db.query(Deposit).filter(Deposit.tx_hash == tx_hash).first()
    if existing:
        logger.info("ton_webhook_idempotent", extra={"event": "ton_webhook_received", "tx_hash": tx_hash})
        return {"ok": True, "credited": False, "reason": "duplicate_tx_hash"}

    balance = db.query(Balance).filter(Balance.user_id == user_id, Balance.currency == currency).first()
    if balance is None:
        balance = Balance(user_id=user_id, currency=currency, available=Decimal("0"), reserved=Decimal("0"))
        db.add(balance)
        db.flush()

    deposit = Deposit(
        user_id=user_id,
        currency=currency,
        amount=amount,
        tx_hash=tx_hash,
        comment_payload=comment,
        status="credited",
    )
    db.add(deposit)
    db.flush()

    entry = LedgerEntry(
        user_id=user_id,
        currency=currency,
        delta=amount,
        reason="deposit",
        ref_type="deposit",
        ref_id=deposit.id,
    )
    db.add(entry)
    balance.available += amount
    db.commit()

    logger.info(
        "ton_webhook_attributed",
        extra={
            "event": "ton_webhook_attributed",
            "telegram_user_id": user.telegram_user_id,
            "tx_hash": tx_hash,
            "amount": str(amount),
            "currency": currency,
        },
    )
    return {"ok": True, "credited": True, "user_id": user_id}
