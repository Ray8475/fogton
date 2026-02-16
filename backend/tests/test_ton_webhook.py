"""
Итерация 5: TON webhook и зачисление.
Тест: webhook с comment пользователя → баланс пользователя увеличился.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import User, Balance


@pytest.fixture
def user_one(db_session: Session) -> User:
    u = User(telegram_user_id="111")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def test_webhook_credits_balance(client: TestClient, user_one: User):
    """POST /ton/webhook с comment u{user_id} зачисляет сумму на баланс пользователя."""
    user_id = user_one.id
    payload = {
        "tx_hash": "test-tx-hash-001",
        "amount": "10.5",
        "comment": f"u{user_id}",
        "currency": "TON",
    }
    r = client.post("/ton/webhook", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("credited") is True
    assert data.get("user_id") == user_id

    # GET /me/balances (auth override = user_id 1; если user_one.id != 1, нужен другой способ проверить)
    # В нашем fixture user_one — единственный пользователь, его id может быть 1
    r2 = client.get("/me/balances")
    assert r2.status_code == 200
    balances = r2.json()
    ton_balance = next((b for b in balances["balances"] if b["currency"] == "TON"), None)
    assert ton_balance is not None
    assert ton_balance["available"] == "10.5"


def test_webhook_idempotent(client: TestClient, user_one: User):
    """Повторный webhook с тем же tx_hash не дублирует зачисление."""
    user_id = user_one.id
    payload = {
        "tx_hash": "idempotent-tx-002",
        "amount": "5",
        "comment": f"u{user_id}",
        "currency": "TON",
    }
    r1 = client.post("/ton/webhook", json=payload)
    assert r1.status_code == 200
    assert r1.json().get("credited") is True

    r2 = client.post("/ton/webhook", json=payload)
    assert r2.status_code == 200
    assert r2.json().get("credited") is False
    assert r2.json().get("reason") == "duplicate_tx_hash"

    r3 = client.get("/me/balances")
    ton = next((b for b in r3.json()["balances"] if b["currency"] == "TON"), None)
    assert ton["available"] == "5"  # только одно зачисление
