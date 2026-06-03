"""Compatibility import path for the unified Tushare provider.

Expose the actual china.tushare module object so monkeypatching this legacy
path affects the implementation globals used by ``TushareProvider``.
"""

import sys

from trader.flows.providers.china import tushare as _impl

sys.modules[__name__] = _impl
