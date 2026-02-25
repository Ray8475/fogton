from __future__ import annotations

"""
Простейший «оракул» цен подарков через Thermos Proxy API.

- Берёт floor-прайсы подарков из Thermos Proxy:
  GET https://proxy.thermos.gifts/api/v1/collections
- Конвертирует floor (строка в nanoton) → Decimal TON.
- Шлёт их в наш backend через POST /admin/markets/prices/bulk.

Это отдельный скрипт, НЕ часть FastAPI — его можно запускать по cron/systemd
или просто в отдельном терминале во время разработки.
"""

import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List

import requests


# Thermos Proxy API (публичный)
PROXY_BASE = os.getenv("THERMOS_PROXY_BASE_URL", "https://proxy.thermos.gifts")

# Наш backend
BACKEND_BASE = os.getenv("BACKEND_BASE_URL", "https://api.fogton.ru")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Какие подарки отслеживаем (по имени коллекции в Thermos Proxy)
TRACKED_GIFTS: List[str] = [
    "Plush Pepe",
    "Durov's Cap",
    "Heart Locket",
]

POLL_INTERVAL_SECONDS = int(os.getenv("ORACLE_POLL_INTERVAL", "60"))


@dataclass
class GiftPrice:
    gift_name: str
    price_ton: Decimal


def collect_gift_prices() -> List[GiftPrice]:
    """
    Обходит коллекции в Thermos Proxy и собирает floor-прайсы
    для отслеживаемых подарков по имени коллекции.
    """
    url = f"{PROXY_BASE}/api/v1/collections"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    collections: List[Dict[str, Any]] = data or []
    result: List[GiftPrice] = []

    for col in collections:
        name = (col.get("name") or "").strip()
        if name not in TRACKED_GIFTS:
            continue
        stats = col.get("stats") or {}
        floor = stats.get("floor")
        if not floor:
            continue
        try:
            nano = Decimal(str(floor))
            ton = nano / Decimal("1e9")
        except Exception:
            continue
        result.append(GiftPrice(gift_name=name, price_ton=ton))

    return result


def push_prices_to_backend(prices: List[GiftPrice]) -> None:
    """Отправляет собранные цены в backend через /admin/markets/prices/bulk."""
    if not prices:
        print("[oracle] no prices to push")
        return
    if not ADMIN_TOKEN:
        raise RuntimeError("ADMIN_TOKEN is not set")

    url = f"{BACKEND_BASE}/admin/markets/prices/bulk"
    payload = [
        {"gift_name": p.gift_name, "price_ton": str(p.price_ton)}
        for p in prices
    ]
    resp = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"},
        timeout=10,
    )
    try:
        data = resp.json()
    except Exception:
        data = resp.text
    if resp.status_code != 200:
        raise RuntimeError(f"Backend responded with {resp.status_code}: {data}")
    print(f"[oracle] pushed {len(prices)} prices, backend response: {data}")


def run_once() -> None:
    prices = collect_gift_prices()
    push_prices_to_backend(prices)


def run_loop() -> None:
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[oracle] error in run_once: {e}")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    mode = os.getenv("ORACLE_MODE", "once")
    if mode == "loop":
        run_loop()
    else:
        run_once()

