# ruff: noqa: F403,F405
from __future__ import annotations

from .common import *


class TokenTracker:
    """Token使用跟踪器"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def track_usage(
        self,
        provider: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        session_id: Optional[str] = None,
        analysis_type: str = "stock_analysis",
    ):
        """跟踪Token使用"""
        if session_id is None:
            session_id = f"session_{datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y%m%d_%H%M%S')}"

        # 检查是否启用成本跟踪
        settings = self.config_manager.load_settings()
        cost_tracking_enabled = settings.get("enable_cost_tracking", True)

        if not cost_tracking_enabled:
            return None

        # 添加使用记录
        record = self.config_manager.add_usage_record(
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            session_id=session_id,
            analysis_type=analysis_type,
        )

        # 检查成本警告
        if record:
            self._check_cost_alert(record.cost)

        return record

    def _check_cost_alert(self, current_cost: float):
        """检查成本警告"""
        settings = self.config_manager.load_settings()
        threshold = settings.get("cost_alert_threshold", 100.0)

        # 获取今日总成本
        today_stats = self.config_manager.get_usage_statistics(1)
        total_today = today_stats["total_cost"]

        if total_today >= threshold:
            logger.warning(
                f"⚠️ 成本警告: 今日成本已达到 ¥{total_today:.4f}，超过阈值 ¥{threshold}",
                extra={
                    "cost": total_today,
                    "threshold": threshold,
                    "event_type": "cost_alert",
                },
            )

    def get_session_cost(self, session_id: str) -> float:
        """获取会话成本"""
        records = self.config_manager.load_usage_records()
        session_cost = sum(
            record.cost for record in records if record.session_id == session_id
        )
        return session_cost

    def estimate_cost(
        self,
        provider: str,
        model_name: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> tuple[float, str]:
        """
        估算成本

        Returns:
            tuple[float, str]: (成本, 货币单位)
        """
        cost_result = self.config_manager.calculate_cost(
            provider, model_name, estimated_input_tokens, estimated_output_tokens
        )
        return float(cost_result), str(getattr(cost_result, "currency", "CNY"))
