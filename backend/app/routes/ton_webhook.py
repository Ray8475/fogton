from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.settings import settings


router = APIRouter(prefix="/ton", tags=["ton"])


@router.post("/webhook")
async def ton_webhook(
    request: Request,
    x_ton_webhook_secret: str | None = Header(default=None),
):
    """
    MVP placeholder endpoint for TON provider webhooks.
    We only validate a shared secret and echo OK.
    """
    if settings.ton_webhook_secret:
        if not x_ton_webhook_secret or x_ton_webhook_secret != settings.ton_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid TON webhook secret")

    _payload = await request.json()
    return {"ok": True}

