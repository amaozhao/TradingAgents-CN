from .base import _ToolkitMixin2
from .common import _ToolkitMixin1
from .imports import DEFAULT_CONFIG
from .models import _ToolkitMixin3

class Toolkit(_ToolkitMixin1, _ToolkitMixin2, _ToolkitMixin3):
    _config = DEFAULT_CONFIG.copy()
