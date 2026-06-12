from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_auditnames() -> ModuleType:
    for parent in Path(__file__).resolve().parents:
        module_path = parent / "tools" / "auditnames.py"
        if module_path.is_file():
            break
    else:
        raise AssertionError("tools/auditnames.py should exist")

    spec = importlib.util.spec_from_file_location("auditnames_for_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_glued_compounds_are_rejected_without_separators() -> None:
    auditnames = load_auditnames()

    dataframe_reasons = auditnames._validate_single_word_stem("dataframe")
    realtime_reasons = auditnames._validate_single_word_stem("realtime")

    assert dataframe_reasons == ["filename stem is glued compound words: data + frame"]
    assert realtime_reasons == ["filename stem is glued compound words: real + time"]


def test_approved_atomic_code_words_are_not_split() -> None:
    auditnames = load_auditnames()

    for stem in (
        "akshare",
        "database",
        "postgres",
        "openapi",
        "runtime",
        "stocktwits",
        "tushare",
    ):
        assert auditnames._validate_single_word_stem(stem) == []
