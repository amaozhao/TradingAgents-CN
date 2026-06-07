# ruff: noqa: F401,F403,F405,F821
def run_analysis():
    time = importlib.import_module("time")
    start_time = time.time()  # 记录开始时间

    # First get all user selections
    selections = get_user_selections()

    # Check API keys before proceeding
    if not check_api_keys(selections["llm_provider"]):
        ui.show_error("分析终止 | Analysis terminated")
        return

    # 显示分析开始信息
    ui.show_step_header(1, "准备分析环境 | Preparing Analysis Environment")
    ui.show_progress(f"正在分析股票: {selections['ticker']}")
    ui.show_progress(f"分析日期: {selections['analysis_date']}")
    ui.show_progress(
        f"选择的分析师: {', '.join(analyst.value for analyst in selections['analysts'])}"
    )

    # Create config with selected research depth
    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = selections["research_depth"]
    config["max_risk_discuss_rounds"] = selections["research_depth"]
    config["quick_think_llm"] = selections["shallow_thinker"]
    config["deep_think_llm"] = selections["deep_thinker"]
    config["backend_url"] = selections["backend_url"]
    config["output_language"] = selections.get(
        "output_language", config.get("output_language")
    )
    config["google_thinking_level"] = selections.get(
        "google_thinking_level", config.get("google_thinking_level")
    )
    config["openai_reasoning_effort"] = selections.get(
        "openai_reasoning_effort", config.get("openai_reasoning_effort")
    )
    config["anthropic_effort"] = selections.get(
        "anthropic_effort", config.get("anthropic_effort")
    )
    selected_llm_provider_name = selections["llm_provider"]
    config["llm_provider"] = selected_llm_provider_name

    if selected_llm_provider_name == "custom_openai":
        custom_url = settings.CUSTOM_OPENAI_BASE_URL or selections["backend_url"]
        config["custom_openai_base_url"] = custom_url
        config["backend_url"] = custom_url

    # Initialize the graph
    ui.show_progress("正在初始化分析系统...")
    try:
        graph = TradingAgentsGraph(
            [analyst.value for analyst in selections["analysts"]],
            config=config,
            debug=True,
        )
        ui.show_success("分析系统初始化完成")
    except ImportError as e:
        ui.show_error(f"模块导入失败 | Module import failed: {str(e)}")
        ui.show_warning("💡 请检查依赖安装 | Please check dependencies installation")
        return
    except ValueError as e:
        ui.show_error(f"配置参数错误 | Configuration error: {str(e)}")
        ui.show_warning("💡 请检查配置参数 | Please check configuration parameters")
        return
    except Exception as e:
        ui.show_error(f"初始化失败 | Initialization failed: {str(e)}")
        ui.show_warning("💡 请检查API密钥配置 | Please check API key configuration")
        return

    # Create result directory
    results_dir = (
        Path(config["results_dir"]) / selections["ticker"] / selections["analysis_date"]
    )
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir = results_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    log_file = results_dir / "message_tool.log"
    log_file.touch(exist_ok=True)

    def save_message_decorator(obj, func_name):
        func = getattr(obj, func_name)

        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, message_type, content = obj.messages[-1]
            content = content.replace("\n", " ")  # Replace newlines with spaces
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} [{message_type}] {content}\n")

        return wrapper

    def save_tool_call_decorator(obj, func_name):
        func = getattr(obj, func_name)

        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, tool_name, args = obj.tool_calls[-1]
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} [Tool Call] {tool_name}({args_str})\n")

        return wrapper

    def save_report_section_decorator(obj, func_name):
        func = getattr(obj, func_name)

        @wraps(func)
        def wrapper(section_name, content):
            func(section_name, content)
            if (
                section_name in obj.report_sections
                and obj.report_sections[section_name] is not None
            ):
                content = obj.report_sections[section_name]
                if content:
                    file_name = f"{section_name}.md"
                    with open(report_dir / file_name, "w", encoding="utf-8") as f:
                        f.write(content)

        return wrapper

    message_buffer.add_message = save_message_decorator(message_buffer, "add_message")
    message_buffer.add_tool_call = save_tool_call_decorator(
        message_buffer, "add_tool_call"
    )
    message_buffer.update_report_section = save_report_section_decorator(
        message_buffer, "update_report_section"
    )

    # Now start the display layout
    layout = create_layout()

    with Live(layout, refresh_per_second=DEFAULT_REFRESH_RATE):
        # Initial display
        update_display(layout)

        # Add initial messages
        message_buffer.add_message("System", f"Selected ticker: {selections['ticker']}")
        message_buffer.add_message(
            "System", f"Analysis date: {selections['analysis_date']}"
        )
        message_buffer.add_message(
            "System",
            f"Selected analysts: {', '.join(analyst.value for analyst in selections['analysts'])}",
        )
        update_display(layout)

        # Reset agent statuses
        for agent in message_buffer.agent_status:
            message_buffer.update_agent_status(agent, "pending")

        # Reset report sections
        for section in message_buffer.report_sections:
            message_buffer.report_sections[section] = None
        message_buffer.current_report = None
        message_buffer.final_report = None

        # Update agent status to in_progress for the first analyst
        first_analyst = f"{selections['analysts'][0].value.capitalize()} Analyst"
        message_buffer.update_agent_status(first_analyst, "in_progress")
        update_display(layout)

        # Create spinner text
        spinner_text = (
            f"Analyzing {selections['ticker']} on {selections['analysis_date']}..."
        )
        update_display(layout, spinner_text)

        # 显示数据预获取和验证阶段
        ui.show_step_header(2, "数据验证阶段 | Data Validation Phase")
        ui.show_progress("🔍 验证股票代码并预获取数据...")

        try:
            prepare_stock_data = getattr(
                importlib.import_module("trader.utils.validation"), "prepare_stock_data"
            )

            # 获取选定市场的数据源类型
            for choice, market in {
                "1": {"data_source": "yahoo_finance"},
                "2": {"data_source": "china_stock"},
                "3": {"data_source": "yahoo_finance"},
            }.items():
                # 这里需要从用户选择中获取市场类型，暂时使用代码推断
                pass

            # 根据股票代码推断市场类型
            if re.match(r"^\d{6}$", selections["ticker"]):
                market_type = "A股"
            elif ".HK" in selections["ticker"].upper():
                market_type = "港股"
            else:
                market_type = "美股"

            # 预获取股票数据（默认30天历史数据）
            preparation_result = prepare_stock_data(
                stock_code=selections["ticker"],
                market_type=market_type,
                period_days=30,
                analysis_date=selections["analysis_date"],
            )

            if not preparation_result.is_valid:
                ui.show_error(
                    f"❌ 股票数据验证失败: {preparation_result.error_message}"
                )
                ui.show_warning(f"💡 建议: {preparation_result.suggestion}")
                logger.error(f"股票数据验证失败: {preparation_result.error_message}")
                return

            # 数据预获取成功
            ui.show_success(
                f"✅ 数据准备完成: {preparation_result.stock_name} ({preparation_result.market_type})"
            )
            ui.show_user_message(
                f"📊 缓存状态: {preparation_result.cache_status}", "dim"
            )
            logger.info(f"股票数据预获取成功: {preparation_result.stock_name}")

        except Exception as e:
            ui.show_error(f"❌ 数据预获取过程中发生错误: {str(e)}")
            ui.show_warning("💡 请检查网络连接或稍后重试")
            logger.error(f"数据预获取异常: {str(e)}")
            return

        # 显示数据获取阶段
        ui.show_step_header(3, "数据获取阶段 | Data Collection Phase")
        ui.show_progress("正在获取股票基本信息...")

        # Initialize state and get graph args
        init_agent_state = graph.propagator.create_initial_state(
            selections["ticker"], selections["analysis_date"]
        )
        args = graph.propagator.get_graph_args()

        ui.show_success("数据获取准备完成")

        # 显示分析阶段
        ui.show_step_header(4, "智能分析阶段 | AI Analysis Phase (预计耗时约10分钟)")
        ui.show_progress("启动分析师团队...")
        ui.show_user_message(
            "💡 提示：智能分析包含多个团队协作，请耐心等待约10分钟", "dim"
        )

        # Stream the analysis
        trace = []

        # 跟踪已完成的分析师，避免重复提示
        completed_analysts = set()

        for chunk in cast(Any, graph.graph).stream(init_agent_state, **args):
            if len(chunk["messages"]) > 0:
                # Get the last message from the chunk
                last_message = chunk["messages"][-1]

                # Extract message content and type
                if hasattr(last_message, "content"):
                    content = extract_content_string(
                        last_message.content
                    )  # Use the helper function
                    msg_type = "Reasoning"
                else:
                    content = str(last_message)
                    msg_type = "System"

                # Add message to buffer
                message_buffer.add_message(msg_type, content)

                # If it's a tool call, add it to tool calls
                if hasattr(last_message, "tool_calls"):
                    for tool_call in last_message.tool_calls:
                        # Handle both dictionary and object tool calls
                        if isinstance(tool_call, dict):
                            message_buffer.add_tool_call(
                                tool_call["name"], tool_call["args"]
                            )
                        else:
                            message_buffer.add_tool_call(tool_call.name, tool_call.args)

                # Update reports and agent status based on chunk content
                # Analyst Team Reports
                if "market_report" in chunk and chunk["market_report"]:
                    # 只在第一次完成时显示提示
                    if "market_report" not in completed_analysts:
                        ui.show_success("📈 市场分析完成")
                        completed_analysts.add("market_report")
                        # 调试信息（写入日志文件）
                        logger.info(
                            f"首次显示市场分析完成提示，已完成分析师: {completed_analysts}"
                        )
                    else:
                        # 调试信息（写入日志文件）
                        logger.debug(
                            f"跳过重复的市场分析完成提示，已完成分析师: {completed_analysts}"
                        )

                    message_buffer.update_report_section(
                        "market_report", chunk["market_report"]
                    )
                    message_buffer.update_agent_status("Market Analyst", "completed")
                    # Set next analyst to in_progress
                    if "social" in selections["analysts"]:
                        message_buffer.update_agent_status(
                            "Social Analyst", "in_progress"
                        )

                if "sentiment_report" in chunk and chunk["sentiment_report"]:
                    # 只在第一次完成时显示提示
                    if "sentiment_report" not in completed_analysts:
                        ui.show_success("💭 情感分析完成")
                        completed_analysts.add("sentiment_report")
                        # 调试信息（写入日志文件）
                        logger.info(
                            f"首次显示情感分析完成提示，已完成分析师: {completed_analysts}"
                        )
                    else:
                        # 调试信息（写入日志文件）
                        logger.debug(
                            f"跳过重复的情感分析完成提示，已完成分析师: {completed_analysts}"
                        )

                    message_buffer.update_report_section(
                        "sentiment_report", chunk["sentiment_report"]
                    )
                    message_buffer.update_agent_status("Social Analyst", "completed")
                    # Set next analyst to in_progress
                    if "news" in selections["analysts"]:
                        message_buffer.update_agent_status(
                            "News Analyst", "in_progress"
                        )

                if "news_report" in chunk and chunk["news_report"]:
                    # 只在第一次完成时显示提示
                    if "news_report" not in completed_analysts:
                        ui.show_success("📰 新闻分析完成")
                        completed_analysts.add("news_report")
                        # 调试信息（写入日志文件）
                        logger.info(
                            f"首次显示新闻分析完成提示，已完成分析师: {completed_analysts}"
                        )
                    else:
                        # 调试信息（写入日志文件）
                        logger.debug(
                            f"跳过重复的新闻分析完成提示，已完成分析师: {completed_analysts}"
                        )

                    message_buffer.update_report_section(
                        "news_report", chunk["news_report"]
                    )
                    message_buffer.update_agent_status("News Analyst", "completed")
                    # Set next analyst to in_progress
                    if "fundamentals" in selections["analysts"]:
                        message_buffer.update_agent_status(
                            "Fundamentals Analyst", "in_progress"
                        )

                if "fundamentals_report" in chunk and chunk["fundamentals_report"]:
                    # 只在第一次完成时显示提示
                    if "fundamentals_report" not in completed_analysts:
                        ui.show_success("📊 基本面分析完成")
                        completed_analysts.add("fundamentals_report")
                        # 调试信息（写入日志文件）
                        logger.info(
                            f"首次显示基本面分析完成提示，已完成分析师: {completed_analysts}"
                        )
                    else:
                        # 调试信息（写入日志文件）
                        logger.debug(
                            f"跳过重复的基本面分析完成提示，已完成分析师: {completed_analysts}"
                        )

                    message_buffer.update_report_section(
                        "fundamentals_report", chunk["fundamentals_report"]
                    )
                    message_buffer.update_agent_status(
                        "Fundamentals Analyst", "completed"
                    )
                    # Set all research team members to in_progress
                    update_research_team_status("in_progress")

                # Research Team - Handle Investment Debate State
                if (
                    "investment_debate_state" in chunk
                    and chunk["investment_debate_state"]
                ):
                    debate_state = chunk["investment_debate_state"]

                    # Update Bull Researcher status and report
                    if "bull_history" in debate_state and debate_state["bull_history"]:
                        # 显示研究团队开始工作
                        if "research_team_started" not in completed_analysts:
                            ui.show_progress("🔬 研究团队开始深度分析...")
                            completed_analysts.add("research_team_started")

                        # Keep all research team members in progress
                        update_research_team_status("in_progress")
                        # Extract latest bull response
                        bull_responses = debate_state["bull_history"].split("\n")
                        latest_bull = bull_responses[-1] if bull_responses else ""
                        if latest_bull:
                            message_buffer.add_message("Reasoning", latest_bull)
                            # Update research report with bull's latest analysis
                            message_buffer.update_report_section(
                                "investment_plan",
                                f"### Bull Researcher Analysis\n{latest_bull}",
                            )

                    # Update Bear Researcher status and report
                    if "bear_history" in debate_state and debate_state["bear_history"]:
                        # Keep all research team members in progress
                        update_research_team_status("in_progress")
                        # Extract latest bear response
                        bear_responses = debate_state["bear_history"].split("\n")
                        latest_bear = bear_responses[-1] if bear_responses else ""
                        if latest_bear:
                            message_buffer.add_message("Reasoning", latest_bear)
                            # Update research report with bear's latest analysis
                            message_buffer.update_report_section(
                                "investment_plan",
                                f"{message_buffer.report_sections['investment_plan']}\n\n### Bear Researcher Analysis\n{latest_bear}",
                            )

                    # Update Research Manager status and final decision
                    if (
                        "judge_decision" in debate_state
                        and debate_state["judge_decision"]
                    ):
                        # 显示研究团队完成
                        if "research_team" not in completed_analysts:
                            ui.show_success("🔬 研究团队分析完成")
                            completed_analysts.add("research_team")

                        # Keep all research team members in progress until final decision
                        update_research_team_status("in_progress")
                        message_buffer.add_message(
                            "Reasoning",
                            f"Research Manager: {debate_state['judge_decision']}",
                        )
                        # Update research report with final decision
                        message_buffer.update_report_section(
                            "investment_plan",
                            f"{message_buffer.report_sections['investment_plan']}\n\n### Research Manager Decision\n{debate_state['judge_decision']}",
                        )
                        # Mark all research team members as completed
                        update_research_team_status("completed")
                        # Set first risk analyst to in_progress
                        message_buffer.update_agent_status(
                            "Risky Analyst", "in_progress"
                        )

                # Trading Team
                if (
                    "trader_investment_plan" in chunk
                    and chunk["trader_investment_plan"]
                ):
                    # 显示交易团队开始工作
                    if "trading_team_started" not in completed_analysts:
                        ui.show_progress("💼 交易团队制定投资计划...")
                        completed_analysts.add("trading_team_started")

                    # 显示交易团队完成
                    if "trading_team" not in completed_analysts:
                        ui.show_success("💼 交易团队计划完成")
                        completed_analysts.add("trading_team")

                    message_buffer.update_report_section(
                        "trader_investment_plan", chunk["trader_investment_plan"]
                    )
                    # Set first risk analyst to in_progress
                    message_buffer.update_agent_status("Risky Analyst", "in_progress")

                # Risk Management Team - Handle Risk Debate State
                if "risk_debate_state" in chunk and chunk["risk_debate_state"]:
                    risk_state = chunk["risk_debate_state"]

                    # Update Risky Analyst status and report
                    if (
                        "current_risky_response" in risk_state
                        and risk_state["current_risky_response"]
                    ):
                        # 显示风险管理团队开始工作
                        if "risk_team_started" not in completed_analysts:
                            ui.show_progress("⚖️ 风险管理团队评估投资风险...")
                            completed_analysts.add("risk_team_started")

                        message_buffer.update_agent_status(
                            "Risky Analyst", "in_progress"
                        )
                        message_buffer.add_message(
                            "Reasoning",
                            f"Risky Analyst: {risk_state['current_risky_response']}",
                        )
                        # Update risk report with risky analyst's latest analysis only
                        message_buffer.update_report_section(
                            "final_trade_decision",
                            f"### Risky Analyst Analysis\n{risk_state['current_risky_response']}",
                        )

                    # Update Safe Analyst status and report
                    if (
                        "current_safe_response" in risk_state
                        and risk_state["current_safe_response"]
                    ):
                        message_buffer.update_agent_status(
                            "Safe Analyst", "in_progress"
                        )
                        message_buffer.add_message(
                            "Reasoning",
                            f"Safe Analyst: {risk_state['current_safe_response']}",
                        )
                        # Update risk report with safe analyst's latest analysis only
                        message_buffer.update_report_section(
                            "final_trade_decision",
                            f"### Safe Analyst Analysis\n{risk_state['current_safe_response']}",
                        )

                    # Update Neutral Analyst status and report
                    if (
                        "current_neutral_response" in risk_state
                        and risk_state["current_neutral_response"]
                    ):
                        message_buffer.update_agent_status(
                            "Neutral Analyst", "in_progress"
                        )
                        message_buffer.add_message(
                            "Reasoning",
                            f"Neutral Analyst: {risk_state['current_neutral_response']}",
                        )
                        # Update risk report with neutral analyst's latest analysis only
                        message_buffer.update_report_section(
                            "final_trade_decision",
                            f"### Neutral Analyst Analysis\n{risk_state['current_neutral_response']}",
                        )

                    # Update Portfolio Manager status and final decision
                    if "judge_decision" in risk_state and risk_state["judge_decision"]:
                        # 显示风险管理团队完成
                        if "risk_management" not in completed_analysts:
                            ui.show_success("⚖️ 风险管理团队分析完成")
                            completed_analysts.add("risk_management")

                        message_buffer.update_agent_status(
                            "Portfolio Manager", "in_progress"
                        )
                        message_buffer.add_message(
                            "Reasoning",
                            f"Portfolio Manager: {risk_state['judge_decision']}",
                        )
                        # Update risk report with final decision only
                        message_buffer.update_report_section(
                            "final_trade_decision",
                            f"### Portfolio Manager Decision\n{risk_state['judge_decision']}",
                        )
                        # Mark risk analysts as completed
                        message_buffer.update_agent_status("Risky Analyst", "completed")
                        message_buffer.update_agent_status("Safe Analyst", "completed")
                        message_buffer.update_agent_status(
                            "Neutral Analyst", "completed"
                        )
                        message_buffer.update_agent_status(
                            "Portfolio Manager", "completed"
                        )

                # Update the display
                update_display(layout)

            trace.append(chunk)

        # 显示最终决策阶段
        ui.show_step_header(5, "投资决策生成 | Investment Decision Generation")
        ui.show_progress("正在处理投资信号...")

        # Get final state and decision
        final_state = trace[-1]
        graph.process_signal(final_state["final_trade_decision"], selections["ticker"])

        ui.show_success("🤖 投资信号处理完成")

        # Update all agent statuses to completed
        for agent in message_buffer.agent_status:
            message_buffer.update_agent_status(agent, "completed")

        message_buffer.add_message(
            "Analysis", f"Completed analysis for {selections['analysis_date']}"
        )

        # Update final report sections
        for section in message_buffer.report_sections.keys():
            if section in final_state:
                message_buffer.update_report_section(section, final_state[section])

        # 显示报告生成完成
        ui.show_step_header(6, "分析报告生成 | Analysis Report Generation")
        ui.show_progress("正在生成最终报告...")

        # Display the complete final report
        display_complete_report(final_state)

        ui.show_success("📋 分析报告生成完成")
        ui.show_success(f"🎉 {selections['ticker']} 股票分析全部完成！")

        # 记录总执行时间
        total_time = time.time() - start_time
        ui.show_user_message(f"⏱️ 总分析时间: {total_time:.1f}秒", "dim")

        update_display(layout)


@app.command(name="analyze", help="开始股票分析 | Start stock analysis")
def analyze():
    """
    启动交互式股票分析工具
    Launch interactive stock analysis tool
    """
    run_analysis()
