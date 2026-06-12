from support.registry import export_module as _export_module

_export_module(globals(), "support.debug.full.flow.module")
_export_module(globals(), "support.cache.optimization.module")
_export_module(globals(), "support.financial.data.validation.module")
_export_module(globals(), "support.optimized.fundamentals.simple.module")
_export_module(globals(), "support.performance.comparison.module")
del _export_module


def test_china_facade_imports_without_split_module_name_errors() -> None:
    import trader.flows.china as china

    assert china.OptimizedChinaDataProvider.__name__ == "OptimizedChinaDataProvider"
