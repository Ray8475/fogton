from __future__ import annotations

from fastapi import FastAPI

from app.db.database import Base, engine
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.me import router as me_router
from app.routes.markets import router as markets_router
from app.routes.ton_webhook import router as ton_router


def create_app() -> FastAPI:
    app = FastAPI(title="Gifts Futures API")

    # MVP: create tables automatically (later: Alembic migrations)
    Base.metadata.create_all(bind=engine)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(markets_router)
    app.include_router(ton_router)
    return app


app = create_app()

