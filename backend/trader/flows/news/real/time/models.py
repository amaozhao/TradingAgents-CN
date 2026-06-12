from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import _RealtimeNewsAggregatorMixin2
    from .common import _RealtimeNewsAggregatorMixin1


class RealtimeNewsAggregator(_RealtimeNewsAggregatorMixin1, _RealtimeNewsAggregatorMixin2):
    """实时新闻聚合器"""
