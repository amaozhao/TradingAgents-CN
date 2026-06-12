#!/usr/bin/env python3
"""
股票数据预获取和验证模块
用于在分析流程开始前验证股票是否存在，并预先获取和缓存必要的数据
"""

import importlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

# 导入日志模块
from trader.utils.logging.manager import get_logger

logger = get_logger("stock_validator")


@dataclass
class StockDataPreparationResult:
    """股票数据预检查结果。"""

    is_valid: bool
    stock_code: str
    market_type: Optional[str] = None
    stock_name: Optional[str] = None
    has_historical_data: bool = False
    has_basic_info: bool = False
    data_period_days: Optional[int] = None
    cache_status: str = ""
    error_message: Optional[str] = None
    suggestion: Optional[str] = None

__all__ = [
    "Dict",
    "datetime",
    "importlib",
    "re",
    "timedelta",
]
