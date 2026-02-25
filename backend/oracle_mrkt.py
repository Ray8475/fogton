from __future__ import annotations

"""
Простейший «оракул» цен подарков под MRKT / TON:

- Берёт floor-прайсы подарков по аккаунту MRKT Bank через TON API (tonapi.io).
- Конвертирует nanoTON → TON.
- Шлёт их в наш backend через POST /admin/markets/prices/bulk.

Это отдельный скрипт, НЕ часть FastAPI — его можно запускать по cron/systemd.

ВАЖНО:
- требуется адрес кошелька MRKT (владелец NFT-подарков) в переменной MRKT_OWNER_ADDRESS;
- названия подарков должны совпадать с тем, как они приходят в metadata.name из TonAPI.
"""

import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import requests


TONAPI_BASE = os.getenv("TONAPI_BASE_URL", "https://tonapi.io")
TONAPI_API_KEY = os.getenv("TONAPI_API_KEY", "")  # опционально

BACKEND_BASE = os.getenv("BACKEND_BASE_URL", "https://api.fogton.ru")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
MRKT_OWNER_ADDRESS = os.getenv("MRKT_OWNER_ADDRESS", "")

# Какие подарки отслеживаем (по metadata.name)
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


def _tonapi_headers() -> Dict[str, str]:
    h: Dict[str, str] = {"Accept": "application/json"}
    if TONAPI_API_KEY:
        h["Authorization"] = f"Bearer {TONAPI_API_KEY}"
    return h


def collect_gift_prices() -> List[GiftPrice]:
    """
    Обходит все NFT на аккаунте MRKT_OWNER_ADDRESS и собирает floor-прайсы
    для отслеживаемых подарков по их имени (metadata.name).
    """
    if not MRKT_OWNER_ADDRESS:
        raise RuntimeError("MRKT_OWNER_ADDRESS is not set")

    url = f"{TONAPI_BASE}/v2/accounts/{MRKT_OWNER_ADDRESS}/nfts"
    params = {
        "limit": 1000,
        "offset": 0,
    }
    resp = requests.get(url, headers=_tonapi_headers(), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    items: List[Dict[str, Any]] = data.get("nft_items") or data.get("items") or []
    prices_by_gift: Dict[str, List[Decimal]] = {name: [] for name in TRACKED_GIFTS}

    for item in items:
        meta = item.get("metadata") or item.get("content") or {}
        name = (meta.get("name") or meta.get("nft_name") or "").strip()
        if not name:
            continue

        # ищем трекаемый подарок по префиксу имени
        gift_name_match: Optional[str] = None
        for g_name in TRACKED_GIFTS:
            if name.startswith(g_name):
                gift_name_match = g_name
                break
        if not gift_name_match:
            continue

        sale = item.get("sale") or {}
        price = sale.get("price") or {}
        value = price.get("value")
        token_name = price.get("token_name") or price.get("token") or ""
        if not value or not token_name:
            continue
        if str(token_name).upper() not in ("TON", "JETTON"):
            continue
        try:
            nano = Decimal(str(value))
            ton = nano / Decimal("1e9")
            prices_by_gift[gift_name_match].append(ton)
        except Exception:
            continue

    result: List[GiftPrice] = []
    for gift_name, plist in prices_by_gift.items():
        if not plist:
            continue
        result.append(GiftPrice(gift_name=gift_name, price_ton=min(plist)))
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

