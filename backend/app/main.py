"""
API: healthz и запуск (tasklist — итерация 2).
vision.md, conventions.md.
"""
from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from sqlalchemy import text

from app.core.settings import settings
from app.db.database import Base, engine
from app.db import models  # noqa: F401 — регистрация таблиц в Base.metadata
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.me import router as me_router
from app.routes.markets import router as markets_router
from app.routes.ton_webhook import router as ton_webhook_router
from app.routes.admin import router as admin_router
from app.routes.futures import router as futures_router


class KeepAliveMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Keep-Alive"] = "timeout=75, max=1000"
        response.headers["Connection"] = "keep-alive"
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="Gifts Futures API")

    app.add_middleware(KeepAliveMiddleware)

    # CORS: позволяем Mini App (GitHub Pages / app.fogton.ru) ходить в API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # для MVP можно ослабить, потом сузим до конкретных доменов
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    Base.metadata.create_all(bind=engine)

    # Простые миграции для SQLite (без Alembic)
    if "sqlite" in (settings.database_url or ""):
        with engine.connect() as conn:
            # users.connected_ton_address
            r = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in r.fetchall()]
            if "connected_ton_address" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN connected_ton_address VARCHAR(68) NULL"))
                conn.commit()
            # markets.price_ton, markets.price_usdt
            r2 = conn.execute(text("PRAGMA table_info(markets)"))
            m_columns = [row[1] for row in r2.fetchall()]
            if "price_ton" not in m_columns:
                conn.execute(text("ALTER TABLE markets ADD COLUMN price_ton NUMERIC"))
            if "price_usdt" not in m_columns:
                conn.execute(text("ALTER TABLE markets ADD COLUMN price_usdt NUMERIC"))
            # gifts.image_url, gifts.total_count, уникальность имени
            r3 = conn.execute(text("PRAGMA table_info(gifts)"))
            g_columns = [row[1] for row in r3.fetchall()]
            if "image_url" not in g_columns:
                conn.execute(text("ALTER TABLE gifts ADD COLUMN image_url VARCHAR(512) NULL"))
            if "total_count" not in g_columns:
                conn.execute(text("ALTER TABLE gifts ADD COLUMN total_count INTEGER NULL"))
            # индекс уникальности по name, если его ещё нет
            r4 = conn.execute(text("PRAGMA index_list(gifts)"))
            idx_names = [row[1] for row in r4.fetchall()]
            if "uq_gifts_name" not in idx_names:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_gifts_name ON gifts(name)"))
            conn.commit()

    app.include_router(health_router)
    # Онбординг Mini App: auth + /me + markets
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(markets_router)
    app.include_router(ton_webhook_router)
    # Админ-панель: управление справочниками и корректировка балансов
    app.include_router(admin_router)
    # Фьючерсы на подарки: предложения, принятие и расчёт
    app.include_router(futures_router)
    return app


app = create_app()
