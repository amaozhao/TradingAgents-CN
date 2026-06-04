from typing import Mapping, Optional


def build_instrument_context(
    ticker: str,
    asset_type: str = "stock",
    identity: Optional[Mapping[str, str]] = None,
) -> str:
    normalized_ticker = str(ticker).strip().upper()
    is_crypto = asset_type == "crypto"
    instrument_label = "加密资产" if is_crypto else "股票/证券标的"
    context = (
        f"当前分析标的的精确股票代码是 `{normalized_ticker}`。"
        f"The exact ticker symbol is `{normalized_ticker}`; preserve any exchange suffix exactly. "
        f"该标的是{instrument_label}。"
        "在所有工具调用、分析报告、交易建议和最终结论中，都必须使用这个完全一致的股票代码。"
        "如果代码带有交易所后缀，例如 `.SH`、`.SZ`、`.SS`、`.HK`、`.TO`、`.L`、`.T`、`-USD`，必须原样保留，绝对不能省略、改写或替换。"
    )
    if identity:
        details = []
        name = identity.get("company_name") or identity.get("name")
        if name:
            details.append(
                f"名称/Company: {name}" if not is_crypto else f"名称/Name: {name}"
            )
        sector = identity.get("sector")
        industry = identity.get("industry")
        if sector and industry:
            details.append(f"行业分类/Sector: {sector} / {industry}")
        elif sector:
            details.append(f"板块：{sector}")
        elif industry:
            details.append(f"行业：{industry}")
        exchange = identity.get("exchange")
        if exchange:
            details.append(f"交易所/Exchange: {exchange}")
        if details:
            context += (
                " 已解析的标的信息/Resolved identity: "
                + "；".join(details)
                + "。不得在没有工具证据的情况下替换为其他公司或代码。"
                " Do not substitute a different company or ticker."
            )
    if is_crypto:
        context += " 请按加密资产处理，不要假设存在公司基本面报表。 Treat it as a crypto asset rather than a company."
    return context
