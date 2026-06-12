from .base import _GoogleToolCallHandlerMixin2
from .common import _GoogleToolCallHandlerMixin1


class GoogleToolCallHandler(_GoogleToolCallHandlerMixin1, _GoogleToolCallHandlerMixin2):
    """Google模型工具调用统一处理器"""
