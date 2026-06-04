# ruff: noqa: F403,F405
from .common import *
from .models import CostResult


class ConfigManagerUsageMixin:
    def add_usage_record(
        self,
        provider: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        session_id: str,
        analysis_type: str = "stock_analysis",
    ):
        """添加使用记录"""
        # 计算成本和货币单位
        cost_result = self.calculate_cost(
            provider, model_name, input_tokens, output_tokens
        )
        cost = float(cost_result)
        currency = str(getattr(cost_result, "currency", "CNY"))

        record = UsageRecord(
            timestamp=datetime.now(ZoneInfo(get_timezone_name())).isoformat(),
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            currency=currency,
            session_id=session_id,
            analysis_type=analysis_type,
        )

        # 🔍 详细日志：记录保存位置
        logger.info(
            f"💾 [Token记录] 准备保存: {provider}/{model_name}, 输入={input_tokens}, 输出={output_tokens}, 成本=¥{cost:.4f}, session={session_id}"
        )

        # 优先使用PostgreSQL token 存储
        if self.postgres_storage and self.postgres_storage.is_connected():
            logger.info(
                f"📊 [Token记录] 使用 PostgreSQL token 存储 (数据库: {self.postgres_storage.database_name}, 集合: {self.postgres_storage.collection_name})"
            )
            success = self.postgres_storage.save_usage_record(record)
            if success:
                logger.info(
                    f"✅ [Token记录] PostgreSQL 保存成功: {provider}/{model_name}"
                )
                return record
            else:
                logger.error("⚠️ [Token记录] PostgreSQL 保存失败，回退到JSON文件存储")
        else:
            # 🔍 详细日志：为什么没有使用 PostgreSQL
            if self.postgres_storage is None:
                logger.warning(
                    "⚠️ [Token记录] PostgreSQL token 存储未初始化 (postgres_storage=None)"
                )
                logger.warning(
                    f"   💡 请检查环境变量: USE_POSTGRES_STORAGE={os.getenv('USE_POSTGRES_STORAGE', '未设置')}"
                )
            elif not self.postgres_storage.is_connected():
                logger.warning(
                    "⚠️ [Token记录] PostgreSQL document store 未连接 (is_connected=False)"
                )

            logger.info(f"📄 [Token记录] 使用 JSON 文件存储: {self.usage_file}")

        # 回退到JSON文件存储
        records = self.load_usage_records()
        records.append(record)

        # 限制记录数量
        settings = self.load_settings()
        max_records = settings.get("max_usage_records", 10000)
        if len(records) > max_records:
            records = records[-max_records:]

        self.save_usage_records(records)
        logger.info(f"✅ [Token记录] JSON 文件保存成功: {self.usage_file}")
        return record

    def calculate_cost(
        self, provider: str, model_name: str, input_tokens: int, output_tokens: int
    ) -> CostResult:
        """
        计算使用成本

        Returns:
            CostResult: float-compatible cost value, unpackable as (cost, currency)
        """
        pricing_configs = self.load_pricing()

        for pricing in pricing_configs:
            if pricing.provider == provider and pricing.model_name == model_name:
                input_cost = (input_tokens / 1000) * pricing.input_price_per_1k
                output_cost = (output_tokens / 1000) * pricing.output_price_per_1k
                total_cost = input_cost + output_cost
                return CostResult(round(total_cost, 6), pricing.currency)

        # 只在找不到配置时输出调试信息
        logger.warning(
            f"⚠️ [calculate_cost] 未找到匹配的定价配置: {provider}/{model_name}"
        )
        logger.debug("⚠️ [calculate_cost] 可用的配置:")
        for pricing in pricing_configs:
            logger.debug(
                f"⚠️ [calculate_cost]   - {pricing.provider}/{pricing.model_name}"
            )

        return CostResult(0.0, "CNY")
