# ruff: noqa: F401,F403,F405,F821,F722
import importlib
import os
import time
from datetime import datetime
from typing import Annotated, Any, Dict, cast

import pandas as pd
from dateutil.relativedelta import relativedelta
from openai import OpenAI
from tqdm import tqdm

from app.core.config import settings
from trader.config.manager import config_manager
from trader.utils.logging.init import setup_dataflow_logging
from trader.utils.logging.manager import get_logger

from ..news.china import get_chinese_social_sentiment as get_chinese_social_sentiment

# 导入新闻模块（支持新旧路径）
try:
    from ..news import fetch_top_from_category
except ImportError:
    from ..news.reddit import fetch_top_from_category

from ..news.google import get_news_data

# 导入 Finnhub 工具（支持新旧路径）
from ..providers.us import get_data_in_range

logger = get_logger("agents")
logger = setup_dataflow_logging()
