# ruff: noqa: F401
#!/usr/bin/env python3
"""
配置管理器
管理API密钥、模型配置、费率设置等

⚠️ DEPRECATED: 此模块已废弃，将在 2026-03-31 后移除
   请使用新的配置系统: app.services.config.ConfigService
"""

import importlib
import json
import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from zoneinfo import ZoneInfo

from app.core.config import settings as app_settings
from trader.config.runtime import get_timezone_name
from trader.utils.logging.manager import get_logger

from ..usage import ModelConfig, PricingConfig, UsageRecord


logger = get_logger("agents")

try:
    from ..postgres import PostgresStorage

    POSTGRES_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ [ConfigManager] 导入 PostgresStorage 失败 (ImportError): {e}")
    import traceback

    logger.error(f"   堆栈: {traceback.format_exc()}")
    POSTGRES_AVAILABLE = False
    PostgresStorage = None
except Exception as e:
    logger.error(f"❌ [ConfigManager] 导入 PostgresStorage 失败 (Exception): {e}")
    import traceback

    logger.error(f"   堆栈: {traceback.format_exc()}")
    POSTGRES_AVAILABLE = False
    PostgresStorage = None
