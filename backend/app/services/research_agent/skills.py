from __future__ import annotations

from typing import Any


SKILL_NAMES: tuple[str, ...] = (
    "adr-hshare",
    "akshare",
    "alpha-zoo",
    "ashare-pre-st-filter",
    "asset-allocation",
    "backtest-diagnose",
    "behavioral-finance",
    "candlestick",
    "ccxt",
    "chanlun",
    "commodity-analysis",
    "convertible-bond",
    "corporate-events",
    "correlation-analysis",
    "credit-analysis",
    "cross-market-strategy",
    "crypto-derivatives",
    "data-routing",
    "defi-yield",
    "dividend-analysis",
    "doc-reader",
    "earnings-forecast",
    "earnings-revision",
    "edgar-sec-filings",
    "elliott-wave",
    "etf-analysis",
    "event-driven",
    "execution-model",
    "factor-research",
    "financial-statement",
    "fund-analysis",
    "fundamental-filter",
    "geopolitical-risk",
    "global-macro",
    "harmonic",
    "hedging-strategy",
    "hk-connect-flow",
    "ichimoku",
    "liquidation-heatmap",
    "macro-analysis",
    "market-microstructure",
    "minute-analysis",
    "ml-strategy",
    "mootdx",
    "multi-factor",
    "okx-market",
    "onchain-analysis",
    "options-advanced",
    "options-payoff",
    "options-strategy",
    "pair-trading",
    "performance-attribution",
    "perp-funding-basis",
    "pine-script",
    "quant-statistics",
    "regulatory-knowledge",
    "report-generate",
    "research-goal",
    "risk-analysis",
    "seasonal",
    "sector-rotation",
    "sentiment-analysis",
    "shadow-account",
    "smc",
    "social-media-intelligence",
    "stablecoin-flow",
    "strategy-generate",
    "technical-basic",
    "token-unlock-treasury",
    "trade-journal",
    "tushare",
    "us-etf-flow",
    "valuation-model",
    "vnpy-export",
    "volatility",
    "web-reader",
    "yfinance",
)


class ResearchSkillCatalogService:
    def list_skills(self) -> list[dict[str, Any]]:
        return [self._skill(name) for name in SKILL_NAMES]

    def get_skill(self, name: str) -> dict[str, Any] | None:
        normalized = name.strip().lower()
        if normalized not in SKILL_NAMES:
            return None
        return self._skill(normalized)

    def _skill(self, name: str) -> dict[str, Any]:
        title = name.replace("-", " ").title()
        return {
            "name": name,
            "title": title,
            "status": "available",
            "source_runtime_dependency": False,
            "mutation_allowed": False,
            "summary": f"{title} capability metadata migrated into the current TradingAgents-CN research-agent catalog.",
            "prompt_context": (
                f"Skill: {name}\n"
                "Use this capability only through current-project tools, artifacts, permissions, and owner-scoped data. "
                "Do not read from the source project at runtime."
            ),
        }
