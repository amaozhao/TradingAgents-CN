# ruff: noqa: F401,F403,F405,F821
"""
股票详情相关API
- 统一响应包: {success, data, message, timestamp}
- 所有端点均需鉴权 (Bearer Token)
- 路径前缀在 main.py 中挂载为 /api，当前路由自身前缀为 /stocks
"""

import importlib
import logging
import re
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.database import get_postgres_db
from app.core.response import ok
from app.models.response import ApiResponse
from app.routers.account import get_current_user
from app.services.market.financial import FinancialDataService
from app.services.stocks.service import StockDataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks", tags=["stocks"])
