from __future__ import annotations

"""
Синхронизация справочника подарков (gifts) из Thermos Proxy API.

- Берём список коллекций: GET https://proxy.thermos.gifts/api/v1/collections
- Для каждой коллекции создаём/обновляем Gift:
  - name
  - image_url
  - total_count

Запускать из корня проекта:

    python backend/sync_gifts_from_thermos.py
"""

import os
from decimal import Decimal

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.db.database import Base, SessionLocal, engine
from app.db.models import Gift


load_dotenv()

PROXY_BASE = os.getenv("THERMOS_PROXY_BASE_URL", "https://proxy.thermos.gifts")


def sync_gifts() -> None:
    # Убедимся, что таблицы созданы
    Base.metadata.create_all(bind=engine)

    url = f"{PROXY_BASE}/api/v1/collections"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        raise RuntimeError("Unexpected response format from Thermos Proxy")

    db: Session = SessionLocal()
    try:
        updated = 0
        created = 0
        for col in data:
            name = (col.get("name") or "").strip()
            if not name:
                continue
            image_url = col.get("image_url")
            stats = col.get("stats") or {}
            total_count = stats.get("count")

            gift = db.query(Gift).filter(Gift.name == name).one_or_none()
            if gift is None:
                gift = Gift(name=name, image_url=image_url, total_count=total_count, is_active=True)
                db.add(gift)
                created += 1
            else:
                changed = False
                if image_url and gift.image_url != image_url:
                    gift.image_url = image_url
                    changed = True
                if isinstance(total_count, int) and gift.total_count != total_count:
                    gift.total_count = total_count
                    changed = True
                if changed:
                    updated += 1

        db.commit()
        print(f"Sync completed. created={created}, updated={updated}")
    finally:
        db.close()


if __name__ == "__main__":
    sync_gifts()

