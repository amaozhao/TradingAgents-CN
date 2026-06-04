# ruff: noqa: F401,F403,F405,F821
# 全局实例
_improved_hk_provider = None


def get_improved_hk_provider() -> ImprovedHKStockProvider:
    """获取改进的港股提供器实例"""
    global _improved_hk_provider
    if _improved_hk_provider is None:
        _improved_hk_provider = ImprovedHKStockProvider()
    return _improved_hk_provider


def get_hk_company_name_improved(symbol: str) -> str:
    """
    获取港股公司名称的改进版本

    Args:
        symbol: 港股代码

    Returns:
        str: 公司名称
    """
    provider = get_improved_hk_provider()
    return provider.get_company_name(symbol)


def get_hk_stock_info_improved(symbol: str) -> Dict[str, Any]:
    """
    获取港股信息的改进版本

    Args:
        symbol: 港股代码

    Returns:
        Dict: 港股信息
    """
    provider = get_improved_hk_provider()
    return provider.get_stock_info(symbol)


def get_hk_financial_indicators(symbol: str) -> Dict[str, Any]:
    """
    获取港股财务指标

    Args:
        symbol: 港股代码

    Returns:
        Dict: 财务指标数据，包括：
            - eps_basic: 基本每股收益
            - eps_ttm: 滚动每股收益
            - bps: 每股净资产
            - roe_avg: 平均净资产收益率
            - roa: 总资产收益率
            - operate_income: 营业收入
            - operate_income_yoy: 营业收入同比增长率
            - debt_asset_ratio: 资产负债率
            等
    """
    provider = get_improved_hk_provider()
    return provider.get_financial_indicators(symbol)
