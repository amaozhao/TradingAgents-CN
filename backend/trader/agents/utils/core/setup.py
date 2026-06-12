from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        Any,
        DEFAULT_CONFIG,
        HumanMessage,
        Mapping,
        Optional,
        RemoveMessage,
        functools,
        importlib,
        logger,
        yf,
    )

def get_language_instruction() -> str:
    """Return output-language instruction compatible with upstream agents."""
    lang = DEFAULT_CONFIG.get("output_language", "Chinese")
    if not isinstance(lang, str) or lang.strip().lower() in {"", "english"}:
        return ""
    return f" 请使用{lang}完成整个回答。"


def _clean_identity_value(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"none", "n/a", "nan", "null", "未知"}:
        return None
    return cleaned


@functools.lru_cache(maxsize=256)
def resolve_instrument_identity(ticker: str) -> dict:
    """Resolve deterministic identity metadata without blocking CN analysis."""
    normalized_ticker = str(ticker).strip().upper()
    identity: dict[str, str] = {}

    # Avoid yfinance for plain A-share numeric codes. CN data providers own
    # those identities and yfinance can produce misleading/noisy metadata.
    is_plain_cn_code = (
        len(normalized_ticker) == 6
        and normalized_ticker.isdigit()
        and normalized_ticker[0] in {"0", "3", "6"}
    )
    if is_plain_cn_code:
        try:
            StockUtils = getattr(
                importlib.import_module("trader.utils.stocks"), "StockUtils"
            )

            market_info = StockUtils.get_market_info(normalized_ticker)
            market_name = _clean_identity_value(market_info.get("market_name"))
            currency = _clean_identity_value(market_info.get("currency_name"))
            if market_name:
                identity["exchange"] = market_name
            if currency:
                identity["currency"] = currency
        except Exception as exc:
            logger.debug(f"无法从 StockUtils 解析标的信息 {normalized_ticker}: {exc}")
        identity.setdefault("quote_type", "A-share")
        return identity

    try:
        info = yf.Ticker(normalized_ticker).info or {}
    except Exception as exc:
        logger.debug(f"无法从 yfinance 解析标的信息 {normalized_ticker}: {exc}")
        return identity

    company_name = _clean_identity_value(info.get("longName")) or _clean_identity_value(
        info.get("shortName")
    )
    if company_name:
        identity["company_name"] = company_name
    for source_key, target_key in (
        ("sector", "sector"),
        ("industry", "industry"),
        ("exchange", "exchange"),
        ("quoteType", "quote_type"),
    ):
        value = _clean_identity_value(info.get(source_key))
        if value:
            identity[target_key] = value
    return identity


def build_instrument_context(
    ticker: str,
    asset_type: str = "stock",
    identity: Optional[Mapping[str, str]] = None,
) -> str:
    _build = getattr(
        importlib.import_module("trader.agents.utils.instruments"),
        "build_instrument_context",
    )

    return _build(ticker, asset_type=asset_type, identity=identity)


def get_instrument_context_from_state(state: Mapping[str, Any]) -> str:
    context = state.get("instrument_context")
    if isinstance(context, str) and context.strip():
        return context
    return build_instrument_context(
        str(state["company_of_interest"]),
        state.get("asset_type", "stock"),
    )


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        instrument_context = get_instrument_context_from_state(state)
        trade_date = state.get("trade_date", "")
        placeholder = HumanMessage(
            content=(
                f"继续分析，不要改变分析标的。{instrument_context}"
                f" 当前交易日期：{trade_date}。"
            )
        )

        return {"messages": removal_operations + [placeholder]}

    return delete_messages
