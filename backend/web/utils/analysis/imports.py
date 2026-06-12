"""
股票分析执行工具
"""

import importlib
import os
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from app.core.config import settings
from trader.utils.logging.init import setup_web_logging
from trader.utils.logging.manager import get_logger, get_logger_manager

logger = get_logger("web")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
logger = setup_web_logging()

# 添加配置管理器
try:
    from trader.config.manager import token_tracker

    TOKEN_TRACKING_ENABLED = True
    logger.info("✅ Token跟踪功能已启用")
except ImportError:
    TOKEN_TRACKING_ENABLED = False
    logger.warning("⚠️ Token跟踪功能未启用")

__all__ = [
    "PROJECT_ROOT",
    "Path",
    "TOKEN_TRACKING_ENABLED",
    "datetime",
    "get_logger",
    "get_logger_manager",
    "importlib",
    "logger",
    "os",
    "settings",
    "setup_web_logging",
    "st",
    "token_tracker",
    "uuid",
]
