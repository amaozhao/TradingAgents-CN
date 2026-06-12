from support.registry import export_module as _export_module

_export_module(globals(), "support.hk.priority.module")
_export_module(globals(), "support.improved.hk.utils.module")
del _export_module


def test_improved_hk_provider_facade_exports_provider() -> None:
    from trader.flows.providers.hk import (
        HK_PROVIDER_AVAILABLE,
        ImprovedHKStockProvider,
        get_improved_hk_provider,
    )

    assert HK_PROVIDER_AVAILABLE is True
    assert ImprovedHKStockProvider is not None
    provider = get_improved_hk_provider()
    assert isinstance(provider, ImprovedHKStockProvider)
