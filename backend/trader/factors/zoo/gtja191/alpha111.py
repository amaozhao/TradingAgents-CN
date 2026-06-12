
# ============================================================
# 中文名称: GTJA Alpha #111
# 简要说明: 国泰君安191短周期交易型alpha因子第111号，详见公式定义。
# 典型用途: 在A股市场经中性化处理后用于选股或股指期货日内交易。
# ============================================================
"""GTJA Alpha 111 (国泰君安 191 短周期交易型 alpha 因子, 2014).

Formula (verbatim from the report):
    SMA(VOL*((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW),11,2) - SMA(VOL*((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW),4,2)

Notes: 
"""
from __future__ import annotations


from trader.factors.base import (
    safe_div,
)

ALPHA_ID = "gtja191_111"

__alpha_meta__ = {
    'id': 'gtja191_111',
    'theme': ['volume', 'microstructure'],
    'formula_latex': 'sma(v*((c-low)-(h-c))/(h-low),11,2)-sma(v*((c-low)-(h-c))/(h-low),4,2)',
    'columns_required': ['open', 'high', 'low', 'close', 'volume'],
    'extras_required': [],
    'universe': ['equity_cn'],
    'frequency': ['1d'],
    'decay_horizon': 11,
    'min_warmup_bars': 12,
    'notes': '',
}


def compute(panel):
    """Compute gtja191_111.

    Args:
        panel: dict[str, pd.DataFrame] with at least the required columns.

    Returns:
        pd.DataFrame with index = panel["close"].index, columns = panel["close"].columns.
    """
    def _sma(x, n, m):
        """SMA(x, n, m) per GTJA convention -> ewm with alpha = m/n."""
        return x.ewm(alpha=m / n, adjust=False).mean()
    c = panel["close"]
    h = panel["high"]
    low = panel["low"]
    v = panel["volume"]
    ratio = safe_div(v * ((c - low) - (h - c)), h - low)
    out = _sma(ratio, 11, 2) - _sma(ratio, 4, 2)
    return out
