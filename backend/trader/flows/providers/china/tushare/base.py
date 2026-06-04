# ruff: noqa: F401,F403,F405,F821
class _TushareProviderMixin2:
    async def get_financial_data(
        self,
        symbol: str,
        report_type: str = "quarterly",
        period: Optional[str] = None,
        limit: int = 4,
    ) -> Optional[Dict[str, Any]]:
        """
        获取财务数据

        Args:
            symbol: 股票代码
            report_type: 报告类型 (quarterly/annual)
            period: 指定报告期 (YYYYMMDD格式)，为空则获取最新数据
            limit: 获取记录数量，默认4条（最近4个季度）

        Returns:
            财务数据字典，包含利润表、资产负债表、现金流量表和财务指标
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)
            self.logger.debug(f"📊 获取Tushare财务数据: {ts_code}, 类型: {report_type}")

            # 构建查询参数
            query_params = {"ts_code": ts_code, "limit": limit}

            # 如果指定了报告期，添加期间参数
            if period:
                query_params["period"] = period

            financial_data = {}

            # 1. 获取利润表数据 (income statement)
            try:
                income_df = await asyncio.to_thread(self.api.income, **query_params)
                if income_df is not None and not income_df.empty:
                    financial_data["income_statement"] = income_df.to_dict("records")
                    self.logger.debug(
                        f"✅ {ts_code} 利润表数据获取成功: {len(income_df)} 条记录"
                    )
                else:
                    self.logger.debug(f"⚠️ {ts_code} 利润表数据为空")
            except Exception as e:
                self.logger.warning(f"❌ 获取{ts_code}利润表数据失败: {e}")

            # 2. 获取资产负债表数据 (balance sheet)
            try:
                balance_df = await asyncio.to_thread(
                    self.api.balancesheet, **query_params
                )
                if balance_df is not None and not balance_df.empty:
                    financial_data["balance_sheet"] = balance_df.to_dict("records")
                    self.logger.debug(
                        f"✅ {ts_code} 资产负债表数据获取成功: {len(balance_df)} 条记录"
                    )
                else:
                    self.logger.debug(f"⚠️ {ts_code} 资产负债表数据为空")
            except Exception as e:
                self.logger.warning(f"❌ 获取{ts_code}资产负债表数据失败: {e}")

            # 3. 获取现金流量表数据 (cash flow statement)
            try:
                cashflow_df = await asyncio.to_thread(self.api.cashflow, **query_params)
                if cashflow_df is not None and not cashflow_df.empty:
                    financial_data["cashflow_statement"] = cashflow_df.to_dict(
                        "records"
                    )
                    self.logger.debug(
                        f"✅ {ts_code} 现金流量表数据获取成功: {len(cashflow_df)} 条记录"
                    )
                else:
                    self.logger.debug(f"⚠️ {ts_code} 现金流量表数据为空")
            except Exception as e:
                self.logger.warning(f"❌ 获取{ts_code}现金流量表数据失败: {e}")

            # 4. 获取财务指标数据 (financial indicators)
            try:
                indicator_df = await asyncio.to_thread(
                    self.api.fina_indicator, **query_params
                )
                if indicator_df is not None and not indicator_df.empty:
                    financial_data["financial_indicators"] = indicator_df.to_dict(
                        "records"
                    )
                    self.logger.debug(
                        f"✅ {ts_code} 财务指标数据获取成功: {len(indicator_df)} 条记录"
                    )
                else:
                    self.logger.debug(f"⚠️ {ts_code} 财务指标数据为空")
            except Exception as e:
                self.logger.warning(f"❌ 获取{ts_code}财务指标数据失败: {e}")

            # 5. 获取主营业务构成数据 (可选)
            try:
                mainbz_df = await asyncio.to_thread(
                    self.api.fina_mainbz, **query_params
                )
                if mainbz_df is not None and not mainbz_df.empty:
                    financial_data["main_business"] = mainbz_df.to_dict("records")
                    self.logger.debug(
                        f"✅ {ts_code} 主营业务构成数据获取成功: {len(mainbz_df)} 条记录"
                    )
                else:
                    self.logger.debug(f"⚠️ {ts_code} 主营业务构成数据为空")
            except Exception as e:
                self.logger.debug(
                    f"获取{ts_code}主营业务构成数据失败: {e}"
                )  # 主营业务数据不是必需的，保持debug级别

            if financial_data:
                # 标准化财务数据
                standardized_data = self._standardize_tushare_financial_data(
                    financial_data, ts_code
                )
                self.logger.info(
                    f"✅ {ts_code} Tushare财务数据获取完成: {len(financial_data)} 个数据集"
                )
                return standardized_data
            else:
                self.logger.warning(f"⚠️ {ts_code} 未获取到任何Tushare财务数据")
                return None

        except Exception as e:
            self.logger.error(f"❌ 获取Tushare财务数据失败 symbol={symbol}: {e}")
            return None

    async def get_stock_news(
        self,
        symbol: Optional[str] = None,
        limit: int = 10,
        hours_back: int = 24,
        src: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票新闻（需要Tushare新闻权限）

        Args:
            symbol: 股票代码，为None时获取市场新闻
            limit: 返回数量限制
            hours_back: 回溯小时数，默认24小时
            src: 新闻源，默认自动选择

        Returns:
            新闻列表
        """
        if not self.is_available():
            return None

        try:
            datetime = getattr(importlib.import_module("datetime"), "datetime")
            timedelta = getattr(importlib.import_module("datetime"), "timedelta")

            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)

            start_date = start_time.strftime("%Y-%m-%d %H:%M:%S")
            end_date = end_time.strftime("%Y-%m-%d %H:%M:%S")

            self.logger.debug(
                f"📰 获取Tushare新闻: symbol={symbol}, 时间范围={start_date} 到 {end_date}"
            )

            # 支持的新闻源列表（按优先级排序）
            news_sources = [
                "sina",  # 新浪财经
                "eastmoney",  # 东方财富
                "10jqka",  # 同花顺
                "wallstreetcn",  # 华尔街见闻
                "cls",  # 财联社
                "yicai",  # 第一财经
                "jinrongjie",  # 金融界
                "yuncaijing",  # 云财经
                "fenghuang",  # 凤凰新闻
            ]

            # 如果指定了数据源，优先使用
            if src and src in news_sources:
                sources_to_try = [src]
            else:
                sources_to_try = news_sources[:3]  # 默认尝试前3个源

            all_news = []

            for source in sources_to_try:
                try:
                    self.logger.debug(f"📰 尝试从 {source} 获取新闻...")

                    # 获取新闻数据
                    news_df = await asyncio.to_thread(
                        self.api.news,
                        src=source,
                        start_date=start_date,
                        end_date=end_date,
                    )

                    if news_df is not None and not news_df.empty:
                        source_news = self._process_tushare_news(
                            news_df, source, symbol, limit
                        )
                        all_news.extend(source_news)

                        self.logger.info(
                            f"✅ 从 {source} 获取到 {len(source_news)} 条新闻"
                        )

                        # 如果已经获取足够的新闻，停止尝试其他源
                        if len(all_news) >= limit:
                            break
                    else:
                        self.logger.debug(f"⚠️ {source} 未返回新闻数据")

                except Exception as e:
                    self.logger.debug(f"从 {source} 获取新闻失败: {e}")
                    continue

                # API限流
                await asyncio.sleep(0.2)

            # 去重和排序
            if all_news:
                # 按时间排序并去重
                unique_news = self._deduplicate_news(all_news)
                sorted_news = sorted(
                    unique_news,
                    key=lambda x: x.get("publish_time", datetime.min),
                    reverse=True,
                )

                # 限制返回数量
                final_news = sorted_news[:limit]

                self.logger.info(
                    f"✅ Tushare新闻获取成功: {len(final_news)} 条（去重后）"
                )
                return final_news
            else:
                self.logger.warning("⚠️ 未获取到任何Tushare新闻数据")
                return []

        except Exception as e:
            # 如果是权限问题，给出明确提示
            if any(
                keyword in str(e).lower()
                for keyword in ["权限", "permission", "unauthorized", "access denied"]
            ):
                self.logger.warning(
                    f"⚠️ Tushare新闻接口需要单独开通权限（付费功能）: {e}"
                )
            elif "积分" in str(e) or "point" in str(e).lower():
                self.logger.warning(f"⚠️ Tushare积分不足，无法获取新闻数据: {e}")
            else:
                self.logger.error(f"❌ 获取Tushare新闻失败: {e}")
            return None

    def _process_tushare_news(
        self,
        news_df: pd.DataFrame,
        source: str,
        symbol: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """处理Tushare新闻数据"""
        news_list = []

        # 限制处理数量
        df_limited = news_df.head(limit * 2)  # 多获取一些，用于过滤

        for _, row in df_limited.iterrows():
            title = str(row.get("title", "") or "")
            content = str(row.get("content", "") or "")
            channels = str(row.get("channels", "") or "")
            datetime_text = str(row.get("datetime", "") or "")
            news_item = {
                "title": title or content[:50] + "...",
                "content": content,
                "summary": self._generate_summary(content),
                "url": "",  # Tushare新闻接口不提供URL
                "source": self._get_source_name(source),
                "author": "",
                "publish_time": self._parse_tushare_news_time(datetime_text),
                "category": self._classify_tushare_news(channels, content),
                "sentiment": self._analyze_news_sentiment(content, title),
                "importance": self._assess_news_importance(content, title),
                "keywords": self._extract_keywords(content, title),
                "data_source": "tushare",
                "original_source": source,
            }

            # 如果指定了股票代码，过滤相关新闻
            if symbol:
                if self._is_news_relevant_to_symbol(news_item, symbol):
                    news_list.append(news_item)
            else:
                news_list.append(news_item)

        return news_list

    def _get_source_name(self, source_code: str) -> str:
        """获取新闻源中文名称"""
        source_names = {
            "sina": "新浪财经",
            "eastmoney": "东方财富",
            "10jqka": "同花顺",
            "wallstreetcn": "华尔街见闻",
            "cls": "财联社",
            "yicai": "第一财经",
            "jinrongjie": "金融界",
            "yuncaijing": "云财经",
            "fenghuang": "凤凰新闻",
        }
        return source_names.get(source_code, source_code)

    def _generate_summary(self, content: str) -> str:
        """生成新闻摘要"""
        if not content:
            return ""

        content_str = str(content)
        if len(content_str) <= 200:
            return content_str

        # 简单的摘要生成：取前200个字符
        return content_str[:200] + "..."

    def _is_news_relevant_to_symbol(
        self, news_item: Dict[str, Any], symbol: str
    ) -> bool:
        """判断新闻是否与股票相关"""
        content = news_item.get("content", "").lower()
        title = news_item.get("title", "").lower()

        # 标准化股票代码
        symbol_clean = symbol.replace(".SH", "").replace(".SZ", "").zfill(6)

        # 关键词匹配
        return any(
            [
                symbol_clean in content,
                symbol_clean in title,
                symbol in content,
                symbol in title,
            ]
        )

    def _deduplicate_news(
        self, news_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """新闻去重"""
        seen_titles = set()
        unique_news = []

        for news in news_list:
            title = news.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news)

        return unique_news

    def _analyze_news_sentiment(self, content: str, title: str) -> str:
        """分析新闻情绪"""
        text = f"{title} {content}".lower()

        positive_keywords = [
            "利好",
            "上涨",
            "增长",
            "盈利",
            "突破",
            "创新高",
            "买入",
            "推荐",
        ]
        negative_keywords = [
            "利空",
            "下跌",
            "亏损",
            "风险",
            "暴跌",
            "卖出",
            "警告",
            "下调",
        ]

        positive_count = sum(1 for keyword in positive_keywords if keyword in text)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    def _assess_news_importance(self, content: str, title: str) -> str:
        """评估新闻重要性"""
        text = f"{title} {content}".lower()

        high_importance_keywords = [
            "业绩",
            "财报",
            "重大",
            "公告",
            "监管",
            "政策",
            "并购",
            "重组",
        ]
        medium_importance_keywords = ["分析", "预测", "观点", "建议", "行业", "市场"]

        if any(keyword in text for keyword in high_importance_keywords):
            return "high"
        elif any(keyword in text for keyword in medium_importance_keywords):
            return "medium"
        else:
            return "low"

    def _extract_keywords(self, content: str, title: str) -> List[str]:
        """提取关键词"""
        text = f"{title} {content}"

        # 简单的关键词提取
        keywords = []
        common_keywords = [
            "股票",
            "公司",
            "市场",
            "投资",
            "业绩",
            "财报",
            "政策",
            "行业",
            "分析",
            "预测",
        ]

        for keyword in common_keywords:
            if keyword in text:
                keywords.append(keyword)

        return keywords[:5]  # 最多返回5个关键词

    def _parse_tushare_news_time(self, time_str: str) -> Optional[datetime]:
        """解析Tushare新闻时间"""
        if not time_str:
            return datetime.now(UTC).replace(tzinfo=None)

        try:
            # Tushare时间格式: 2018-11-21 09:30:00
            return datetime.strptime(str(time_str), "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            self.logger.debug(f"解析Tushare新闻时间失败: {e}")
            return datetime.now(UTC).replace(tzinfo=None)

    def _classify_tushare_news(self, channels: str, content: str) -> str:
        """分类Tushare新闻"""
        channels = str(channels).lower()
        content = str(content).lower()

        # 根据频道和内容关键词分类
        if any(
            keyword in channels or keyword in content
            for keyword in ["公告", "业绩", "财报"]
        ):
            return "company_announcement"
        elif any(
            keyword in channels or keyword in content
            for keyword in ["政策", "监管", "央行"]
        ):
            return "policy_news"
        elif any(
            keyword in channels or keyword in content for keyword in ["行业", "板块"]
        ):
            return "industry_news"
        elif any(
            keyword in channels or keyword in content
            for keyword in ["市场", "指数", "大盘"]
        ):
            return "market_news"
        else:
            return "other"

    async def get_financial_data_by_period(
        self,
        symbol: str,
        start_period: Optional[str] = None,
        end_period: Optional[str] = None,
        report_type: str = "quarterly",
    ) -> Optional[List[Dict[str, Any]]]:
        """
        按时间范围获取财务数据

        Args:
            symbol: 股票代码
            start_period: 开始报告期 (YYYYMMDD)
            end_period: 结束报告期 (YYYYMMDD)
            report_type: 报告类型 (quarterly/annual)

        Returns:
            财务数据列表，按报告期倒序排列
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)
            self.logger.debug(
                f"📊 按期间获取Tushare财务数据: {ts_code}, {start_period} - {end_period}"
            )

            # 构建查询参数
            query_params = {"ts_code": ts_code}

            if start_period:
                query_params["start_date"] = start_period
            if end_period:
                query_params["end_date"] = end_period

            # 获取利润表数据作为主要数据源
            income_df = await asyncio.to_thread(self.api.income, **query_params)

            if income_df is None or income_df.empty:
                self.logger.warning(f"⚠️ {ts_code} 指定期间无财务数据")
                return None

            # 按报告期分组获取完整财务数据
            financial_data_list = []

            for _, income_row in income_df.iterrows():
                period = income_row["end_date"]

                # 获取该期间的完整财务数据
                period_data = await self.get_financial_data(
                    symbol=symbol, period=period, limit=1
                )

                if period_data:
                    financial_data_list.append(period_data)

                # API限流
                await asyncio.sleep(0.1)

            self.logger.info(
                f"✅ {ts_code} 按期间获取财务数据完成: {len(financial_data_list)} 个报告期"
            )
            return financial_data_list

        except Exception as e:
            self.logger.error(f"❌ 按期间获取Tushare财务数据失败 symbol={symbol}: {e}")
            return None

    async def get_financial_indicators_only(
        self, symbol: str, limit: int = 4
    ) -> Optional[Dict[str, Any]]:
        """
        仅获取财务指标数据（轻量级接口）

        Args:
            symbol: 股票代码
            limit: 获取记录数量

        Returns:
            财务指标数据
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)

            # 仅获取财务指标
            indicator_df = await asyncio.to_thread(
                self.api.fina_indicator, ts_code=ts_code, limit=limit
            )

            if indicator_df is not None and not indicator_df.empty:
                indicators = indicator_df.to_dict("records")

                return {
                    "symbol": symbol,
                    "ts_code": ts_code,
                    "financial_indicators": indicators,
                    "data_source": "tushare",
                    "updated_at": datetime.now(UTC).replace(tzinfo=None),
                }

            return None

        except Exception as e:
            self.logger.error(f"❌ 获取Tushare财务指标失败 symbol={symbol}: {e}")
            return None

    def standardize_basic_info(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化股票基础信息"""
        ts_code = raw_data.get("ts_code", "")
        symbol = raw_data.get(
            "symbol", ts_code.split(".")[0] if "." in ts_code else ts_code
        )

        return {
            # 基础字段
            "code": symbol,
            "name": raw_data.get("name", ""),
            "symbol": symbol,
            "full_symbol": ts_code,
            # 市场信息
            "market_info": self._determine_market_info_from_ts_code(ts_code),
            # 业务信息
            "area": self._safe_str(raw_data.get("area")),
            "industry": self._safe_str(raw_data.get("industry")),
            "market": raw_data.get("market"),  # 主板/创业板/科创板
            "list_date": self._format_date_output(raw_data.get("list_date")),
            # 港股通信息
            "is_hs": raw_data.get("is_hs"),
            # 实控人信息
            "act_name": raw_data.get("act_name"),
            "act_ent_type": raw_data.get("act_ent_type"),
            # 元数据
            "data_source": "tushare",
            "data_version": 1,
            "updated_at": datetime.now(UTC).replace(tzinfo=None),
        }

    def standardize_quotes(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化实时行情数据"""
        ts_code = raw_data.get("ts_code", "")
        symbol = ts_code.split(".")[0] if "." in ts_code else ts_code

        return {
            # 基础字段
            "code": symbol,
            "symbol": symbol,
            "full_symbol": ts_code,
            "market": self._determine_market(ts_code),
            # 价格数据
            "close": self._convert_to_float(raw_data.get("close")),
            "current_price": self._convert_to_float(raw_data.get("close")),
            "open": self._convert_to_float(raw_data.get("open")),
            "high": self._convert_to_float(raw_data.get("high")),
            "low": self._convert_to_float(raw_data.get("low")),
            "pre_close": self._convert_to_float(raw_data.get("pre_close")),
            # 变动数据
            "change": self._convert_to_float(raw_data.get("change")),
            "pct_chg": self._convert_to_float(raw_data.get("pct_chg")),
            # 成交数据。历史K线的单位转换在 historical path 完成；这里保持
            # quote 标准化为调用方传入的当前行情单位，兼容旧接口。
            "volume": self._convert_to_float(
                raw_data.get("volume", raw_data.get("vol"))
            ),
            "amount": self._convert_to_float(raw_data.get("amount")),
            # 财务指标
            "total_mv": self._convert_to_float(raw_data.get("total_mv")),
            "circ_mv": self._convert_to_float(raw_data.get("circ_mv")),
            "pe": self._convert_to_float(raw_data.get("pe")),
            "pb": self._convert_to_float(raw_data.get("pb")),
            "turnover_rate": self._convert_to_float(raw_data.get("turnover_rate")),
            # 时间数据
            "trade_date": self._format_date_output(raw_data.get("trade_date")),
            "timestamp": datetime.now(UTC).replace(tzinfo=None),
            # 元数据
            "data_source": "tushare",
            "data_version": 1,
            "updated_at": datetime.now(UTC).replace(tzinfo=None),
        }

    def _normalize_ts_code(self, symbol: str) -> str:
        """标准化为Tushare的ts_code格式"""
        if "." in symbol:
            return symbol  # 已经是ts_code格式

        # 6位数字代码，需要添加后缀
        if symbol.isdigit() and len(symbol) == 6:
            if symbol.startswith(("60", "68", "90")):
                return f"{symbol}.SH"  # 上交所
            else:
                return f"{symbol}.SZ"  # 深交所

        return symbol

    def _determine_market_info_from_ts_code(self, ts_code: str) -> Dict[str, Any]:
        """根据ts_code确定市场信息"""
        if ".SH" in ts_code:
            return {
                "market": "CN",
                "exchange": "SSE",
                "exchange_name": "上海证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
            }
        elif ".SZ" in ts_code:
            return {
                "market": "CN",
                "exchange": "SZSE",
                "exchange_name": "深圳证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
            }
        elif ".BJ" in ts_code:
            return {
                "market": "CN",
                "exchange": "BSE",
                "exchange_name": "北京证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
            }
        else:
            return {
                "market": "CN",
                "exchange": "UNKNOWN",
                "exchange_name": "未知交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
            }

    def _determine_market(self, ts_code: str) -> str:
        """确定市场代码"""
        market_info = self._determine_market_info_from_ts_code(ts_code)
        return market_info.get("market", "CN")

    def _format_date(self, date_value: Union[str, date]) -> str:
        """格式化日期为Tushare格式 (YYYYMMDD)"""
        if isinstance(date_value, str):
            return date_value.replace("-", "")
        elif isinstance(date_value, date):
            return date_value.strftime("%Y%m%d")
        else:
            return str(date_value).replace("-", "")
