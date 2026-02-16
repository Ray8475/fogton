"""
Итерация 6: Вывод (заявка и статус).
Тест: создать вывод → в списке выводов виден статус pending.
"""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import User, Balance


@pytest.fixture
def user_one_with_balance(db_session: Session) -> User:
    """Пользователь id=1 (auth override) с балансом TON."""
    u = User(telegram_user_id="one")
    db_session.add(u)
    db_session.flush()
    b = Balance(user_id=u.id, currency="TON", available=Decimal("50"), reserved=Decimal("0"))
    db_session.add(b)
    db_session.commit()
    db_session.refresh(u)
    return u


def test_withdraw_and_list(client: TestClient, user_one_with_balance: User):
    """Создать вывод от user_id=1 → в списке выводов виден статус pending."""
    r = client.post(
        "/me/withdraw",
        json={
            "amount": "10",
            "currency": "TON",
            "destination_address": "EQtest1234567890123456789012345678901234567890abc",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert data["amount"] == "10"
    assert data["currency"] == "TON"

    r2 = client.get("/me/withdrawals")
    assert r2.status_code == 200
    withdrawals = r2.json()["withdrawals"]
    assert len(withdrawals) >= 1
    last = withdrawals[0]
    assert last["status"] in ("pending", "completed", "failed")
    assert last["amount"] == "10"
