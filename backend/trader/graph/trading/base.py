# ruff: noqa: F401,F403,F405,F821
class _GraphMixin2:
    def propagate(
        self,
        company_name,
        trade_date,
        progress_callback=None,
        task_id=None,
        asset_type: str = "stock",
    ):
        """Run the trading agents graph for a company on a specific date.

        Args:
            company_name: Company name or stock symbol
            trade_date: Date for analysis
            progress_callback: Optional callback function for progress updates
            task_id: Optional task ID for tracking performance data
        """

        # 添加详细的接收日志
        logger.debug(
            "🔍 [GRAPH DEBUG] ===== TradingAgentsGraph.propagate 接收参数 ====="
        )
        logger.debug(
            f"🔍 [GRAPH DEBUG] 接收到的company_name: '{company_name}' (类型: {type(company_name)})"
        )
        logger.debug(
            f"🔍 [GRAPH DEBUG] 接收到的trade_date: '{trade_date}' (类型: {type(trade_date)})"
        )
        logger.debug(f"🔍 [GRAPH DEBUG] 接收到的task_id: '{task_id}'")

        if not isinstance(self, TradingAgentsGraph) and callable(
            getattr(self, "_run_graph", None)
        ):
            return self._run_graph(company_name, trade_date, asset_type=asset_type)

        self.ticker = company_name
        logger.debug(f"🔍 [GRAPH DEBUG] 设置self.ticker: '{self.ticker}'")

        self._resolve_pending_entries(company_name)
        past_context = self.memory_log.get_past_context(company_name)
        instrument_context = self.resolve_instrument_context(company_name, asset_type)

        if self.config.get("checkpoint_enabled"):
            self._checkpointer_ctx = get_checkpointer(
                self.config["data_cache_dir"], company_name
            )
            saver = self._checkpointer_ctx.__enter__()
            self.graph = self.workflow.compile(checkpointer=saver)
            step = checkpoint_step(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )
            if step is not None:
                logger.info(
                    f"🔄 [Checkpoint] 从步骤 {step} 恢复: {company_name} {trade_date}"
                )
            else:
                logger.info(
                    f"🆕 [Checkpoint] 开始新的分析: {company_name} {trade_date}"
                )

        # Initialize state
        logger.debug(
            f"🔍 [GRAPH DEBUG] 创建初始状态，传递参数: company_name='{company_name}', trade_date='{trade_date}'"
        )
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            asset_type=asset_type,
            past_context=past_context,
            instrument_context=instrument_context,
        )
        logger.debug(
            f"🔍 [GRAPH DEBUG] 初始状态中的company_of_interest: '{init_agent_state.get('company_of_interest', 'NOT_FOUND')}'"
        )
        logger.debug(
            f"🔍 [GRAPH DEBUG] 初始状态中的trade_date: '{init_agent_state.get('trade_date', 'NOT_FOUND')}'"
        )

        # 初始化计时器
        node_timings = {}  # 记录每个节点的执行时间
        total_start_time = time.time()  # 总体开始时间
        current_node_start = None  # 当前节点开始时间
        current_node_name = None  # 当前节点名称

        # 保存task_id用于后续保存性能数据
        self._current_task_id = task_id

        # 根据是否有进度回调选择不同的stream_mode
        args = self.propagator.get_graph_args(
            use_progress_callback=bool(progress_callback)
        )
        if self.config.get("checkpoint_enabled"):
            args.setdefault("config", {}).setdefault("configurable", {})[
                "thread_id"
            ] = thread_id(company_name, str(trade_date))

        try:
            if self.debug:
                trace = []
                final_state = None
                for chunk in cast(Any, self.graph).stream(init_agent_state, **args):
                    for node_name in chunk.keys():
                        if not node_name.startswith("__"):
                            if current_node_name and current_node_start:
                                elapsed = time.time() - current_node_start
                                node_timings[current_node_name] = elapsed
                                logger.info(
                                    f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒"
                                )

                            current_node_name = node_name
                            current_node_start = time.time()
                            break

                    if progress_callback and args.get("stream_mode") == "updates":
                        self._send_progress_update(chunk, progress_callback)
                        if final_state is None:
                            final_state = init_agent_state.copy()
                        for node_name, node_update in chunk.items():
                            if not node_name.startswith("__"):
                                final_state.update(node_update)
                    else:
                        if len(chunk.get("messages", [])) > 0:
                            chunk["messages"][-1].pretty_print()
                        trace.append(chunk)
                        final_state = chunk

                if trace:
                    final_state = trace[-1]
            elif progress_callback:
                final_state = None
                for chunk in cast(Any, self.graph).stream(init_agent_state, **args):
                    for node_name in chunk.keys():
                        if not node_name.startswith("__"):
                            if current_node_name and current_node_start:
                                elapsed = time.time() - current_node_start
                                node_timings[current_node_name] = elapsed
                                logger.info(
                                    f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒"
                                )
                                logger.info(
                                    f"🔍 [TIMING] 节点切换: {current_node_name} → {node_name}"
                                )

                            current_node_name = node_name
                            current_node_start = time.time()
                            logger.info(f"🔍 [TIMING] 开始计时: {node_name}")
                            break

                    self._send_progress_update(chunk, progress_callback)
                    if final_state is None:
                        final_state = init_agent_state.copy()
                    for node_name, node_update in chunk.items():
                        if not node_name.startswith("__"):
                            final_state.update(node_update)
            else:
                logger.info("⏱️ 使用 invoke 模式执行分析（无进度回调）")
                final_state = None
                for chunk in cast(Any, self.graph).stream(init_agent_state, **args):
                    if isinstance(chunk, dict):
                        final_state = chunk
                    else:
                        logger.warning(
                            "⚠️ LangGraph values stream 返回非字典状态: %s",
                            type(chunk),
                        )
        finally:
            if self._checkpointer_ctx is not None:
                self._checkpointer_ctx.__exit__(None, None, None)
                self._checkpointer_ctx = None
                self.graph = self.workflow.compile()

        # 记录最后一个节点的时间
        if current_node_name and current_node_start:
            elapsed = time.time() - current_node_start
            node_timings[current_node_name] = elapsed
            logger.info(f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒")

        # 计算总时间
        total_elapsed = time.time() - total_start_time

        # 调试日志
        logger.info(f"🔍 [TIMING DEBUG] 节点计时数量: {len(node_timings)}")
        logger.info(f"🔍 [TIMING DEBUG] 总耗时: {total_elapsed:.2f}秒")
        logger.info(f"🔍 [TIMING DEBUG] 节点列表: {list(node_timings.keys())}")

        # 打印详细的时间统计
        logger.info("🔍 [TIMING DEBUG] 准备调用 _print_timing_summary")
        self._print_timing_summary(node_timings, total_elapsed)
        logger.info("🔍 [TIMING DEBUG] _print_timing_summary 调用完成")

        if final_state is None:
            raise RuntimeError("图执行未产生最终状态")

        # 构建性能数据
        performance_data = self._build_performance_data(node_timings, total_elapsed)

        # 将性能数据添加到状态中
        final_state["performance_metrics"] = performance_data

        # Store current state for reflection
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=str(trade_date),
            final_trade_decision=final_state["final_trade_decision"],
        )

        # 获取模型信息
        model_info = ""
        try:
            if hasattr(self.deep_thinking_llm, "model_name"):
                model_info = f"{self.deep_thinking_llm.__class__.__name__}:{self.deep_thinking_llm.model_name}"
            else:
                model_info = self.deep_thinking_llm.__class__.__name__
        except Exception:
            model_info = "Unknown"

        # 处理决策并添加模型信息
        decision = self.process_signal(
            final_state["final_trade_decision"], company_name
        )
        decision["model_info"] = model_info

        # Return decision and processed signal
        return final_state, decision

    def _send_progress_update(self, chunk, progress_callback):
        """发送进度更新到回调函数

        LangGraph stream 返回的 chunk 格式：{node_name: {...}}
        节点名称示例：
        - "Market Analyst", "Fundamentals Analyst", "News Analyst", "Social Analyst"
        - "tools_market", "tools_fundamentals", "tools_news", "tools_social"
        - "Msg Clear Market", "Msg Clear Fundamentals", etc.
        - "Bull Researcher", "Bear Researcher", "Research Manager"
        - "Trader"
        - "Risky Analyst", "Safe Analyst", "Neutral Analyst", "Risk Judge", "Portfolio Manager"
        """
        try:
            # 从chunk中提取当前执行的节点信息
            if not isinstance(chunk, dict):
                return

            # 获取第一个非特殊键作为节点名
            node_name = None
            for key in chunk.keys():
                if not key.startswith("__"):
                    node_name = key
                    break

            if not node_name:
                return

            logger.info(f"🔍 [Progress] 节点名称: {node_name}")

            # 检查是否为结束节点
            if "__end__" in chunk:
                logger.info("📊 [Progress] 检测到__end__节点")
                progress_callback("📊 生成报告")
                return

            # 节点名称映射表（匹配 LangGraph 实际节点名）
            node_mapping = {
                # 分析师节点
                "Market Analyst": "📊 市场分析师",
                "Fundamentals Analyst": "💼 基本面分析师",
                "News Analyst": "📰 新闻分析师",
                "Social Analyst": "💬 社交媒体分析师",
                # 工具节点（不发送进度更新，避免重复）
                "tools_market": None,
                "tools_fundamentals": None,
                "tools_news": None,
                "tools_social": None,
                # 消息清理节点（不发送进度更新）
                "Msg Clear Market": None,
                "Msg Clear Fundamentals": None,
                "Msg Clear News": None,
                "Msg Clear Social": None,
                # 研究员节点
                "Bull Researcher": "🐂 看涨研究员",
                "Bear Researcher": "🐻 看跌研究员",
                "Research Manager": "👔 研究经理",
                # 交易员节点
                "Trader": "💼 交易员决策",
                # 风险评估节点
                "Risky Analyst": "🔥 激进风险评估",
                "Safe Analyst": "🛡️ 保守风险评估",
                "Neutral Analyst": "⚖️ 中性风险评估",
                "Risk Judge": "🎯 风险经理",
                "Portfolio Manager": "🎯 投资组合经理",
            }

            # 查找映射的消息
            message = node_mapping.get(node_name)

            if message is None:
                # None 表示跳过（工具节点、消息清理节点）
                logger.debug(f"⏭️ [Progress] 跳过节点: {node_name}")
                return

            if message:
                # 发送进度更新
                logger.info(f"📤 [Progress] 发送进度更新: {message}")
                progress_callback(message)
            else:
                # 未知节点，使用节点名称
                logger.warning(f"⚠️ [Progress] 未知节点: {node_name}")
                progress_callback(f"🔍 {node_name}")

        except Exception as e:
            logger.error(f"❌ 进度更新失败: {e}", exc_info=True)

    def _build_performance_data(
        self, node_timings: Dict[str, float], total_elapsed: float
    ) -> Dict[str, Any]:
        """构建性能数据结构

        Args:
            node_timings: 每个节点的执行时间字典
            total_elapsed: 总执行时间

        Returns:
            性能数据字典
        """
        # 节点分类（注意：风险管理节点要先于分析师节点判断，因为它们也包含'Analyst'）
        analyst_nodes = {}
        tool_nodes = {}
        msg_clear_nodes = {}
        research_nodes = {}
        trader_nodes = {}
        risk_nodes = {}
        other_nodes = {}

        for node_name, elapsed in node_timings.items():
            # 优先匹配风险管理团队（因为它们也包含'Analyst'）
            if (
                "Risky" in node_name
                or "Safe" in node_name
                or "Neutral" in node_name
                or "Risk Judge" in node_name
                or "Portfolio Manager" in node_name
            ):
                risk_nodes[node_name] = elapsed
            # 然后匹配分析师团队
            elif "Analyst" in node_name:
                analyst_nodes[node_name] = elapsed
            # 工具节点
            elif node_name.startswith("tools_"):
                tool_nodes[node_name] = elapsed
            # 消息清理节点
            elif node_name.startswith("Msg Clear"):
                msg_clear_nodes[node_name] = elapsed
            # 研究团队
            elif "Researcher" in node_name or "Research Manager" in node_name:
                research_nodes[node_name] = elapsed
            # 交易团队
            elif "Trader" in node_name:
                trader_nodes[node_name] = elapsed
            # 其他节点
            else:
                other_nodes[node_name] = elapsed

        # 计算统计数据
        slowest_node = (
            max(node_timings.items(), key=lambda x: x[1]) if node_timings else (None, 0)
        )
        fastest_node = (
            min(node_timings.items(), key=lambda x: x[1]) if node_timings else (None, 0)
        )
        avg_time = sum(node_timings.values()) / len(node_timings) if node_timings else 0

        return {
            "total_time": round(total_elapsed, 2),
            "total_time_minutes": round(total_elapsed / 60, 2),
            "node_count": len(node_timings),
            "average_node_time": round(avg_time, 2),
            "slowest_node": {"name": slowest_node[0], "time": round(slowest_node[1], 2)}
            if slowest_node[0]
            else None,
            "fastest_node": {"name": fastest_node[0], "time": round(fastest_node[1], 2)}
            if fastest_node[0]
            else None,
            "node_timings": {k: round(v, 2) for k, v in node_timings.items()},
            "category_timings": {
                "analyst_team": {
                    "nodes": {k: round(v, 2) for k, v in analyst_nodes.items()},
                    "total": round(sum(analyst_nodes.values()), 2),
                    "percentage": round(
                        sum(analyst_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "tool_calls": {
                    "nodes": {k: round(v, 2) for k, v in tool_nodes.items()},
                    "total": round(sum(tool_nodes.values()), 2),
                    "percentage": round(
                        sum(tool_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "message_clearing": {
                    "nodes": {k: round(v, 2) for k, v in msg_clear_nodes.items()},
                    "total": round(sum(msg_clear_nodes.values()), 2),
                    "percentage": round(
                        sum(msg_clear_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "research_team": {
                    "nodes": {k: round(v, 2) for k, v in research_nodes.items()},
                    "total": round(sum(research_nodes.values()), 2),
                    "percentage": round(
                        sum(research_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "trader_team": {
                    "nodes": {k: round(v, 2) for k, v in trader_nodes.items()},
                    "total": round(sum(trader_nodes.values()), 2),
                    "percentage": round(
                        sum(trader_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "risk_management_team": {
                    "nodes": {k: round(v, 2) for k, v in risk_nodes.items()},
                    "total": round(sum(risk_nodes.values()), 2),
                    "percentage": round(
                        sum(risk_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "other": {
                    "nodes": {k: round(v, 2) for k, v in other_nodes.items()},
                    "total": round(sum(other_nodes.values()), 2),
                    "percentage": round(
                        sum(other_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
            },
            "llm_config": {
                "provider": self.config.get("llm_provider", "unknown"),
                "deep_think_model": self.config.get("deep_think_llm", "unknown"),
                "quick_think_model": self.config.get("quick_think_llm", "unknown"),
            },
        }

    def _print_timing_summary(
        self, node_timings: Dict[str, float], total_elapsed: float
    ):
        """打印详细的时间统计报告

        Args:
            node_timings: 每个节点的执行时间字典
            total_elapsed: 总执行时间
        """
        logger.info("🔍 [_print_timing_summary] 方法被调用")
        logger.info(
            "🔍 [_print_timing_summary] node_timings 数量: " + str(len(node_timings))
        )
        logger.info("🔍 [_print_timing_summary] total_elapsed: " + str(total_elapsed))

        logger.info("=" * 80)
        logger.info("⏱️  分析性能统计报告")
        logger.info("=" * 80)

        # 节点分类（注意：风险管理节点要先于分析师节点判断，因为它们也包含'Analyst'）
        analyst_nodes = []
        tool_nodes = []
        msg_clear_nodes = []
        research_nodes = []
        trader_nodes = []
        risk_nodes = []
        other_nodes = []

        for node_name, elapsed in node_timings.items():
            # 优先匹配风险管理团队（因为它们也包含'Analyst'）
            if (
                "Risky" in node_name
                or "Safe" in node_name
                or "Neutral" in node_name
                or "Risk Judge" in node_name
                or "Portfolio Manager" in node_name
            ):
                risk_nodes.append((node_name, elapsed))
            # 然后匹配分析师团队
            elif "Analyst" in node_name:
                analyst_nodes.append((node_name, elapsed))
            # 工具节点
            elif node_name.startswith("tools_"):
                tool_nodes.append((node_name, elapsed))
            # 消息清理节点
            elif node_name.startswith("Msg Clear"):
                msg_clear_nodes.append((node_name, elapsed))
            # 研究团队
            elif "Researcher" in node_name or "Research Manager" in node_name:
                research_nodes.append((node_name, elapsed))
            # 交易团队
            elif "Trader" in node_name:
                trader_nodes.append((node_name, elapsed))
            # 其他节点
            else:
                other_nodes.append((node_name, elapsed))

        # 打印分类统计
        def print_category(title: str, nodes: List[Tuple[str, float]]):
            if not nodes:
                return
            logger.info(f"\n📊 {title}")
            logger.info("-" * 80)
            total_category_time = sum(t for _, t in nodes)
            for node_name, elapsed in sorted(nodes, key=lambda x: x[1], reverse=True):
                percentage = (elapsed / total_elapsed * 100) if total_elapsed > 0 else 0
                logger.info(
                    f"  • {node_name:40s} {elapsed:8.2f}秒  ({percentage:5.1f}%)"
                )
            logger.info(
                f"  {'小计':40s} {total_category_time:8.2f}秒  ({total_category_time / total_elapsed * 100:5.1f}%)"
            )

        print_category("分析师团队", analyst_nodes)
        print_category("工具调用", tool_nodes)
        print_category("消息清理", msg_clear_nodes)
        print_category("研究团队", research_nodes)
        print_category("交易团队", trader_nodes)
        print_category("风险管理团队", risk_nodes)
        print_category("其他节点", other_nodes)

        # 打印总体统计
        logger.info("\n" + "=" * 80)
        logger.info(
            f"🎯 总执行时间: {total_elapsed:.2f}秒 ({total_elapsed / 60:.2f}分钟)"
        )
        logger.info(f"📈 节点总数: {len(node_timings)}")
        if node_timings:
            avg_time = sum(node_timings.values()) / len(node_timings)
            logger.info(f"⏱️  平均节点耗时: {avg_time:.2f}秒")
            slowest_node = max(node_timings.items(), key=lambda x: x[1])
            logger.info(f"🐌 最慢节点: {slowest_node[0]} ({slowest_node[1]:.2f}秒)")
            fastest_node = min(node_timings.items(), key=lambda x: x[1])
            logger.info(f"⚡ 最快节点: {fastest_node[0]} ({fastest_node[1]:.2f}秒)")

        # 打印LLM配置信息
        logger.info("\n🤖 LLM配置:")
        logger.info(f"  • 提供商: {self.config.get('llm_provider', 'unknown')}")
        logger.info(f"  • 深度思考模型: {self.config.get('deep_think_llm', 'unknown')}")
        logger.info(
            f"  • 快速思考模型: {self.config.get('quick_think_llm', 'unknown')}"
        )
        logger.info("=" * 80)

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "risky_history": final_state["risk_debate_state"]["risky_history"],
                "safe_history": final_state["risk_debate_state"]["safe_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file
        safe_ticker = safe_ticker_component(str(self.ticker))
        directory = Path("eval_results") / safe_ticker / "TradingAgentsStrategy_logs"
        directory.mkdir(parents=True, exist_ok=True)

        with open(directory / "full_states_log.json", "w", encoding="utf-8") as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update existing CN role memories."""
        if self.bull_memory is not None:
            self.reflector.reflect_bull_researcher(
                self.curr_state, returns_losses, self.bull_memory
            )
        if self.bear_memory is not None:
            self.reflector.reflect_bear_researcher(
                self.curr_state, returns_losses, self.bear_memory
            )
        if self.trader_memory is not None:
            self.reflector.reflect_trader(
                self.curr_state, returns_losses, self.trader_memory
            )
        if self.invest_judge_memory is not None:
            self.reflector.reflect_invest_judge(
                self.curr_state, returns_losses, self.invest_judge_memory
            )
        if self.risk_manager_memory is not None:
            self.reflector.reflect_risk_manager(
                self.curr_state, returns_losses, self.risk_manager_memory
            )

    def process_signal(self, full_signal, stock_symbol=None):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal, stock_symbol)
