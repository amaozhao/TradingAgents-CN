#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定时任务管理服务
提供定时任务的查询、暂停、恢复、手动触发等功能
"""

# ruff: noqa: F401

import asyncio
import importlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    JobExecutionEvent,
)
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.database import get_postgres_db
from app.db.dual import dual_write_hot_document
from app.utils.timezone import now_tz
from trader.utils.logging.manager import get_logger

logger = get_logger(__name__)

# UTC+8 时区
UTC_8 = timezone(timedelta(hours=8))


def get_utc8_now():
    """
    获取 UTC+8 当前时间（naive datetime）

    注意：返回 naive datetime（不带时区信息），PostgreSQL 会按原样存储本地时间值
    这样前端可以直接添加 +08:00 后缀显示
    """
    return now_tz().replace(tzinfo=None)


class TaskCancelledException(Exception):
    """任务被取消异常"""

    pass
