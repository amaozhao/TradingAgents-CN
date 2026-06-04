# ruff: noqa: F401,F403,F405,F821
def get_optimized_china_data_provider() -> OptimizedChinaDataProvider:
    """获取全局A股数据提供器实例"""
    global _china_data_provider
    if _china_data_provider is None:
        _china_data_provider = OptimizedChinaDataProvider()
    return _china_data_provider
