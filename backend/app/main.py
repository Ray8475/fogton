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

    # Добавить колонку connected_ton_address в существующие БД (миграция без Alembic)
    if "sqlite" in (settings.database_url or ""):
        with engine.connect() as conn:
            r = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in r.fetchall()]
            if "connected_ton_address" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN connected_ton_address VARCHAR(68) NULL"))
                conn.commit()

    app.include_router(health_router)
    # Онбординг Mini App: auth + /me + markets
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(markets_router)
    app.include_router(ton_webhook_router)
    return app


app = create_app()
