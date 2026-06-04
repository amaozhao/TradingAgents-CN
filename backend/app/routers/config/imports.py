# ruff: noqa: F401,F403,F405,F821
"""
配置管理API路由
"""

import importlib
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.core.response import ok
from app.schemas.config import (
    ConfigTestRequest,
    ConfigTestResponse,
    DatabaseConfig,
    DatabaseConfigRequest,
    DataSourceConfig,
    DataSourceConfigRequest,
    DataSourceGrouping,
    DataSourceGroupingRequest,
    DataSourceOrderRequest,
    LLMConfig,
    LLMConfigRequest,
    LLMProvider,
    LLMProviderRequest,
    LLMProviderResponse,
    MarketCategory,
    MarketCategoryRequest,
    ModelCatalog,
    ModelInfo,
    SystemConfigResponse,
)
from app.schemas.operations import ActionType
from app.schemas.response import ApiResponse
from app.schemas.user import User
from app.routers.account import get_current_user
from app.services.config import config_service
from app.services.operation import log_operation
from app.services.provider import provider as config_provider
from app.utils.timezone import now_tz

router = APIRouter(prefix="/config", tags=["配置管理"])
logger = logging.getLogger("webapi")
