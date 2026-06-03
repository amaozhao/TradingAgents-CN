"""Compatibility alias for the upstream risk analyst module name.

The CN project historically used the misspelled module name
``aggresive_debator``. Upstream imports use ``aggressive_debator`` and the
factory name ``create_aggressive_debator``. Keep both paths available while
reusing the CN Chinese risk-debate implementation.
"""

from trader.agents.risk.management.risky import create_risky_debator


def create_aggressive_debator(llm):
    return create_risky_debator(llm)


__all__ = ["create_aggressive_debator", "create_risky_debator"]
