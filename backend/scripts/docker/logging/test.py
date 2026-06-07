#!/usr/bin/env python3
"""
测试Docker环境下的日志功能
"""

import importlib
import sys
from pathlib import Path

from app.core.runtime import apply_runtime_env


def test_logging():
    """测试日志功能"""
    print("🧪 测试Docker环境日志功能")
    print("=" * 50)

    try:
        # 设置Docker环境变量
        apply_runtime_env(
            {"DOCKER_CONTAINER": "true", "TRADING_AGENTS_LOG_DIR": "/app/logs"}
        )

        # 导入日志模块
        init_logging = getattr(
            importlib.import_module("trader.utils.logging.init"), "init_logging"
        )
        get_logger = getattr(
            importlib.import_module("trader.utils.logging.init"), "get_logger"
        )

        # 初始化日志
        print("📋 初始化日志系统...")
        init_logging()

        # 获取日志器
        logger = get_logger("test")

        # 测试各种级别的日志
        print("📝 写入测试日志...")
        logger.debug("🔍 这是DEBUG级别日志")
        logger.info("ℹ️ 这是INFO级别日志")
        logger.warning("⚠️ 这是WARNING级别日志")
        logger.error("❌ 这是ERROR级别日志")

        # 检查日志文件
        log_dir = Path("/app/logs")
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log*"))
            print(f"📄 找到日志文件: {len(log_files)} 个")
            for log_file in log_files:
                size = log_file.stat().st_size
                print(f"   📄 {log_file.name}: {size} 字节")
        else:
            print("❌ 日志目录不存在")

        print("✅ 日志测试完成")

    except Exception as e:
        print(f"❌ 日志测试失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    test_logging()
    sys.exit(0)
