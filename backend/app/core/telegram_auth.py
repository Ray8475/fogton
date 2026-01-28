from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qsl


def verify_telegram_webapp_init_data(init_data: str, bot_token: str) -> dict:
    """
    Verifies Telegram WebApp initData signature.
    Returns parsed key/value dict on success; raises ValueError on failure.
    """
    if not init_data:
        raise ValueError("initData is empty")
    if not bot_token:
        raise ValueError("BOT_TOKEN is not configured")

    pairs = list(parse_qsl(init_data, keep_blank_values=True))
    data = dict(pairs)
    received_hash = data.get("hash")
    if not received_hash:
        raise ValueError("initData missing hash")

    check_pairs = [(k, v) for (k, v) in pairs if k != "hash"]
    check_pairs.sort(key=lambda kv: kv[0])
    data_check_string = "\n".join([f"{k}={v}" for (k, v) in check_pairs])

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("initData hash mismatch")

    return data

