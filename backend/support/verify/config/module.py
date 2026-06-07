#!/usr/bin/env python3
"""
验证配置是否正确
"""

from app.core.config import settings as app_settings

print("🔧 验证.env配置")
print("=" * 30)

# 检查启用开关
postgres_enabled = app_settings.text_value("POSTGRES_ENABLED", "false")
redis_enabled = app_settings.text_value("REDIS_ENABLED", "false")

print(f"POSTGRES_ENABLED: {postgres_enabled}")
print(f"REDIS_ENABLED: {redis_enabled}")

# 使用强健的布尔值解析（兼容Python 3.13+）
try:
    from trader.config.env import parse_bool_env

    postgres_bool = parse_bool_env("POSTGRES_ENABLED", False)
    redis_bool = parse_bool_env("REDIS_ENABLED", False)
    print("✅ 使用强健的布尔值解析")
except ImportError:
    # 回退到原始方法
    postgres_bool = postgres_enabled.lower() == "true"
    redis_bool = redis_enabled.lower() == "true"
    print("⚠️ 使用传统布尔值解析")

print(f"PostgreSQL启用: {postgres_bool}")
print(f"Redis启用: {redis_bool}")

if not postgres_bool and not redis_bool:
    print("✅ 默认配置：数据库都未启用，系统将使用文件缓存")
else:
    print("⚠️ 有数据库启用，系统将尝试连接数据库")

print("\n💡 配置说明:")
print("- POSTGRES_ENABLED=false (默认)")
print("- REDIS_ENABLED=false (默认)")
print("- 系统使用文件缓存，无需数据库")
print("- 如需启用数据库，修改.env文件中的对应值为true")
