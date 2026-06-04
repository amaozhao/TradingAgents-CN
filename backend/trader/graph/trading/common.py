# ruff: noqa: F401,F403,F405,F821
class _GraphMixin1:
    def _get_provider_kwargs(self) -> Dict[str, Any]:
        provider_kwargs: Dict[str, Any] = {}
        temperature = self.config.get("temperature")
        if temperature not in (None, ""):
            provider_kwargs["temperature"] = float(temperature)
        if self.config.get("google_thinking_level"):
            provider_kwargs["thinking_level"] = self.config["google_thinking_level"]
        if self.config.get("openai_reasoning_effort"):
            provider_kwargs["reasoning_effort"] = self.config["openai_reasoning_effort"]
        if self.config.get("anthropic_effort"):
            provider_kwargs["effort"] = self.config["anthropic_effort"]
        return provider_kwargs

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG

        # Keep both CN runtime settings and migrated upstream dataflow routing in sync.
        set_interface_config(self.config)
        set_dataflows_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs
        # 🔧 从配置中读取模型参数（优先使用用户配置，否则使用默认值）
        quick_config = self.config.get("quick_model_config", {})
        deep_config = self.config.get("deep_model_config", {})

        configured_temperature = self.config.get("temperature")
        default_temperature = (
            0.7
            if configured_temperature in (None, "")
            else float(configured_temperature)
        )

        # 读取快速模型参数
        quick_max_tokens = quick_config.get("max_tokens", 4000)
        quick_temperature = quick_config.get("temperature", default_temperature)
        quick_timeout = quick_config.get("timeout", 180)

        # 读取深度模型参数
        deep_max_tokens = deep_config.get("max_tokens", 4000)
        deep_temperature = deep_config.get("temperature", default_temperature)
        deep_timeout = deep_config.get("timeout", 180)

        # 🔧 检查是否为混合模式（快速模型和深度模型来自不同厂家）
        quick_provider = self.config.get("quick_provider")
        deep_provider = self.config.get("deep_provider")
        normalized_quick_provider = (
            normalize_provider_key(quick_provider) if quick_provider else None
        )
        normalized_deep_provider = (
            normalize_provider_key(deep_provider) if deep_provider else None
        )
        quick_backend_url = self.config.get("quick_backend_url")
        deep_backend_url = self.config.get("deep_backend_url")
        normalized_provider = normalize_provider_key(self.config["llm_provider"])

        if (
            normalized_quick_provider
            and normalized_deep_provider
            and normalized_quick_provider != normalized_deep_provider
        ):
            # 混合模式：快速模型和深度模型来自不同厂家
            logger.info("🔀 [混合模式] 检测到不同厂家的模型组合")
            logger.info(
                f"   快速模型: {self.config['quick_think_llm']} ({normalized_quick_provider})"
            )
            logger.info(
                f"   深度模型: {self.config['deep_think_llm']} ({normalized_deep_provider})"
            )

            # 使用统一的函数创建 LLM 实例
            self.quick_thinking_llm = create_llm_by_provider(
                provider=normalized_quick_provider,
                model=self.config["quick_think_llm"],
                backend_url=quick_backend_url or self.config.get("backend_url", ""),
                temperature=quick_temperature,
                max_tokens=quick_max_tokens,
                timeout=quick_timeout,
                api_key=self.config.get("quick_api_key"),  # 🔥 传递 API Key
                **_configured_provider_kwargs(self.config, normalized_quick_provider),
            )

            self.deep_thinking_llm = create_llm_by_provider(
                provider=normalized_deep_provider,
                model=self.config["deep_think_llm"],
                backend_url=deep_backend_url or self.config.get("backend_url", ""),
                temperature=deep_temperature,
                max_tokens=deep_max_tokens,
                timeout=deep_timeout,
                api_key=self.config.get("deep_api_key"),  # 🔥 传递 API Key
                **_configured_provider_kwargs(self.config, normalized_deep_provider),
            )

            logger.info("✅ [混合模式] LLM 实例创建成功")

        elif normalized_provider in {
            "openai",
            "siliconflow",
            "openrouter",
            "aihubmix",
            "ollama",
        }:
            provider = normalized_provider
            logger.info(
                f"🔧 [{provider}-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [{provider}-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            api_key = None
            if provider == "siliconflow":
                api_key = os.getenv("SILICONFLOW_API_KEY")
                if not api_key:
                    raise ValueError(
                        "使用SiliconFlow需要设置SILICONFLOW_API_KEY环境变量"
                    )
            elif provider == "openrouter":
                api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "使用OpenRouter需要设置OPENROUTER_API_KEY或OPENAI_API_KEY环境变量"
                    )
            elif provider == "aihubmix":
                api_key = os.getenv("AIHUBMIX_API_KEY")
                if not api_key:
                    raise ValueError("使用AiHubMix需要设置AIHUBMIX_API_KEY环境变量")

            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider=provider,
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=self.config["backend_url"],
                api_key=api_key,
            )
        elif normalized_provider in {"anthropic", "minimax-token-plan"}:
            logger.info(
                f"🔧 [Anthropic-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [Anthropic-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            anthropic_api_key = (
                self.config.get("quick_api_key")
                or self.config.get("deep_api_key")
                or os.getenv(env_key_for_provider(normalized_provider))
                or os.getenv("ANTHROPIC_API_KEY")
            )
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider=normalized_provider,
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=self.config.get("backend_url"),
                api_key=anthropic_api_key,
            )
        elif normalized_provider == "google":
            # 使用统一 llm_clients 入口，但底层仍返回 ChatGoogleOpenAI 兼容适配器
            logger.info(
                "🔧 使用统一 llm_clients 路径初始化 Google AI（保留工具调用兼容行为）"
            )

            # 🔥 优先使用数据库配置的 API Key，否则从环境变量读取
            google_api_key = (
                self.config.get("quick_api_key")
                or self.config.get("deep_api_key")
                or os.getenv("GOOGLE_API_KEY")
            )
            if not google_api_key:
                raise ValueError(
                    "使用Google AI需要在数据库中配置API Key或设置GOOGLE_API_KEY环境变量"
                )

            logger.info(
                f"🔑 [Google AI] API Key 来源: {'数据库配置' if self.config.get('quick_api_key') or self.config.get('deep_api_key') else '环境变量'}"
            )

            logger.info(
                f"🔧 [Google-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [Google-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            # 获取 backend_url（如果配置中有的话）
            backend_url = self.config.get("backend_url")
            if backend_url:
                logger.info(f"🔧 [Google AI] 使用配置的 backend_url: {backend_url}")
            else:
                logger.info("🔧 [Google AI] 未配置 backend_url，使用默认端点")

            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="google",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=backend_url if backend_url else None,
                api_key=google_api_key,
                quick_extra_kwargs={"transport": "rest"},
            )

            logger.info(
                "✅ [Google AI] 已启用优化的工具调用和内容格式处理并应用用户配置的模型参数"
            )
        elif normalized_provider == "qwen":
            logger.info("🔧 使用统一 llm_clients 路径初始化阿里百炼/通义千问")
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="qwen",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=self.config.get("backend_url"),
            )
            logger.info(
                "✅ [阿里百炼] 已通过 llm_clients 初始化成功并应用用户配置的模型参数"
            )
        elif normalized_provider == "deepseek":
            deepseek_api_key = (
                self.config.get("quick_api_key")
                or self.config.get("deep_api_key")
                or os.getenv("DEEPSEEK_API_KEY")
            )
            if not deepseek_api_key:
                raise ValueError("使用DeepSeek需要设置DEEPSEEK_API_KEY环境变量")

            deepseek_base_url = self.config.get("backend_url") or os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            )
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="deepseek",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=deepseek_base_url,
                api_key=deepseek_api_key,
            )
            logger.info(
                "✅ [DeepSeek] 已通过 llm_clients 初始化成功并应用用户配置的模型参数"
            )
        elif normalized_provider == "custom_openai":
            custom_api_key = os.getenv("CUSTOM_OPENAI_API_KEY")
            if not custom_api_key:
                raise ValueError(
                    "使用自定义OpenAI端点需要设置CUSTOM_OPENAI_API_KEY环境变量"
                )

            custom_base_url = self.config.get(
                "custom_openai_base_url", "https://api.openai.com/v1"
            )
            logger.info(f"🔧 [自定义OpenAI] 使用端点: {custom_base_url}")
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="custom_openai",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=custom_base_url,
                api_key=custom_api_key,
            )
            logger.info(
                "✅ [自定义OpenAI] 已通过 llm_clients 初始化成功并应用用户配置的模型参数"
            )
        elif normalized_provider == "qianfan":
            # 百度千帆（文心一言）配置 - 统一由适配器内部读取与校验 QIANFAN_API_KEY
            logger.info(
                f"🔧 [千帆-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [千帆-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="qianfan",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
            )
            logger.info("✅ [千帆] 文心一言适配器已配置成功并应用用户配置的模型参数")
        elif normalized_provider == "glm":
            # 🔥 优先使用数据库配置的 API Key，否则从环境变量读取
            zhipu_api_key = (
                self.config.get("quick_api_key")
                or self.config.get("deep_api_key")
                or os.getenv("ZHIPU_API_KEY")
            )
            logger.info(
                f"🔑 [智谱AI] API Key 来源: {'数据库配置' if self.config.get('quick_api_key') or self.config.get('deep_api_key') else '环境变量'}"
            )

            if not zhipu_api_key:
                raise ValueError(
                    "使用智谱AI需要在数据库中配置API Key或设置ZHIPU_API_KEY环境变量"
                )

            # 🔧 从配置中读取模型参数（优先使用用户配置，否则使用默认值）
            quick_config = self.config.get("quick_model_config", {})
            deep_config = self.config.get("deep_model_config", {})

            quick_max_tokens = quick_config.get("max_tokens", 4000)
            quick_temperature = quick_config.get("temperature", default_temperature)
            quick_timeout = quick_config.get("timeout", 180)

            deep_max_tokens = deep_config.get("max_tokens", 4000)
            deep_temperature = deep_config.get("temperature", default_temperature)
            deep_timeout = deep_config.get("timeout", 180)

            logger.info(
                f"🔧 [智谱AI-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [智谱AI-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            # 获取 backend_url（如果配置中有的话）
            backend_url = self.config.get("backend_url")
            if backend_url:
                logger.info(f"🔧 [智谱AI] 使用配置的 backend_url: {backend_url}")
            else:
                logger.info("🔧 [智谱AI] 未配置 backend_url，使用默认端点")
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="glm",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=backend_url,
                api_key=zhipu_api_key,
            )

            logger.info(
                "✅ [智谱AI] 已通过 llm_clients 初始化成功并应用用户配置的模型参数"
            )
        else:
            provider_name = self.config["llm_provider"]
            logger.info(f"🔧 使用统一 llm_clients 路径处理自定义厂家: {provider_name}")
            api_key_candidates = [
                f"{provider_name.upper()}_API_KEY",  # 例如: KYX_API_KEY
                f"{provider_name}_API_KEY",  # 例如: kyx_API_KEY
                "CUSTOM_OPENAI_API_KEY",  # 通用环境变量
            ]

            custom_api_key = None
            for env_var in api_key_candidates:
                custom_api_key = os.getenv(env_var)
                if custom_api_key:
                    logger.info(f"✅ 从环境变量 {env_var} 获取到 API Key")
                    break

            if not custom_api_key:
                raise ValueError(
                    f"使用自定义厂家 {provider_name} 需要设置以下环境变量之一:\n"
                    f"  - {provider_name.upper()}_API_KEY\n"
                    f"  - CUSTOM_OPENAI_API_KEY"
                )

            # 获取 backend_url（从配置中获取）
            backend_url = self.config.get("backend_url")
            if not backend_url:
                raise ValueError(
                    f"使用自定义厂家 {provider_name} 需要在数据库配置中设置 default_base_url"
                )

            logger.info(f"🔧 [自定义厂家 {provider_name}] 使用端点: {backend_url}")

            # 🔧 从配置中读取模型参数
            quick_config = self.config.get("quick_model_config", {})
            deep_config = self.config.get("deep_model_config", {})

            quick_max_tokens = quick_config.get("max_tokens", 4000)
            quick_temperature = quick_config.get("temperature", default_temperature)
            quick_timeout = quick_config.get("timeout", 180)

            deep_max_tokens = deep_config.get("max_tokens", 4000)
            deep_temperature = deep_config.get("temperature", default_temperature)
            deep_timeout = deep_config.get("timeout", 180)

            logger.info(
                f"🔧 [{provider_name}-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [{provider_name}-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="custom_openai",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=backend_url,
                api_key=custom_api_key,
            )

            logger.info(
                f"✅ [自定义厂家 {provider_name}] 已配置自定义端点并应用用户配置的模型参数"
            )

        self.toolkit = Toolkit(config=self.config)

        # Preserve existing CN role memories; TradingMemoryLog is additive.
        memory_enabled = self.config.get("memory_enabled", True)
        if memory_enabled:
            self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
            self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
            self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
            self.invest_judge_memory = FinancialSituationMemory(
                "invest_judge_memory", self.config
            )
            self.risk_manager_memory = FinancialSituationMemory(
                "risk_manager_memory", self.config
            )
        else:
            self.bull_memory = None
            self.bear_memory = None
            self.trader_memory = None
            self.invest_judge_memory = None
            self.risk_manager_memory = None

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        # 🔥 [修复] 从配置中读取辩论轮次参数
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config.get("max_debate_rounds", 1),
            max_risk_discuss_rounds=self.config.get("max_risk_discuss_rounds", 1),
        )
        logger.info("🔧 [ConditionalLogic] 初始化完成:")
        logger.info(
            f"   - max_debate_rounds: {self.conditional_logic.max_debate_rounds}"
        )
        logger.info(
            f"   - max_risk_discuss_rounds: {self.conditional_logic.max_risk_discuss_rounds}"
        )

        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.toolkit,
            self.tool_nodes,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.risk_manager_memory,
            self.conditional_logic,
            self.config,
            getattr(self, "react_llm", None),
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)
        self.memory_log = TradingMemoryLog(self.config)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.workflow = self.graph_setup.setup_graph(selected_analysts)
        self.graph = self.workflow.compile()
        self._checkpointer_ctx = None

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources.

        注意：ToolNode 包含所有可能的工具，但 LLM 只会调用它绑定的工具。
        ToolNode 的作用是执行 LLM 生成的 tool_calls，而不是限制 LLM 可以调用哪些工具。
        """
        return {
            "market": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_market_data_unified,
                    # 在线工具（备用）
                    self.toolkit.get_yfin_data_online,
                    self.toolkit.get_stockstats_indicators_report_online,
                    # 离线工具（备用）
                    self.toolkit.get_yfin_data,
                    self.toolkit.get_stockstats_indicators_report,
                ]
            ),
            "social": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_sentiment_unified,
                    # 在线工具（备用）
                    self.toolkit.get_stock_news_openai,
                    # 离线工具（备用）
                    self.toolkit.get_reddit_stock_info,
                ]
            ),
            "news": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_news_unified,
                    # 在线工具（备用）
                    self.toolkit.get_global_news_openai,
                    self.toolkit.get_google_news,
                    # 离线工具（备用）
                    self.toolkit.get_finnhub_news,
                    self.toolkit.get_reddit_news,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_fundamentals_unified,
                    # 离线工具（备用）
                    self.toolkit.get_finnhub_company_insider_sentiment,
                    self.toolkit.get_finnhub_company_insider_transactions,
                    self.toolkit.get_simfin_balance_sheet,
                    self.toolkit.get_simfin_cashflow,
                    self.toolkit.get_simfin_income_stmt,
                    # 中国市场工具（备用）
                    self.toolkit.get_china_stock_data,
                    self.toolkit.get_china_fundamentals,
                ]
            ),
        }

    def resolve_instrument_context(self, ticker: str, asset_type: str = "stock") -> str:
        identity = resolve_instrument_identity(ticker)
        return build_instrument_context(ticker, asset_type, identity)

    def _resolve_benchmark(self, ticker: str) -> str:
        explicit = self.config.get("benchmark_ticker")
        if explicit:
            return explicit
        benchmark_map = self.config.get("benchmark_map", {})
        ticker_upper = str(ticker).upper()
        for suffix, benchmark in benchmark_map.items():
            if suffix and ticker_upper.endswith(str(suffix).upper()):
                return benchmark
        return benchmark_map.get("", "SPY")

    def _fetch_returns(
        self,
        ticker: str,
        trade_date: str,
        holding_days: int = 5,
        benchmark: str = "SPY",
    ) -> Tuple[Optional[float], Optional[float], Optional[int]]:
        try:
            yf = importlib.import_module("yfinance")

            start = datetime.strptime(str(trade_date), "%Y-%m-%d")
            end = start + timedelta(days=holding_days + 7)
            end_str = end.strftime("%Y-%m-%d")
            stock = yf.Ticker(ticker).history(start=str(trade_date), end=end_str)
            bench = yf.Ticker(benchmark).history(start=str(trade_date), end=end_str)
            if len(stock) < 2 or len(bench) < 2:
                return None, None, None
            actual_days = min(holding_days, len(stock) - 1, len(bench) - 1)
            raw = float(
                (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0])
                / stock["Close"].iloc[0]
            )
            bench_ret = float(
                (bench["Close"].iloc[actual_days] - bench["Close"].iloc[0])
                / bench["Close"].iloc[0]
            )
            return raw, raw - bench_ret, actual_days
        except Exception as exc:
            logger.warning(
                "Could not resolve outcome for %s on %s vs %s: %s",
                ticker,
                trade_date,
                benchmark,
                exc,
            )
            return None, None, None

    def _resolve_pending_entries(self, ticker: str) -> None:
        pending = [
            e for e in self.memory_log.get_pending_entries() if e["ticker"] == ticker
        ]
        if not pending:
            return
        benchmark = self._resolve_benchmark(ticker)
        updates = []
        for entry in pending:
            raw, alpha, days = self._fetch_returns(
                ticker, entry["date"], benchmark=benchmark
            )
            if raw is None or alpha is None:
                continue
            reflection = self.reflector.reflect_on_final_decision(
                final_decision=entry.get("decision", ""),
                raw_return=raw,
                alpha_return=alpha,
                benchmark_name=benchmark,
            )
            updates.append(
                {
                    "ticker": ticker,
                    "trade_date": entry["date"],
                    "raw_return": raw,
                    "alpha_return": alpha,
                    "holding_days": days,
                    "reflection": reflection,
                }
            )
        if updates:
            self.memory_log.batch_update_with_outcomes(updates)

    def _run_graph(self, company_name, trade_date, asset_type: str = "stock"):
        self._resolve_pending_entries(company_name)
        past_context = self.memory_log.get_past_context(company_name)
        instrument_context = self.resolve_instrument_context(company_name, asset_type)
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            asset_type=asset_type,
            past_context=past_context,
            instrument_context=instrument_context,
        )
        args = self.propagator.get_graph_args()
        if self.config.get("checkpoint_enabled"):
            args.setdefault("config", {}).setdefault("configurable", {})[
                "thread_id"
            ] = thread_id(company_name, str(trade_date))
        final_state = cast(Any, self.graph).invoke(init_agent_state, **args)
        self.curr_state = final_state
        self._log_state(trade_date, final_state)
        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=str(trade_date),
            final_trade_decision=final_state["final_trade_decision"],
        )
        if self.config.get("checkpoint_enabled"):
            clear_checkpoint(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )
        return final_state, self.process_signal(
            final_state["final_trade_decision"], company_name
        )
