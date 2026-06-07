# ruff: noqa: F401
#!/usr/bin/env python3
"""
股票数据缓存管理器
支持本地缓存股票数据，减少API调用，提高响应速度
"""

import hashlib
import importlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

# 导入日志模块
from app.core.config import settings
from trader.utils.logging.manager import get_logger

logger = get_logger("agents")
