# ruff: noqa: F401,F403,F405,F821
"""
分析结果管理组件
提供股票分析历史结果的查看和管理功能
"""

import importlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# PostgreSQL相关导入
try:
    from web.utils.postgres import PostgreSQLReportManager

    POSTGRES_AVAILABLE = True
    print("✅ PostgreSQL模块导入成功")
except ImportError as e:
    POSTGRES_AVAILABLE = False
    print(f"❌ PostgreSQL模块导入失败: {e}")

# 设置日志
logger = logging.getLogger(__name__)
