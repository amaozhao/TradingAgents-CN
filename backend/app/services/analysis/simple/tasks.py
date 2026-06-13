from __future__ import annotations

from datetime import UTC

from .common import Dict, List, Optional, datetime


def degraded_task_list_result(
    *,
    user_id: str,
    warnings: List[str],
    batch_id: Optional[str] = None,
) -> List[Dict[str, object]]:
    return [{
        "task_id": "task-status-degraded",
        "batch_id": batch_id,
        "user_id": user_id,
        "symbol": None,
        "stock_code": None,
        "stock_symbol": None,
        "stock_name": None,
        "status": "degraded",
        "progress": 0,
        "message": "任务状态读取暂时不可用，请稍后重试。",
        "current_step": "status_unavailable",
        "start_time": datetime.now(UTC).isoformat(),
        "end_time": None,
        "parameters": {},
        "execution_time": None,
        "tokens_used": None,
        "result_data": None,
        "degraded": True,
        "warnings": warnings,
    }]
