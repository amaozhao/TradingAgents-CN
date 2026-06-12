"""
股票分析API路由
增强版本，支持优先级、进度跟踪、任务管理等功能
"""

import asyncio
import importlib
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.core.database import get_postgres_db
from app.db.dual import dual_write_hot_document
from app.routers.account import get_current_user
from app.schemas.analysis import (
    BatchAnalysisRequest,
    SingleAnalysisRequest,
)
from app.schemas.response import ApiResponse
from app.services.analysis.simple import get_simple_analysis_service
from app.services.queue.service import QueueService, get_queue_service
from app.services.research.agent.batch.repository import BatchRepository
from app.services.research.agent.batch.runner import BatchStockWorkflow
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.socket import get_websocket_manager

router = APIRouter()
logger = logging.getLogger("webapi")


def _analysis_request_queue_params(request: SingleAnalysisRequest, task_id: str, user_id: str) -> Dict[str, Any]:
    params = request.parameters.model_dump(mode="json") if request.parameters else {}
    symbol = request.get_symbol()
    params.update({
        "task_id": task_id,
        "stock_code": symbol,
        "symbol": symbol,
        "user_id": user_id,
    })
    return params

__all__ = [
    "ApiResponse",
    "BackgroundTasks",
    "BaseModel",
    "BatchAnalysisRequest",
    "BatchRepository",
    "BatchStockWorkflow",
    "ConfigDict",
    "Depends",
    "Field",
    "HTTPException",
    "List",
    "Optional",
    "Path",
    "Query",
    "QueueService",
    "ResearchPrincipal",
    "ToolExecutionContext",
    "WebSocket",
    "WebSocketDisconnect",
    "asyncio",
    "datetime",
    "dual_write_hot_document",
    "get_current_user",
    "get_postgres_db",
    "get_queue_service",
    "get_simple_analysis_service",
    "get_websocket_manager",
    "importlib",
    "os",
    "re",
    "settings",
    "time",
    "timezone",
    "uuid",
]
