from __future__ import annotations

"""
Простейший «оракул» цен подарков под MRKT / TON:

- Берёт floor-прайсы подарков через TON API (tonapi.io, метод getItemsFromCollection).
- Конвертирует nanoTON → TON.
- Шлёт их в наш backend через POST /admin/markets/prices/bulk.

Это отдельный скрипт, НЕ часть FastAPI — его можно запускать по cron/systemd.

ВАЖНО:
- здесь зашита только структура; реальные адреса коллекций MRKT/TON и,
  при необходимости, точные параметры tonapi, нужно заполнить руками.
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

# Соответствие: имя подарка → адрес коллекции в TON (MRKT/Portals и т.п.)
# TODO: заполнить реальными адресами коллекций
GIFT_COLLECTIONS: Dict[str, str] = {
    "Plush Pepe": "<TON_COLLECTION_ADDRESS_PLUSH_PEPE>",
    "Durov's Cap": "<TON_COLLECTION_ADDRESS_DUROVS_CAP>",
    "Heart Locket": "<TON_COLLECTION_ADDRESS_HEART_LOCKET>",
}

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


def fetch_floor_price_for_collection(collection_address: str) -> Optional[Decimal]:
    """
    Берём список NFT из коллекции через TonAPI и ищем минимальную цену (floor).

    Основано на документации TonAPI getItemsFromCollection:
    - каждая NFT имеет поле sale.price.value (в nanoTON), если она выставлена на продажу.

    Если активных продаж нет — возвращаем None.
    """
    # Примерный URL; при необходимости скорректировать под актуальный TonAPI.
    url = f"{TONAPI_BASE}/v2/nfts/collections/{collection_address}/items"
    params = {
        "limit": 200,
        "offset": 0,
    }
    resp = requests.get(url, headers=_tonapi_headers(), params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    items: List[Dict[str, Any]] = data.get("nft_items") or data.get("items") or []
    prices: List[Decimal] = []
    for item in items:
        sale = item.get("sale") or {}
        price = sale.get("price") or {}
        value = price.get("value")
        token_name = price.get("token_name") or price.get("token") or ""
        if not value or not token_name:
            continue
        # Нас интересуют цены в TON
        if str(token_name).upper() not in ("TON", "JETTON"):
            continue
        try:
            # TonAPI обычно отдаёт nanoTON; делим на 1e9
            nano = Decimal(str(value))
            prices.append(nano / Decimal("1e9"))
        except Exception:
            continue

    if not prices:
        return None
    return min(prices)


def collect_gift_prices() -> List[GiftPrice]:
    """Обходит все подарки из GIFT_COLLECTIONS и собирает floor-прайсы."""
    result: List[GiftPrice] = []
    for gift_name, coll in GIFT_COLLECTIONS.items():
        if not coll or coll.startswith("<TON_COLLECTION_ADDRESS"):
            # коллекция ещё не настроена
            continue
        try:
            price = fetch_floor_price_for_collection(coll)
        except Exception as e:
            print(f"[oracle] error fetching price for {gift_name}: {e}")
            continue
        if price is None:
            continue
        result.append(GiftPrice(gift_name=gift_name, price_ton=price))
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

