# ruff: noqa: F401,F403,F405,F821
def select_market():
    """选择股票市场"""
    markets = {
        "1": {
            "name": "美股",
            "name_en": "US Stock",
            "default": "SPY",
            "examples": ["SPY", "AAPL", "TSLA", "NVDA", "MSFT"],
            "format": "直接输入代码 (如: AAPL)",
            "pattern": r"^[A-Z]{1,5}$",
            "data_source": "yahoo_finance",
        },
        "2": {
            "name": "A股",
            "name_en": "China A-Share",
            "default": "600036",
            "examples": ["000001 (平安银行)", "600036 (招商银行)", "000858 (五粮液)"],
            "format": "6位数字代码 (如: 600036, 000001)",
            "pattern": r"^\d{6}$",
            "data_source": "china_stock",
        },
        "3": {
            "name": "港股",
            "name_en": "Hong Kong Stock",
            "default": "0700.HK",
            "examples": ["0700.HK (腾讯)", "09988.HK (阿里巴巴)", "03690.HK (美团)"],
            "format": "代码.HK (如: 0700.HK, 09988.HK)",
            "pattern": r"^\d{4,5}\.HK$",
            "data_source": "yahoo_finance",
        },
    }

    console.print(
        "\n[bold cyan]请选择股票市场 | Please select stock market:[/bold cyan]"
    )
    for key, market in markets.items():
        examples_str = ", ".join(market["examples"][:3])
        console.print(f"[cyan]{key}[/cyan]. 🌍 {market['name']} | {market['name_en']}")
        console.print(f"   示例 | Examples: {examples_str}")

    while True:
        choice = typer.prompt("\n请选择市场 | Select market", default="2")
        if choice in markets:
            selected_market = markets[choice]
            console.print(
                f"[green]✅ 已选择: {selected_market['name']} | Selected: {selected_market['name_en']}[/green]"
            )
            # 记录系统日志（只写入文件）
            logger.info(
                f"用户选择市场: {selected_market['name']} ({selected_market['name_en']})"
            )
            return selected_market
        else:
            console.print(
                "[red]❌ 无效选择，请输入 1、2 或 3 | Invalid choice, please enter 1, 2, or 3[/red]"
            )
            logger.warning(f"用户输入无效选择: {choice}")


def get_ticker(market):
    """根据选定市场获取股票代码"""
    console.print(
        f"\n[bold cyan]{market['name']}股票示例 | {market['name_en']} Examples:[/bold cyan]"
    )
    for example in market["examples"]:
        console.print(f"  • {example}")

    console.print(f"\n[dim]格式要求 | Format: {market['format']}[/dim]")

    while True:
        ticker = typer.prompt(
            f"\n请输入{market['name']}股票代码 | Enter {market['name_en']} ticker",
            default=market["default"],
        )

        # 记录用户输入（只写入文件）
        logger.info(f"用户输入股票代码: {ticker}")

        # 验证股票代码格式
        re = importlib.import_module("re")

        # 添加边界条件检查
        ticker = normalize_ticker_symbol(ticker)
        if not ticker:  # 检查空字符串
            console.print("[red]❌ 股票代码不能为空 | Ticker cannot be empty[/red]")
            logger.warning("用户输入空股票代码")
            continue

        ticker_to_check = ticker if market["data_source"] != "china_stock" else ticker

        if re.match(market["pattern"], ticker_to_check):
            # 对于A股，返回纯数字代码
            if market["data_source"] == "china_stock":
                console.print(
                    f"[green]✅ A股代码有效: {ticker} (将使用中国股票数据源)[/green]"
                )
                logger.info(f"A股代码验证成功: {ticker}")
                return ticker
            else:
                console.print(f"[green]✅ 股票代码有效: {ticker.upper()}[/green]")
                logger.info(f"股票代码验证成功: {ticker.upper()}")
                return ticker.upper()
        else:
            console.print("[red]❌ 股票代码格式不正确 | Invalid ticker format[/red]")
            console.print(f"[yellow]请使用正确格式: {market['format']}[/yellow]")
            logger.warning(f"股票代码格式验证失败: {ticker}")


