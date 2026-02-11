from __future__ import annotations

import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.settings import settings
from app.core.telegram_auth import verify_telegram_webapp_init_data
from app.core.jwt import issue_jwt
from app.db.database import get_db, engine
from app.db import models  # noqa: F401
from app.db.models import User
from app.db.database import Base


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("api")


class TelegramAuthIn(BaseModel):
    init_data: str


class TelegramAuthOut(BaseModel):
    token: str
    user: dict


@router.post("/telegram", response_model=TelegramAuthOut)
def auth_telegram(payload: TelegramAuthIn, db: Session = Depends(get_db)):
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

    token = issue_jwt(subject=str(user.id), secret=settings.jwt_secret, ttl_seconds=settings.jwt_ttl_seconds)
    logger.info(
        "Auth success",
        extra={"event": "auth_success", "telegram_user_id": user.telegram_user_id},
    )
    return {"token": token, "user": {"id": user.id, "telegram_user_id": user.telegram_user_id}}

