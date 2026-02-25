from __future__ import annotations

"""
Одноразовый скрипт для создания рынков по всем подаркам из таблицы gifts.

Использует текущую DATABASE_URL и модели SQLAlchemy.
Запускать из корня проекта:
    python backend/seed_markets.py
"""

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, Base, engine
from app.db.models import Gift, Expiry, Market


def main() -> None:
    # Убедимся, что таблицы созданы (если API ещё не запускали)
    Base.metadata.create_all(bind=engine)

    # Простая миграция для SQLite: добавляем gifts.image_url / gifts.total_count при необходимости
    with engine.connect() as conn:
        r = conn.execute(text("PRAGMA table_info(gifts)"))
        columns = [row[1] for row in r.fetchall()]
        if "image_url" not in columns:
            conn.execute(text("ALTER TABLE gifts ADD COLUMN image_url VARCHAR(512) NULL"))
        if "total_count" not in columns:
            conn.execute(text("ALTER TABLE gifts ADD COLUMN total_count INTEGER NULL"))
        conn.commit()

    db: Session = SessionLocal()
    try:
        # expiry 7 дней
        expiry = db.query(Expiry).filter(Expiry.days == 7).first()
        if expiry is None:
            expiry = Expiry(days=7, settlement_at=None, is_active=True)
            db.add(expiry)
            db.flush()

        # Берём все активные подарки и создаём по рынку на каждый (для expiry=7 дней)
        gifts = db.query(Gift).filter(Gift.is_active == True).all()  # noqa: E712

        for idx, gift in enumerate(gifts, start=1):

            market = (
                db.query(Market)
                .filter(Market.gift_id == gift.id, Market.expiry_id == expiry.id)
                .first()
            )
            if market is None:
                # простые стартовые курсы в TON
                base_price = Decimal("1.0") + Decimal(idx - 1) * Decimal("0.5")
                market = Market(
                    gift_id=gift.id,
                    expiry_id=expiry.id,
                    is_active=True,
                    price_ton=base_price,
                    price_usdt=None,
                )
                db.add(market)

        db.commit()
        print("Seed completed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

