#!/usr/bin/env python3
"""
手动测试新闻获取超时修复

这个脚本用于手动验证新闻获取功能，特别是在Google新闻获取超时的情况下的轮询机制。
"""

import time
from datetime import datetime

import pytest

# 导入需要测试的模块
from trader.flows.real.time import get_realtime_stock_news
from trader.utils.logging import get_logger

# 获取日志记录器
logger = get_logger("test")
TEST_TICKERS = ["600036.SH"]
MANUAL_TEST_TICKERS = [
    "600036.SH",
    "000001.SZ",
    "601318.SH",
    "00700.HK",
    "09988.HK",
    "AAPL.US",
    "MSFT.US",
    "GOOGL.US",
]


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


def main():
    """
    主函数
    """
    # 测试结果统计
    success_count = 0
    fail_count = 0

    # 逐个测试
    for ticker in MANUAL_TEST_TICKERS:
        if fetch_news_for_stock(ticker):
            success_count += 1
        else:
            fail_count += 1

    # 打印统计结果
    print(f"\n测试完成: 成功 {success_count} 个, 失败 {fail_count} 个")


if __name__ == "__main__":
    main()
