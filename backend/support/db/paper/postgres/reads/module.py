import pytest

from app.core.config import settings
from app.routers import paper


@pytest.mark.asyncio
async def test_paper_account_read_uses_postgres_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg_account(user_id):
        assert user_id == "user-1"
        return {"user_id": user_id, "cash": {"USD": 1000.0}}

    monkeypatch.setattr(paper, "_get_paper_account_from_postgres", fake_pg_account)

    account = await paper._get_account_for_read("user-1")

    assert account["cash"] == {"USD": 1000.0}


@pytest.mark.asyncio
async def test_paper_positions_read_uses_postgres_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg_positions(user_id):
        assert user_id == "user-1"
        return [{"user_id": user_id, "code": "AAPL", "quantity": 2}]

    monkeypatch.setattr(paper, "_list_paper_positions_from_postgres", fake_pg_positions)

    positions = await paper._list_positions_for_read("user-1")

    assert positions == [{"user_id": "user-1", "code": "AAPL", "quantity": 2}]


@pytest.mark.asyncio
async def test_paper_orders_read_uses_postgres_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg_orders(user_id, *, limit):
        assert user_id == "user-1"
        assert limit == 10
        return [{"user_id": user_id, "code": "AAPL", "side": "buy", "status": "filled"}]

    monkeypatch.setattr(paper, "_list_paper_orders_from_postgres", fake_pg_orders)

    orders = await paper._list_orders_for_read("user-1", limit=10)

    assert orders[0]["code"] == "AAPL"
    assert orders[0]["status"] == "filled"
