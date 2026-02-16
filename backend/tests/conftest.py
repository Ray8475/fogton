"""
Фикстуры для тестов API. Используется временный файловый SQLite и переопределение auth для /me.
"""
from __future__ import annotations

import os
import sys
import tempfile

# Настраиваем env до импорта app (engine создаётся при импорте database)
# Используем временный файл для SQLite (удаляется после тестов)
_test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
_test_db_path = _test_db_file.name
_test_db_file.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_test_db_path}")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("BOT_TOKEN", "test-bot-token")
os.environ.setdefault("TON_WEBHOOK_SECRET", "")  # Пустой — в тестах webhook можно вызывать без заголовка

# Добавляем backend в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import create_app
from app.core.auth_deps import require_user_id_dep
from app.db.database import SessionLocal
from app.db.models import User, Gift, Expiry, Market, Balance


# Переопределение: в тестах «текущий пользователь» = user_id 1
def _override_user_id(request, response):
    return 1


@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.dependency_overrides[require_user_id_dep] = _override_user_id
    return app


@pytest.fixture(scope="session")
def client(app):
    return TestClient(app, base_url="http://testserver")


@pytest.fixture
def db_session():
    """Сессия БД для подготовки данных в тестах."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clean_tables_before(db_session: Session):
    """Очистка таблиц перед каждым тестом (порядок из-за FK)."""
    for table in ("ledger_entries", "withdrawals", "deposits", "balances", "markets", "expiries", "gifts", "users"):
        try:
            db_session.execute(text(f"DELETE FROM {table}"))
            db_session.commit()
        except Exception:
            db_session.rollback()
    yield
    db_session.rollback()


def pytest_sessionfinish(session, exitstatus):
    """Удаляем временный файл БД после всех тестов."""
    try:
        if os.path.exists(_test_db_path):
            os.unlink(_test_db_path)
    except Exception:
        pass


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Пользователь с id=1 для тестов /me и webhook."""
    user = User(telegram_user_id="123456789")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_gift_expiry_market(db_session: Session, test_user: User):
    """Gift, Expiry, Market для тестов админки и рынков."""
    gift = Gift(name="Test Gift", is_active=True)
    db_session.add(gift)
    expiry = Expiry(days=7, is_active=True)
    db_session.add(expiry)
    db_session.flush()
    market = Market(gift_id=gift.id, expiry_id=expiry.id, is_active=True)
    db_session.add(market)
    db_session.commit()
    db_session.refresh(gift)
    db_session.refresh(expiry)
    db_session.refresh(market)
    return {"gift": gift, "expiry": expiry, "market": market}


@pytest.fixture
def admin_headers():
    """Заголовок Authorization для админ-эндпоинтов."""
    return {"Authorization": "Bearer test-admin-token"}
