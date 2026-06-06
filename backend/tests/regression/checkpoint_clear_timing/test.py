from types import SimpleNamespace

import app.services.analysis.simple.task as task_module
from app.services.analysis.simple.task import AnalysisTaskMixin


def test_analysis_checkpoint_is_cleared_only_after_task_completion(monkeypatch):
    cleared = []

    def fake_import_module(name):
        if name == "trader.default":
            return SimpleNamespace(DEFAULT_CONFIG={"data_cache_dir": "/tmp/cache"})
        if name == "trader.graph.checkpointer":
            return SimpleNamespace(
                clear_checkpoint=lambda data_dir, stock, date: cleared.append(
                    (data_dir, stock, date)
                )
            )
        return __import__(name, fromlist=["*"])

    monkeypatch.setattr(task_module.importlib, "import_module", fake_import_module)

    request = SimpleNamespace(get_symbol=lambda: "600519")
    AnalysisTaskMixin()._clear_analysis_checkpoint_after_completion(
        request,
        {"stock_code": "600519", "analysis_date": "2026-06-06"},
    )

    assert cleared == [("/tmp/cache", "600519", "2026-06-06")]
