from __future__ import annotations

from pydantic import BaseModel
from dotenv import load_dotenv
import os


load_dotenv()


class Settings(BaseModel):
    bot_token: str = os.getenv("BOT_TOKEN", "")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_ttl_seconds: int = int(os.getenv("JWT_TTL_SECONDS", "300"))  # 5 минут — сессия
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    admin_token: str = os.getenv("ADMIN_TOKEN", "")

    ton_webhook_secret: str = os.getenv("TON_WEBHOOK_SECRET", "")


settings = Settings()

