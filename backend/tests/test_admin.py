"""
Итерация 7: Админ-панель.
Тест: curl с ADMIN_TOKEN — переключить is_active рынка; корректировка баланса — проверить баланс и ledger.
"""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import User, Balance, LedgerEntry


def test_admin_toggle_market(client: TestClient, test_gift_expiry_market: dict, admin_headers: dict):
    """PATCH /admin/markets/{id} переключает is_active."""
    market = test_gift_expiry_market["market"]
    assert market.is_active is True

    r = client.patch(
        f"/admin/markets/{market.id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["is_active"] is False

    # Повторный запрос — обратно
    r2 = client.patch(
        f"/admin/markets/{market.id}",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["is_active"] is True


def test_admin_toggle_market_unauthorized(client: TestClient, test_gift_expiry_market: dict):
    """PATCH /admin/markets/{id} без токена — 401."""
    market = test_gift_expiry_market["market"]
    r = client.patch(
        f"/admin/markets/{market.id}",
        json={"is_active": False},
    )
    assert r.status_code == 401


@pytest.fixture
def user_for_adjust(db_session: Session) -> User:
    """Пользователь для корректировки баланса."""
    u = User(telegram_user_id="adjust-test")
    db_session.add(u)
    db_session.flush()
    b = Balance(user_id=u.id, currency="TON", available=Decimal("100"), reserved=Decimal("0"))
    db_session.add(b)
    db_session.commit()
    db_session.refresh(u)
    return u


def test_admin_adjust_balance(client: TestClient, user_for_adjust: User, admin_headers: dict, db_session: Session):
    """POST /admin/balances/adjust корректирует баланс и создаёт ledger entry."""
    user_id = user_for_adjust.id
    # Balance имеет composite key (user_id, currency), используем query
    initial_balance = db_session.query(Balance).filter(Balance.user_id == user_id, Balance.currency == "TON").first()
    assert initial_balance.available == Decimal("100")

    r = client.post(
        "/admin/balances/adjust",
        json={
            "user_id": user_id,
            "currency": "TON",
            "delta": "20.5",
            "reason": "Test adjustment",
        },
        headers=admin_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == user_id
    assert data["currency"] == "TON"
    assert data["delta"] == "20.5"
    # Decimal может сериализоваться с лишними нулями, нормализуем
    assert Decimal(data["new_available"]) == Decimal("120.5")
    assert Decimal(data["old_available"]) == Decimal("100")

    # Проверяем баланс в БД
    db_session.refresh(initial_balance)
    assert initial_balance.available == Decimal("120.5")

    # Проверяем ledger entry
    entries = db_session.query(LedgerEntry).filter(
        LedgerEntry.user_id == user_id,
        LedgerEntry.currency == "TON",
        LedgerEntry.reason == "adjustment",
    ).all()
    assert len(entries) >= 1
    last_entry = entries[-1]
    assert last_entry.delta == Decimal("20.5")
    assert last_entry.reason == "adjustment"
    assert last_entry.ref_type == "admin_adjustment"


def test_admin_adjust_balance_negative_rejected(client: TestClient, user_for_adjust: User, admin_headers: dict):
    """Корректировка, приводящая к отрицательному балансу, отклоняется."""
    user_id = user_for_adjust.id
    r = client.post(
        "/admin/balances/adjust",
        json={
            "user_id": user_id,
            "currency": "TON",
            "delta": "-150",  # больше чем баланс 100
            "reason": "Test negative",
        },
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "Insufficient balance" in r.json()["detail"]


def test_admin_adjust_balance_no_reason_rejected(client: TestClient, user_for_adjust: User, admin_headers: dict):
    """Корректировка без reason отклоняется."""
    user_id = user_for_adjust.id
    r = client.post(
        "/admin/balances/adjust",
        json={
            "user_id": user_id,
            "currency": "TON",
            "delta": "10",
            "reason": "",  # пустой reason
        },
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "Reason is required" in r.json()["detail"]
