#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Google模型工具调用统一处理器

解决Google模型在工具调用时result.content为空的问题，
提供统一的工具调用处理逻辑供所有分析师使用。
"""

import importlib
import logging
import traceback
from typing import Any, Dict, List, Tuple

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)

__all__ = [
    "AIMessage",
    "Any",
    "Dict",
    "HumanMessage",
    "List",
    "ToolMessage",
    "Tuple",
    "importlib",
    "traceback",
]
