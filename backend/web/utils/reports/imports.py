# ruff: noqa: F401,F403,F405,F821
#!/usr/bin/env python3
"""
报告导出工具
支持将分析结果导出为多种格式
"""

import importlib
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional

import streamlit as st

# 导入日志模块
from trader.utils.logging.manager import get_logger

logger = get_logger("web")

# 导入PostgreSQL报告管理器
try:
    from web.utils.postgres import postgres_report_manager

    POSTGRES_REPORT_AVAILABLE = True
except ImportError:
    POSTGRES_REPORT_AVAILABLE = False
    postgres_report_manager = None

# 配置日志 - 确保输出到stdout以便Docker logs可见
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # 输出到stdout
    ],
)
logger = logging.getLogger(__name__)

# 导入Docker适配器
try:
    from ..docker import (
        get_docker_status_info,
        is_docker_environment,
        setup_xvfb_display,
    )

    DOCKER_ADAPTER_AVAILABLE = True
except ImportError:
    DOCKER_ADAPTER_AVAILABLE = False
    logger.warning("⚠️ Docker适配器不可用")

# 导入导出相关库
try:
    import os
    import tempfile

    # 导入pypandoc（用于markdown转docx和pdf）
    import pypandoc

    # 检查pandoc是否可用，如果不可用则尝试下载
    try:
        pypandoc.get_pandoc_version()
        PANDOC_AVAILABLE = True
    except OSError:
        logger.warning("⚠️ 未找到pandoc，正在尝试自动下载...")
        try:
            pypandoc.download_pandoc()
            PANDOC_AVAILABLE = True
            logger.info("✅ pandoc下载成功！")
        except Exception as download_error:
            logger.error(f"❌ pandoc下载失败: {download_error}")
            PANDOC_AVAILABLE = False

    EXPORT_AVAILABLE = True

except ImportError as e:
    EXPORT_AVAILABLE = False
    PANDOC_AVAILABLE = False
    logger.info(f"导出功能依赖包缺失: {e}")
    logger.info("请安装: pip install pypandoc markdown")
