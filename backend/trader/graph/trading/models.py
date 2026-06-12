from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import _GraphMixin2
    from .common import _GraphMixin1


class TradingAgentsGraph(_GraphMixin1, _GraphMixin2):
    """Main class that orchestrates the trading agents framework."""
