# ruff: noqa: F401,F403,F405,F821
#!/usr/bin/env python3
"""
数据源管理器
统一管理中国股票数据源的选择和切换，支持Tushare、AKShare、BaoStock等
"""

import importlib
import os
import time
import warnings
from enum import Enum
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd

from trader.config.databases import get_database_manager
from trader.constants import DataSourceCode
from trader.utils.logging.init import setup_dataflow_logging
from trader.utils.logging.manager import get_logger

logger = get_logger("agents")
warnings.filterwarnings("ignore")

logger = setup_dataflow_logging()
