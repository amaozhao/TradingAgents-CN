# ruff: noqa: F401,F403,F405,F821
def get_stock_data_service() -> DataSourceManager:
    """
    获取股票数据服务实例（兼容 stock_data_service 接口）

    ⚠️ 此函数为兼容性接口，实际返回 DataSourceManager 实例
    推荐直接使用 get_data_source_manager()
    """
    return get_data_source_manager()
