# ruff: noqa: F401,F403,F405,F821
#!/usr/bin/env python3
"""
改进的港股数据获取工具
解决API速率限制和数据获取问题
"""

import importlib
import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from trader.config.runtime import get_int
from trader.tools.analysis.indicators import add_all_indicators

# 导入统一日志系统
from trader.utils.logging.init import get_logger

logger = get_logger("default")

try:
    import akshare as ak
except Exception:
    ak = None

# 新增：使用统一的数据目录配置
_cache_dir_func: Any
try:
    _cache_dir_func = getattr(importlib.import_module("utils.config"), "get_cache_dir")
except Exception:
    # 回退：在项目根目录下的 data/cache/hk
    def _fallback_get_cache_dir(
        subdir: Optional[str] = None, create: bool = True
    ) -> str:
        base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cache"
        )
        if subdir:
            base = os.path.join(base, subdir)
        if create:
            os.makedirs(base, exist_ok=True)
        return base

    _cache_dir_func = _fallback_get_cache_dir


def get_cache_dir(subdir: Optional[str] = None, create: bool = True) -> str | Path:
    return _cache_dir_func(subdir, create)
