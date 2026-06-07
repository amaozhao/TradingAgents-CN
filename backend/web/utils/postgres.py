#!/usr/bin/env python3
"""PostgreSQL document store 报告管理器。"""

import importlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db.store import create_sync_client

logger = logging.getLogger(__name__)


class PostgresReportManager:
    """PostgreSQL document store 报告管理器。"""

    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        self.connected = False

        self._connect()

    def _connect(self):
        """连接到 PostgreSQL document store"""
        try:
            self.client = create_sync_client()
            self.client.admin.command("ping")

            self.db = self.client["trading_agents"]
            self.collection = self.db["analysis_reports"]

            self._create_indexes()

            self.connected = True
            logger.info(
                "✅ PostgreSQL document store 连接成功: trading_agents.analysis_reports"
            )

        except Exception as e:
            logger.error(f"❌ PostgreSQL document store 连接失败: {e}")
            self.connected = False

    def _create_indexes(self):
        """创建索引以提高查询性能"""
        try:
            # 创建复合索引
            self.collection.create_index(
                [("stock_symbol", 1), ("analysis_date", -1), ("timestamp", -1)]
            )

            # 创建单字段索引
            self.collection.create_index("analysis_id")
            self.collection.create_index("status")

            logger.info("✅ PostgreSQL document store 索引兼容调用完成")

        except Exception as e:
            logger.error(f"❌ PostgreSQL document store 索引兼容调用失败: {e}")

    def save_analysis_report(
        self, stock_symbol: str, analysis: Dict[str, Any], reports: Dict[str, str]
    ) -> bool:
        """保存分析报告到 PostgreSQL document store"""
        if not self.connected:
            logger.warning("PostgreSQL document store 未连接，跳过保存")
            return False

        try:
            # 生成分析ID
            timestamp = datetime.now()
            analysis_id = f"{stock_symbol}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

            # 🔥 根据股票代码推断市场类型
            StockUtils = getattr(
                importlib.import_module("trader.utils.stocks"), "StockUtils"
            )
            market_info = StockUtils.get_market_info(stock_symbol)
            market_type_map = {
                "china_a": "A股",
                "hong_kong": "港股",
                "us": "美股",
                "unknown": "A股",  # 默认为A股
            }
            market_type = market_type_map.get(
                market_info.get("market", "unknown"), "A股"
            )
            logger.info(f"📊 推断市场类型: {stock_symbol} -> {market_type}")

            # 🔥 获取股票名称
            stock_name = stock_symbol  # 默认使用股票代码
            try:
                if market_info.get("market") == "china_a":
                    # A股：使用统一接口获取股票信息
                    get_china_stock_info_unified = getattr(
                        importlib.import_module("trader.flows.interface"),
                        "get_china_stock_info_unified",
                    )
                    stock_info = get_china_stock_info_unified(stock_symbol)
                    if "股票名称:" in stock_info:
                        stock_name = (
                            stock_info.split("股票名称:")[1].split("\n")[0].strip()
                        )
                        logger.info(f"📊 获取A股名称: {stock_symbol} -> {stock_name}")
                elif market_info.get("market") == "hong_kong":
                    # 港股：使用改进的港股工具
                    try:
                        get_hk_company_name_improved = getattr(
                            importlib.import_module(
                                "trader.flows.providers.hk.improved"
                            ),
                            "get_hk_company_name_improved",
                        )
                        stock_name = get_hk_company_name_improved(stock_symbol)
                        logger.info(f"📊 获取港股名称: {stock_symbol} -> {stock_name}")
                    except Exception:
                        clean_ticker = stock_symbol.replace(".HK", "").replace(
                            ".hk", ""
                        )
                        stock_name = f"港股{clean_ticker}"
                elif market_info.get("market") == "us":
                    # 美股：使用简单映射
                    us_stock_names = {
                        "AAPL": "苹果公司",
                        "TSLA": "特斯拉",
                        "NVDA": "英伟达",
                        "MSFT": "微软",
                        "GOOGL": "谷歌",
                        "AMZN": "亚马逊",
                        "META": "Meta",
                        "NFLX": "奈飞",
                    }
                    stock_name = us_stock_names.get(
                        stock_symbol.upper(), f"美股{stock_symbol}"
                    )
                    logger.info(f"📊 获取美股名称: {stock_symbol} -> {stock_name}")
            except Exception as e:
                logger.warning(f"⚠️ 获取股票名称失败: {stock_symbol} - {e}")
                stock_name = stock_symbol

            # 获取模型信息
            model_info = analysis.get("model_info", "Unknown")

            # 构建文档
            document = {
                "analysis_id": analysis_id,
                "stock_symbol": stock_symbol,
                "stock_name": stock_name,  # 🔥 添加股票名称字段
                "market_type": market_type,  # 🔥 添加市场类型字段
                "model_info": model_info,  # 🔥 添加模型信息字段
                "analysis_date": timestamp.strftime("%Y-%m-%d"),
                "timestamp": timestamp,
                "status": "completed",
                "source": "postgres",
                # 分析结果摘要
                "summary": analysis.get("summary", ""),
                "analysts": analysis.get("analysts", []),
                "research_depth": analysis.get(
                    "research_depth", 1
                ),  # 修正：从分析结果中获取真实的研究深度
                # 报告内容
                "reports": reports,
                # 元数据
                "created_at": timestamp,
                "updated_at": timestamp,
            }

            # 插入文档
            result = self.collection.insert_one(document)

            if result.inserted_id:
                logger.info(
                    f"✅ 分析报告已保存到 PostgreSQL document store: {analysis_id}"
                )
                return True
            else:
                logger.error("❌ PostgreSQL document store 插入失败")
                return False

        except Exception as e:
            logger.error(f"❌ 保存分析报告到 PostgreSQL document store 失败: {e}")
            return False

    def get_analysis_reports(
        self,
        limit: int = 100,
        stock_symbol: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> List[Dict[str, Any]]:
        """从 PostgreSQL document store 获取分析报告"""
        if not self.connected:
            return []

        try:
            # 构建查询条件
            query = {}

            if stock_symbol:
                query["stock_symbol"] = stock_symbol

            if start_date or end_date:
                date_query = {}
                if start_date:
                    date_query["$gte"] = start_date
                if end_date:
                    date_query["$lte"] = end_date
                query["analysis_date"] = date_query

            # 查询数据
            cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)

            results = []
            for doc in cursor:
                # 处理timestamp字段，兼容不同的数据类型
                timestamp_value = doc.get("timestamp")
                if hasattr(timestamp_value, "timestamp"):
                    # datetime对象
                    timestamp = timestamp_value.timestamp()
                elif isinstance(timestamp_value, (int, float)):
                    # 已经是时间戳
                    timestamp = float(timestamp_value)
                else:
                    # 其他情况，使用当前时间
                    datetime = getattr(importlib.import_module("datetime"), "datetime")
                    timestamp = datetime.now().timestamp()

                # 转换为Web应用期望的格式
                result = {
                    "analysis_id": doc["analysis_id"],
                    "timestamp": timestamp,
                    "stock_symbol": doc["stock_symbol"],
                    "analysts": doc.get("analysts", []),
                    "research_depth": doc.get("research_depth", 0),
                    "status": doc.get("status", "completed"),
                    "summary": doc.get("summary", ""),
                    "performance": {},
                    "tags": [],
                    "is_favorite": False,
                    "reports": doc.get("reports", {}),
                    "source": "postgres",
                }
                results.append(result)

            logger.info(
                f"✅ 从 PostgreSQL document store 获取到 {len(results)} 个分析报告"
            )
            return results

        except Exception as e:
            logger.error(f"❌ 从 PostgreSQL document store 获取分析报告失败: {e}")
            return []

    def get_report_by_id(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取单个分析报告"""
        if not self.connected:
            return None

        try:
            doc = self.collection.find_one({"analysis_id": analysis_id})

            if doc:
                # 转换为Web应用期望的格式
                result = {
                    "analysis_id": doc["analysis_id"],
                    "timestamp": doc["timestamp"].timestamp(),
                    "stock_symbol": doc["stock_symbol"],
                    "analysts": doc.get("analysts", []),
                    "research_depth": doc.get("research_depth", 0),
                    "status": doc.get("status", "completed"),
                    "summary": doc.get("summary", ""),
                    "performance": {},
                    "tags": [],
                    "is_favorite": False,
                    "reports": doc.get("reports", {}),
                    "source": "postgres",
                }
                return result

            return None

        except Exception as e:
            logger.error(f"❌ 从 PostgreSQL document store 获取报告失败: {e}")
            return None

    def delete_report(self, analysis_id: str) -> bool:
        """删除分析报告"""
        if not self.connected:
            return False

        try:
            result = self.collection.delete_one({"analysis_id": analysis_id})

            if result.deleted_count > 0:
                logger.info(f"✅ 已删除分析报告: {analysis_id}")
                return True
            else:
                logger.warning(f"⚠️ 未找到要删除的报告: {analysis_id}")
                return False

        except Exception as e:
            logger.error(f"❌ 删除分析报告失败: {e}")
            return False

    def get_all_reports(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """获取所有分析报告"""
        if not self.connected:
            return []

        try:
            # 获取所有报告，按时间戳降序排列
            cursor = self.collection.find().sort("timestamp", -1).limit(limit)
            reports = list(cursor)

            # 转换DocumentId为字符串
            for report in reports:
                if "_id" in report:
                    report["_id"] = str(report["_id"])

            logger.info(
                f"✅ 从 PostgreSQL document store 获取了 {len(reports)} 个分析报告"
            )
            return reports

        except Exception as e:
            logger.error(f"❌ 从 PostgreSQL document store 获取所有报告失败: {e}")
            return []

    def fix_inconsistent_reports(self) -> bool:
        """修复不一致的报告数据结构"""
        if not self.connected:
            logger.warning("PostgreSQL document store 未连接，跳过修复")
            return False

        try:
            # 查找缺少reports字段或reports字段为空的文档
            query = {
                "$or": [
                    {"reports": {"$exists": False}},
                    {"reports": {}},
                    {"reports": None},
                ]
            }

            cursor = self.collection.find(query)
            inconsistent_docs = list(cursor)

            if not inconsistent_docs:
                logger.info("✅ 所有报告数据结构一致，无需修复")
                return True

            logger.info(f"🔧 发现 {len(inconsistent_docs)} 个不一致的报告，开始修复...")

            fixed_count = 0
            for doc in inconsistent_docs:
                try:
                    # 为缺少reports字段的文档添加空的reports字段
                    update_data = {
                        "$set": {"reports": {}, "updated_at": datetime.now()}
                    }

                    result = self.collection.update_one(
                        {"_id": doc["_id"]}, update_data
                    )

                    if result.modified_count > 0:
                        fixed_count += 1
                        logger.info(f"✅ 修复报告: {doc.get('analysis_id', 'unknown')}")

                except Exception as e:
                    logger.error(
                        f"❌ 修复报告失败 {doc.get('analysis_id', 'unknown')}: {e}"
                    )

            logger.info(f"✅ 修复完成，共修复 {fixed_count} 个报告")
            return True

        except Exception as e:
            logger.error(f"❌ 修复不一致报告失败: {e}")
            return False

    def save_report(self, report_data: Dict[str, Any]) -> bool:
        """保存报告数据（通用方法）"""
        if not self.connected:
            logger.warning("PostgreSQL document store 未连接，跳过保存")
            return False

        try:
            # 确保有必要的字段
            if "analysis_id" not in report_data:
                logger.error("报告数据缺少analysis_id字段")
                return False

            # 添加保存时间戳
            report_data["saved_at"] = datetime.now()

            # 使用upsert操作，如果存在则更新，不存在则插入
            result = self.collection.replace_one(
                {"analysis_id": report_data["analysis_id"]}, report_data, upsert=True
            )

            if result.upserted_id or result.modified_count > 0:
                logger.info(f"✅ 报告保存成功: {report_data['analysis_id']}")
                return True
            else:
                logger.warning(f"⚠️ 报告保存无变化: {report_data['analysis_id']}")
                return True

        except Exception as e:
            logger.error(f"❌ 保存报告到 PostgreSQL document store 失败: {e}")
            return False


# 创建全局实例
postgres_report_manager = PostgresReportManager()
