# ruff: noqa: F401,F403,F405,F821
class TushareProvider(
    _TushareProviderMixin1,
    _TushareProviderMixin2,
    _TushareProviderMixin3,
    BaseStockDataProvider,
):
    """
    统一的Tushare数据提供器
    合并app层和trading_agents层的所有优势功能
    """
