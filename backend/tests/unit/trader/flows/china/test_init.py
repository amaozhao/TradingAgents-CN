def test_china_facade_imports_without_split_module_name_errors() -> None:
    import trader.flows.china as china

    assert china.OptimizedChinaDataProvider.__name__ == "OptimizedChinaDataProvider"
