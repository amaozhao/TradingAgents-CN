# ruff: noqa: F401,F403,F405,F821,E402
"""
AGENTrader v1.0.1 FastAPI Backend
主应用程序入口

Copyright (c) 2025 hsliuping. All rights reserved.
版权所有 (c) 2025 hsliuping。保留所有权利。

This software is proprietary and confidential. Unauthorized copying, distribution,
or use of this software, via any medium, is strictly prohibited.
本软件为专有和机密软件。严禁通过任何媒介未经授权复制、分发或使用本软件。

For commercial licensing, please contact: hsliup@163.com
商业许可咨询，请联系：hsliup@163.com
"""

import asyncio
import importlib
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.network_proxy import configure_runtime_proxy

configure_runtime_proxy()

from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.logs import setup_logging

# 港股和美股改为按需获取+缓存模式，不再需要定时同步任务
# from app.worker.hk.sync import ...
# from app.worker.us.sync import ...
from app.middleware.operations import OperationLogMiddleware
from app.middleware.requests import RequestIDMiddleware
from app.routers import account as auth
from app.routers import akshare as akshare_init
from app.routers import alpha_zoo as alpha_zoo
from app.routers import analysis as analysis
from app.routers import baostock as baostock_init
from app.routers import cache, favorites, health, logs, queue, reports, sse, tags
from app.routers import capabilities as model_capabilities
from app.routers import config as config
from app.routers import data as stock_data_router
from app.routers import database as database
from app.routers import financial as financial_data
from app.routers import historical as historical_data
from app.routers import markets as multi_market_stocks_router
from app.routers import messages as internal_messages
from app.routers import news as news_data
from app.routers import notifications as notifications_router
from app.routers import operations as operations
from app.routers import paper as paper_router
from app.routers import periods as multi_period_sync
from app.routers import research_agent as research_agent_router
from app.routers import research_matrix as research_matrix
from app.routers import scheduler as scheduler_router
from app.routers import screening as screening
from app.routers import social as social_media
from app.routers import socket as websocket_notifications_router
from app.routers import sources as multi_source_sync
from app.routers import stock as stock_sync_router
from app.routers import stocks as stocks_router
from app.routers import sync as sync_router
from app.routers import system as system_config_router
from app.routers import tushare as tushare_init
from app.routers import user_model_keys as user_model_keys_router
from app.routers import usage as usage_statistics
from app.services.quotes.ingestion import QuotesIngestionService
from app.services.scheduler import set_scheduler_instance
from app.services.sync.source import get_multi_source_sync_service
