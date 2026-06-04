# ruff: noqa: F403,F405
from .common import *


class AnalysisUsageMixin:
    async def _record_token_usage(
        self, task: AnalysisTask, result: AnalysisResult, provider: str, model_name: str
    ):
        """记录 token 使用情况"""
        try:
            # 从结果中提取 token 使用信息
            # 注意：这里需要从 LLM 响应中获取实际的 token 使用量
            # 目前使用估算值
            input_tokens = result.tokens_used // 2 if result.tokens_used > 0 else 0
            output_tokens = (
                result.tokens_used - input_tokens if result.tokens_used > 0 else 0
            )

            # 如果没有 token 使用信息，使用默认估算
            if result.tokens_used == 0:
                # 根据分析类型估算
                input_tokens = 2000  # 默认输入 token
                output_tokens = 1000  # 默认输出 token

            # 获取模型价格配置
            config_service = getattr(
                importlib.import_module("app.services.config"), "config_service"
            )
            config = await config_service.get_system_config()

            # 查找对应的 LLM 配置
            llm_config = None
            if config and config.llm_configs:
                for cfg in config.llm_configs:
                    if cfg.provider == provider and cfg.model_name == model_name:
                        llm_config = cfg
                        break

            # 计算成本
            cost = 0.0
            currency = "CNY"  # 默认货币单位
            if llm_config:
                input_price = llm_config.input_price_per_1k or 0.0
                output_price = llm_config.output_price_per_1k or 0.0
                cost = (input_tokens / 1000 * input_price) + (
                    output_tokens / 1000 * output_price
                )
                currency = llm_config.currency or "CNY"

            # 创建使用记录
            usage_record = UsageRecord(
                timestamp=datetime.now().isoformat(),
                provider=provider,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                currency=currency,
                session_id=task.task_id,
                analysis_type="stock_analysis",
                stock_code=task.symbol,
            )

            # 保存到数据库
            success = await self.usage_service.add_usage_record(usage_record)

            if success:
                logger.info(f"💰 记录使用成本: {provider}/{model_name} - ¥{cost:.4f}")
            else:
                logger.warning("⚠️  记录使用成本失败")

        except Exception as e:
            logger.error(f"❌ 记录 token 使用失败: {e}")
