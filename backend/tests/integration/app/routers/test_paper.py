from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import paper


USER = {"id": "user-1", "username": "alice", "is_admin": False, "roles": []}


class FakeInsertResult:
    def __init__(self, inserted_id: str) -> None:
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        self.documents = documents or []
        self.updates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self.inserts: list[dict[str, Any]] = []
        self.deletes: list[dict[str, Any]] = []

    async def find_one(self, query: dict[str, Any], *_args, **_kwargs):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document
        return None

    async def insert_one(self, document: dict[str, Any]):
        self.inserts.append(document)
        self.documents.append(document)
        return FakeInsertResult(f"inserted-{len(self.inserts)}")

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        self.updates.append((query, update))
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                for dotted_key, value in update.get("$set", {}).items():
                    _set_dotted(document, dotted_key, value)
                for dotted_key, value in update.get("$inc", {}).items():
                    current = _get_dotted(document, dotted_key) or 0
                    _set_dotted(document, dotted_key, current + value)
                break

    async def delete_one(self, query: dict[str, Any]):
        self.deletes.append(query)
        self.documents = [
            document
            for document in self.documents
            if not all(document.get(key) == value for key, value in query.items())
        ]


class FakeDb:
    def __init__(
        self,
        *,
        account: dict[str, Any],
        positions: list[dict[str, Any]] | None = None,
    ) -> None:
        self.collections = {
            "paper_accounts": FakeCollection([account]),
            "paper_positions": FakeCollection(positions or []),
            "paper_orders": FakeCollection(),
            "paper_trades": FakeCollection(),
        }

    def __getitem__(self, name: str):
        return self.collections[name]


def _set_dotted(document: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    current = document
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _get_dotted(document: dict[str, Any], dotted_key: str) -> Any:
    current: Any = document
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


@pytest.fixture(autouse=True)
def paper_dependencies(monkeypatch: pytest.MonkeyPatch):
    async def no_dual_write(_collection: str, _document: dict[str, Any]) -> None:
        return None

    async def last_price(_code: str, _market: str) -> float:
        return 20.0

    async def market_rules(_market: str) -> dict[str, Any]:
        return {"commission": {"rate": 0.001, "min": 5.0}}

    monkeypatch.setattr(paper, "_dual_write_paper", no_dual_write)
    monkeypatch.setattr(paper, "_get_last_price", last_price)
    monkeypatch.setattr(paper, "_get_market_rules", market_rules)


@pytest.mark.asyncio
async def test_buy_rejects_when_cash_cannot_cover_notional_and_fee(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb(
        account={
            "user_id": USER["id"],
            "cash": {"CNY": 100.0, "HKD": 0.0, "USD": 0.0},
            "realized_pnl": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
        }
    )
    monkeypatch.setattr(paper, "get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await paper.place_order(
            paper.PlaceOrderRequest(code="600519", side="buy", quantity=5),
            current_user=USER,
        )

    assert exc.value.status_code == 400
    assert "可用CNY不足" in str(exc.value.detail)
    assert db["paper_orders"].inserts == []
    assert db["paper_trades"].inserts == []


@pytest.mark.asyncio
async def test_buy_updates_cash_and_weighted_average_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = {
        "user_id": USER["id"],
        "cash": {"CNY": 10_000.0, "HKD": 0.0, "USD": 0.0},
        "realized_pnl": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
    }
    position = {
        "_id": "position-1",
        "user_id": USER["id"],
        "code": "600519",
        "market": "CN",
        "currency": "CNY",
        "quantity": 100,
        "available_qty": 100,
        "avg_cost": 10.0,
    }
    db = FakeDb(account=account, positions=[position])
    monkeypatch.setattr(paper, "get_postgres_db", lambda: db)

    response = await paper.place_order(
        paper.PlaceOrderRequest(
            code="600519",
            side="buy",
            quantity=100,
            analysis_id="analysis-1",
        ),
        current_user=USER,
    )

    assert response["success"] is True
    assert account["cash"]["CNY"] == 7_995.0
    assert position["quantity"] == 200
    assert position["available_qty"] == 100
    assert position["avg_cost"] == 15.0
    assert db["paper_orders"].inserts[0]["commission"] == 5.0
    assert db["paper_orders"].inserts[0]["analysis_id"] == "analysis-1"
    assert db["paper_trades"].inserts[0]["pnl"] == 0.0


@pytest.mark.asyncio
async def test_sell_rejects_when_available_position_is_too_small(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = {
        "user_id": USER["id"],
        "cash": {"CNY": 10_000.0, "HKD": 0.0, "USD": 0.0},
        "realized_pnl": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
    }
    position = {
        "_id": "position-1",
        "user_id": USER["id"],
        "code": "600519",
        "market": "CN",
        "currency": "CNY",
        "quantity": 100,
        "available_qty": 5,
        "avg_cost": 10.0,
    }
    db = FakeDb(account=account, positions=[position])
    monkeypatch.setattr(paper, "get_postgres_db", lambda: db)

    async def available_quantity(*_args) -> int:
        return 5

    monkeypatch.setattr(paper, "_get_available_quantity", available_quantity)

    with pytest.raises(HTTPException) as exc:
        await paper.place_order(
            paper.PlaceOrderRequest(code="600519", side="sell", quantity=10),
            current_user=USER,
        )

    assert exc.value.status_code == 400
    assert "可用持仓不足" in str(exc.value.detail)
    assert db["paper_orders"].inserts == []
    assert db["paper_trades"].inserts == []
