from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Integer, Boolean, Numeric, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


# --- Справочники (vision.md: Модель данных) ---


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("telegram_user_id", name="uq_users_telegram_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Gift(Base):
    __tablename__ = "gifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Expiry(Base):
    __tablename__ = "expiries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    days: Mapped[int] = mapped_column(Integer, nullable=False)  # например 7, 30
    settlement_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # дата/время расчёта
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gift_id: Mapped[int] = mapped_column(ForeignKey("gifts.id"), nullable=False)
    expiry_id: Mapped[int] = mapped_column(ForeignKey("expiries.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    gift: Mapped["Gift"] = relationship("Gift", foreign_keys=[gift_id])
    expiry: Mapped["Expiry"] = relationship("Expiry", foreign_keys=[expiry_id])


# --- Балансы и операции (денежный учёт) ---

CURRENCY_LEN = 8  # "TON" | "USDT"


class Balance(Base):
    __tablename__ = "balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(CURRENCY_LEN), nullable=False)  # TON | USDT
    available: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"), nullable=False)
    reserved: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"), nullable=False)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(CURRENCY_LEN), nullable=False)
    delta: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)  # + или -
    reason: Mapped[str] = mapped_column(String(32), nullable=False)  # deposit, trade, withdraw, adjustment
    ref_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# --- Депозиты (TON/USDT) ---


class Deposit(Base):
    __tablename__ = "deposits"
    __table_args__ = (UniqueConstraint("tx_hash", name="uq_deposits_tx_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(CURRENCY_LEN), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    tx_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    comment_payload: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # received | credited | rejected
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# --- Торговля (пока без конкретной торговой модели) ---


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # long | short
    qty: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # buy | sell
    qty: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    fee_currency: Mapped[str | None] = mapped_column(String(CURRENCY_LEN), nullable=True)
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(36, 18), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

