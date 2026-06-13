#!/usr/bin/env python3
"""
手动测试新闻获取超时修复

这个脚本用于手动验证新闻获取功能，特别是在Google新闻获取超时的情况下的轮询机制。
"""

import time
from datetime import datetime

import pytest

from trader.flows.real.time import get_realtime_stock_news
from trader.utils.logging import get_logger

pytestmark = pytest.mark.integration

logger = get_logger("test")
TEST_TICKERS = ["600036.SH"]


def fetch_news_for_stock(ticker: str) -> str:
    """
    测试获取指定股票的新闻

    Args:
        ticker: 股票代码
    """
    logger.info(f"开始获取{ticker}的新闻...")
    curr_date = datetime.now().strftime("%Y-%m-%d")

    try:
        # 获取新闻
        start_time = time.time()
        news = get_realtime_stock_news(ticker, curr_date)
        end_time = time.time()

        # 打印结果
        logger.info(f"获取{ticker}的新闻成功，耗时{end_time - start_time:.2f}秒")
        print("\n" + "=" * 80)
        print(f"股票: {ticker}")
        print("=" * 80)
        print(news)
        print("=" * 80 + "\n")

        return news
    except Exception as e:
        logger.error(f"获取{ticker}的新闻失败: {e}")
        return ""


@pytest.mark.parametrize("ticker", TEST_TICKERS)
def test_news_for_stock(ticker: str) -> None:
    news = fetch_news_for_stock(ticker)
    assert news.strip()
