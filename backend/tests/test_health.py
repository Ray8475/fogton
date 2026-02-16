"""Итерация 2: GET /healthz — 200 и db ok."""
import pytest
from fastapi.testclient import TestClient


def test_healthz_ok(client: TestClient):
    r = client.get("/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("db") == "ok"
