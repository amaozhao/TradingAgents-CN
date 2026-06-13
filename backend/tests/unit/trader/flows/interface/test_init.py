def test_interface_facade_imports_without_split_module_name_errors() -> None:
    import trader.flows.interface as interface

    assert callable(interface.get_finnhub_news)
