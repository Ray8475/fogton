from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("")
def list_markets():
    # MVP stub (we'll back this with DB tables later)
    return {
        "markets": [
            {"gift": "Gift A", "expiry_days": 7, "symbol": "GIFT_A-7D"},
            {"gift": "Gift A", "expiry_days": 30, "symbol": "GIFT_A-30D"},
        ]
    }

