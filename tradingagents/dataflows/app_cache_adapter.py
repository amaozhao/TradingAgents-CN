"""Adapter helpers for reading TradingAgents-CN app cache collections."""

from __future__ import annotations

from typing import Any

import pandas as pd


def get_market_quote_dataframe(symbol: str) -> pd.DataFrame:
    """Return a single-symbol market quote dataframe from the app Mongo cache."""
    try:
        from tradingagents.config.database_manager import get_database_manager

        manager = get_database_manager()
        if not manager.is_mongodb_available():
            return pd.DataFrame()

        db = manager.get_mongodb_db()
        if db is None:
            return pd.DataFrame()

        code = str(symbol).zfill(6)
        doc: dict[str, Any] | None = db["market_quotes"].find_one({"code": code})
        if not doc:
            return pd.DataFrame()

        doc.pop("_id", None)
        return pd.DataFrame([doc])
    except Exception:
        return pd.DataFrame()
