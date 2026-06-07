# ruff: noqa: F401,F403,F405,F821
"""
AKShare统一数据提供器
基于AKShare SDK的统一数据同步方案，提供标准化的数据接口
"""

import asyncio
import importlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

import pandas as pd

from app.core.config import settings
from ...base import BaseStockDataProvider

logger = logging.getLogger(__name__)
