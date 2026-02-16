from __future__ import annotations

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.core.telegram_auth import verify_telegram_webapp_init_data
from app.core.jwt import issue_access_token, issue_refresh_token
from app.db.database import get_db
from app.db.models import User


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("api")


class TelegramAuthIn(BaseModel):
    init_data: str


@router.post("/telegram")
def auth_telegram(
    payload: TelegramAuthIn,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Аутентификация через Telegram initData. Устанавливает access и refresh токены в http-only cookies.
    Возвращает только статус успеха (токены в cookies, недоступны из JS).
    """
    try:
        parsed = verify_telegram_webapp_init_data(payload.init_data, settings.bot_token)
    except ValueError as e:
        logger.warning("Auth failed: initData validation error", extra={"event": "auth_failed", "detail": str(e)})
        raise HTTPException(status_code=401, detail=str(e))

    raw_user = parsed.get("user")
    if not raw_user:
        raise HTTPException(status_code=400, detail="initData missing user")

    try:
        user_obj = json.loads(raw_user)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="initData user is not valid JSON")

    telegram_user_id = str(user_obj.get("id"))
    if telegram_user_id in ("None", ""):
        raise HTTPException(status_code=400, detail="initData user.id missing")

    user = db.query(User).filter(User.telegram_user_id == telegram_user_id).one_or_none()
    if user is None:
        user = User(telegram_user_id=telegram_user_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token = issue_access_token(
        subject=str(user.id),
        secret=settings.jwt_secret,
        ttl_seconds=settings.jwt_ttl_seconds,
    )
    refresh_token = issue_refresh_token(
        subject=str(user.id),
        secret=settings.jwt_refresh_secret,
        ttl_seconds=settings.jwt_refresh_ttl_seconds,
    )

    cookie_options = {
        "httponly": True,
        "secure": True,
        "samesite": "strict",
        "path": "/",
    }
    response.set_cookie("ACCESS_TOKEN", access_token, max_age=settings.jwt_ttl_seconds, **cookie_options)
    response.set_cookie("REFRESH_TOKEN", refresh_token, max_age=settings.jwt_refresh_ttl_seconds, **cookie_options)

    logger.info(
        "Auth success",
        extra={"event": "auth_success", "telegram_user_id": user.telegram_user_id},
    )
    return {"ok": True, "user": {"id": user.id, "telegram_user_id": user.telegram_user_id}}

