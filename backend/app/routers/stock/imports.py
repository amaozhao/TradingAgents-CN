# ruff: noqa: F401,F403,F405,F821
"""
股票数据同步API路由
支持单个股票或批量股票的历史数据和财务数据同步
"""

import asyncio
import importlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_postgres_db
from app.core.response import ok
from app.db.dual import dual_write_hot_document
from app.schemas.response import ApiResponse
from app.routers.account import get_current_user

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/stock-sync", tags=["股票数据同步"])