def get_analysis_date():
    """Get the analysis date from user input."""
    while True:
        date_str = typer.prompt(
            "请输入分析日期 | Enter analysis date",
            default=datetime.datetime.now().strftime("%Y-%m-%d"),
        )
        try:
            # Validate date format and ensure it's not in the future
            analysis_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            if analysis_date.date() > datetime.datetime.now().date():
                console.print(
                    "[red]错误：分析日期不能是未来日期 | Error: Analysis date cannot be in the future[/red]"
                )
                logger.warning(f"用户输入未来日期: {date_str}")
                continue
            return date_str
        except ValueError:
            console.print(
                "[red]错误：日期格式无效，请使用 YYYY-MM-DD 格式 | Error: Invalid date format. Please use YYYY-MM-DD[/red]"
            )


def display_complete_report(final_state):
    """Display the complete analysis report with team-based panels."""
    logger.info("\n[bold green]Complete Analysis Report[/bold green]\n")

    # I. Analyst Team Reports
    analyst_reports = []

    # Market Analyst Report
    if final_state.get("market_report"):
        analyst_reports.append(
            Panel(
                Markdown(final_state["market_report"]),
                title="Market Analyst",
                border_style="blue",
                padding=(1, 2),
            )
        )

    # Social Analyst Report
    if final_state.get("sentiment_report"):
        analyst_reports.append(
            Panel(
                Markdown(final_state["sentiment_report"]),
                title="Social Analyst",
                border_style="blue",
                padding=(1, 2),
            )
        )

    # News Analyst Report
    if final_state.get("news_report"):
        analyst_reports.append(
            Panel(
                Markdown(final_state["news_report"]),
                title="News Analyst",
                border_style="blue",
                padding=(1, 2),
            )
        )

    # Fundamentals Analyst Report
    if final_state.get("fundamentals_report"):
        analyst_reports.append(
            Panel(
                Markdown(final_state["fundamentals_report"]),
                title="Fundamentals Analyst",
                border_style="blue",
                padding=(1, 2),
            )
        )

    if analyst_reports:
        console.print(
            Panel(
                Columns(analyst_reports, equal=True, expand=True),
                title="I. Analyst Team Reports",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    # II. Research Team Reports
    if final_state.get("investment_debate_state"):
        research_reports = []
        debate_state = final_state["investment_debate_state"]

        # Bull Researcher Analysis
        if debate_state.get("bull_history"):
            research_reports.append(
                Panel(
                    Markdown(debate_state["bull_history"]),
                    title="Bull Researcher",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        # Bear Researcher Analysis
        if debate_state.get("bear_history"):
            research_reports.append(
                Panel(
                    Markdown(debate_state["bear_history"]),
                    title="Bear Researcher",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        # Research Manager Decision
        if debate_state.get("judge_decision"):
            research_reports.append(
                Panel(
                    Markdown(debate_state["judge_decision"]),
                    title="Research Manager",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        if research_reports:
            console.print(
                Panel(
                    Columns(research_reports, equal=True, expand=True),
                    title="II. Research Team Decision",
                    border_style="magenta",
                    padding=(1, 2),
                )
            )

    # III. Trading Team Reports
    if final_state.get("trader_investment_plan"):
        console.print(
            Panel(
                Panel(
                    Markdown(final_state["trader_investment_plan"]),
                    title="Trader",
                    border_style="blue",
                    padding=(1, 2),
                ),
                title="III. Trading Team Plan",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    # IV. Risk Management Team Reports
    if final_state.get("risk_debate_state"):
        risk_reports = []
        risk_state = final_state["risk_debate_state"]

        # Aggressive (Risky) Analyst Analysis
        if risk_state.get("risky_history"):
            risk_reports.append(
                Panel(
                    Markdown(risk_state["risky_history"]),
                    title="Aggressive Analyst",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        # Conservative (Safe) Analyst Analysis
        if risk_state.get("safe_history"):
            risk_reports.append(
                Panel(
                    Markdown(risk_state["safe_history"]),
                    title="Conservative Analyst",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        # Neutral Analyst Analysis
        if risk_state.get("neutral_history"):
            risk_reports.append(
                Panel(
                    Markdown(risk_state["neutral_history"]),
                    title="Neutral Analyst",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        if risk_reports:
            console.print(
                Panel(
                    Columns(risk_reports, equal=True, expand=True),
                    title="IV. Risk Management Team Decision",
                    border_style="red",
                    padding=(1, 2),
                )
            )

        # V. Portfolio Manager Decision
        if risk_state.get("judge_decision"):
            console.print(
                Panel(
                    Panel(
                        Markdown(risk_state["judge_decision"]),
                        title="Portfolio Manager",
                        border_style="blue",
                        padding=(1, 2),
                    ),
                    title="V. Portfolio Manager Decision",
                    border_style="green",
                    padding=(1, 2),
                )
            )


def update_research_team_status(status):
    """
    更新所有研究团队成员和交易员的状态
    Update status for all research team members and trader

    Args:
        status: 新的状态值
    """
    research_team = ["Bull Researcher", "Bear Researcher", "Research Manager", "Trader"]
    for agent in research_team:
        message_buffer.update_agent_status(agent, status)


def extract_content_string(content):
    """
    从各种消息格式中提取字符串内容
    Extract string content from various message formats

    Args:
        content: 消息内容，可能是字符串、列表或其他格式

    Returns:
        str: 提取的字符串内容
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # Handle Anthropic's list format
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type")  # 缓存type值
                if item_type == "text":
                    text_parts.append(item.get("text", ""))
                elif item_type == "tool_use":
                    tool_name = item.get("name", "unknown")  # 缓存name值
                    text_parts.append(f"[Tool: {tool_name}]")
            else:
                text_parts.append(str(item))
        return " ".join(text_parts)
    else:
        return str(content)


def check_api_keys(llm_provider: str) -> bool:
    """检查必要的API密钥是否已配置"""

    missing_keys = []
    provider = llm_provider.lower()

    # 检查LLM提供商对应的API密钥
    if provider in {"qwen", "dashscope"}:
        if not settings.DASHSCOPE_API_KEY:
            missing_keys.append("DASHSCOPE_API_KEY (阿里百炼)")
    elif provider == "deepseek":
        if not settings.DEEPSEEK_API_KEY:
            missing_keys.append("DEEPSEEK_API_KEY")
    elif provider == "openai":
        if not settings.OPENAI_API_KEY:
            missing_keys.append("OPENAI_API_KEY")
    elif provider == "custom_openai":
        if not settings.CUSTOM_OPENAI_API_KEY and not settings.OPENAI_API_KEY:
            missing_keys.append("CUSTOM_OPENAI_API_KEY / OPENAI_API_KEY")
    elif provider == "openrouter":
        if not settings.OPENROUTER_API_KEY:
            missing_keys.append("OPENROUTER_API_KEY")
    elif provider == "glm":
        if not settings.ZHIPU_API_KEY:
            missing_keys.append("ZHIPU_API_KEY")
    elif provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            missing_keys.append("ANTHROPIC_API_KEY")
    elif provider == "google":
        if not settings.GOOGLE_API_KEY:
            missing_keys.append("GOOGLE_API_KEY")

    # 检查金融数据API密钥
    if not settings.FINNHUB_API_KEY:
        missing_keys.append("FINNHUB_API_KEY (金融数据)")

    if missing_keys:
        logger.error("[red]❌ 缺少必要的API密钥 | Missing required API keys[/red]")
        for key in missing_keys:
            logger.info(f"   • {key}")

        logger.info("\n[yellow]💡 解决方案 | Solutions:[/yellow]")
        logger.info("1. 在 backend/.env 创建配置文件 | Create backend/.env:")
        logger.info("   DASHSCOPE_API_KEY=your_dashscope_key")
        logger.info("   FINNHUB_API_KEY=your_finnhub_key")
        logger.info("\n2. 或设置环境变量 | Or set environment variables")
        logger.info("\n3. 运行 'python -m cli.main config' 查看详细配置说明")

        return False

    return True
