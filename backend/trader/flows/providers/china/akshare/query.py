# ruff: noqa: F401,F403,F405,F821
class AKShareProvider(
    _AKShareProviderMixin1,
    _AKShareProviderMixin2,
    _AKShareProviderMixin3,
    BaseStockDataProvider,
):
    """
    AKShare统一数据提供器

    提供标准化的股票数据接口，支持：
    - 股票基础信息获取
    - 历史行情数据
    - 实时行情数据
    - 财务数据
    - 港股数据支持
    """
