from __future__ import annotations

from pydantic import BaseModel
from dotenv import load_dotenv
import os


load_dotenv()


class Settings(BaseModel):
    bot_token: str = os.getenv("BOT_TOKEN", "")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_refresh_secret: str = os.getenv("JWT_REFRESH_SECRET", "change-me-refresh")
    jwt_ttl_seconds: int = int(os.getenv("JWT_TTL_SECONDS", "300"))  # 5 минут — access token
    jwt_refresh_ttl_seconds: int = int(os.getenv("JWT_REFRESH_TTL_SECONDS", "604800"))  # 7 дней — refresh token
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    admin_token: str = os.getenv("ADMIN_TOKEN", "")

    ton_webhook_secret: str = os.getenv("TON_WEBHOOK_SECRET", "")
    deposit_wallet_address: str = os.getenv("TON_PROJECT_WALLET_ADDRESS", "")


settings = Settings()

