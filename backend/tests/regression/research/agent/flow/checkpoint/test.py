import pytest

from app.services.research.agent.flow.checkpoint import UnsupportedCheckpointError
from app.services.research.agent.flow.runner import StockDagParityWorkflow


class ContextWithCheckpoint:
    symbol = "600519"
    trade_date = "2026-06-12"
    task_id = "task-1"
    config = {"checkpoint_enabled": True}


def test_checkpoint_enabled_is_explicitly_blocked_until_adapter_exists():
    with pytest.raises(UnsupportedCheckpointError):
        StockDagParityWorkflow(ContextWithCheckpoint()).run()
