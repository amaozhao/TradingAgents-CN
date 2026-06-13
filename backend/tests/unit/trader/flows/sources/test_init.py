def test_sources_facade_imports_without_split_module_name_errors() -> None:
    import trader.flows.sources as sources

    assert callable(sources.get_data_source_manager)
