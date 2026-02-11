"""
API: healthz и запуск (tasklist — итерация 2).
vision.md, conventions.md.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.db.database import Base, engine
from app.db import models  # noqa: F401 — регистрация таблиц в Base.metadata
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.me import router as me_router
from app.routes.markets import router as markets_router


def create_app() -> FastAPI:
    app = FastAPI(title="Gifts Futures API")
    Base.metadata.create_all(bind=engine)
    app.include_router(health_router)
     # Онбординг Mini App: auth + /me + markets
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(markets_router)
    return app


app = create_app()
