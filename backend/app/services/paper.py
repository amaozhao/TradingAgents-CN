from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PaperOrderError(ValueError):
    pass


@dataclass(frozen=True)
class SellAccountTotals:
    cash: dict[str, float]
    realized_pnl: dict[str, float]


class PaperOrderService:
    @staticmethod
    def currency_for_market(market: str) -> str:
        return {"CN": "CNY", "HK": "HKD", "US": "USD"}.get(market, "CNY")

    @staticmethod
    def currency_amounts(value: Any) -> dict[str, float]:
        if isinstance(value, dict):
            return {
                "CNY": float(value.get("CNY", 0.0)),
                "HKD": float(value.get("HKD", 0.0)),
                "USD": float(value.get("USD", 0.0)),
            }
        return {"CNY": float(value or 0.0), "HKD": 0.0, "USD": 0.0}

    @staticmethod
    def require_buying_power(
        *,
        cash: Any,
        currency: str,
        total_cost: float,
    ) -> dict[str, float]:
        account_cash = PaperOrderService.currency_amounts(cash)
        available_cash = float(account_cash.get(currency, 0.0))
        if available_cash < total_cost:
            raise PaperOrderError(
                f"可用{currency}不足：需要 {total_cost:.2f}，可用 {available_cash:.2f}"
            )
        account_cash[currency] = round(available_cash - total_cost, 2)
        return account_cash

    @staticmethod
    def weighted_average_cost(
        *,
        old_quantity: int,
        old_cost: float,
        buy_quantity: int,
        buy_price: float,
    ) -> float:
        new_quantity = old_quantity + buy_quantity
        if new_quantity <= 0:
            return buy_price
        return round((old_cost * old_quantity + buy_price * buy_quantity) / new_quantity, 4)

    @staticmethod
    def available_after_buy(*, market: str, current_available: int, new_quantity: int) -> int:
        if market == "CN":
            return current_available
        return new_quantity

    @staticmethod
    def apply_sell_proceeds(
        *,
        account: dict[str, Any],
        currency: str,
        net_proceeds: float,
        realized_pnl_delta: float,
    ) -> SellAccountTotals:
        account_cash = PaperOrderService.currency_amounts(account.get("cash", {}))
        account_pnl = PaperOrderService.currency_amounts(account.get("realized_pnl", {}))
        account_cash[currency] = round(float(account_cash.get(currency, 0.0)) + net_proceeds, 2)
        account_pnl[currency] = round(float(account_pnl.get(currency, 0.0)) + realized_pnl_delta, 2)
        return SellAccountTotals(cash=account_cash, realized_pnl=account_pnl)
