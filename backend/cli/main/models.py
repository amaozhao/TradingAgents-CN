from .base import run_analysis
from .imports import (
    DEFAULT_API_KEY_DISPLAY_LENGTH,
    Optional,
    Table,
    app,
    console,
    get_close_matches,
    importlib,
    logger,
    os,
    settings,
    subprocess,
    sys,
    typer,
)


@app.command(name="config", help="配置设置 | Configuration settings")
def config():
    """
    显示和配置系统设置
    Display and configure system settings
    """
    logger.info("\n[bold blue]🔧 TradingAgents 配置 | Configuration[/bold blue]")
    logger.info("\n[yellow]当前支持的LLM提供商 | Supported LLM Providers:[/yellow]")

    providers_table = Table(show_header=True, header_style="bold magenta")
    providers_table.add_column("提供商 | Provider", style="cyan")
    providers_table.add_column("模型 | Models", style="green")
    providers_table.add_column("状态 | Status", style="yellow")
    providers_table.add_column("说明 | Description")

    providers_table.add_row(
        "🇨🇳 阿里百炼 (DashScope)",
        "qwen-turbo, qwen-plus, qwen-max",
        "✅ 推荐 | Recommended",
        "国产大模型，中文优化 | Chinese-optimized",
    )
    providers_table.add_row(
        "🌍 OpenAI",
        "gpt-4o, gpt-4o-mini, gpt-3.5-turbo",
        "✅ 支持 | Supported",
        "需要国外API | Requires overseas API",
    )
    providers_table.add_row(
        "🤖 Anthropic",
        "claude-3-opus, claude-3-sonnet",
        "✅ 支持 | Supported",
        "需要国外API | Requires overseas API",
    )
    providers_table.add_row(
        "🔍 Google AI",
        "gemini-pro, gemini-2.0-flash",
        "✅ 支持 | Supported",
        "需要国外API | Requires overseas API",
    )

    console.print(providers_table)

    # 检查API密钥状态
    logger.info("\n[yellow]API密钥状态 | API Key Status:[/yellow]")

    api_keys_table = Table(show_header=True, header_style="bold magenta")
    api_keys_table.add_column("API密钥 | API Key", style="cyan")
    api_keys_table.add_column("状态 | Status", style="yellow")
    api_keys_table.add_column("说明 | Description")

    # 检查各个API密钥
    dashscope_key = settings.DASHSCOPE_API_KEY
    openai_key = settings.OPENAI_API_KEY
    finnhub_key = settings.FINNHUB_API_KEY
    anthropic_key = settings.ANTHROPIC_API_KEY
    google_key = settings.GOOGLE_API_KEY

    api_keys_table.add_row(
        "DASHSCOPE_API_KEY",
        "✅ 已配置" if dashscope_key else "❌ 未配置",
        f"阿里百炼 | {dashscope_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..."
        if dashscope_key
        else "阿里百炼API密钥",
    )
    api_keys_table.add_row(
        "FINNHUB_API_KEY",
        "✅ 已配置" if finnhub_key else "❌ 未配置",
        f"金融数据 | {finnhub_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..."
        if finnhub_key
        else "金融数据API密钥",
    )
    api_keys_table.add_row(
        "OPENAI_API_KEY",
        "✅ 已配置" if openai_key else "❌ 未配置",
        f"OpenAI | {openai_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..."
        if openai_key
        else "OpenAI API密钥",
    )
    api_keys_table.add_row(
        "ANTHROPIC_API_KEY",
        "✅ 已配置" if anthropic_key else "❌ 未配置",
        f"Anthropic | {anthropic_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..."
        if anthropic_key
        else "Anthropic API密钥",
    )
    api_keys_table.add_row(
        "GOOGLE_API_KEY",
        "✅ 已配置" if google_key else "❌ 未配置",
        f"Google AI | {google_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..."
        if google_key
        else "Google AI API密钥",
    )

    console.print(api_keys_table)

    logger.info("\n[yellow]配置API密钥 | Configure API Keys:[/yellow]")
    logger.info("1. 编辑 backend/.env 文件 | Edit backend/.env")
    logger.info("2. 或设置环境变量 | Or set environment variables:")
    logger.info("   - DASHSCOPE_API_KEY (阿里百炼)")
    logger.info("   - OPENAI_API_KEY (OpenAI)")
    logger.info("   - FINNHUB_API_KEY (金融数据 | Financial data)")

    # 如果缺少关键API密钥，给出提示
    if not dashscope_key or not finnhub_key:
        logger.warning("[red]⚠️ 警告 | Warning:[/red]")
        if not dashscope_key:
            logger.info("   • 缺少阿里百炼API密钥，无法使用推荐的中文优化模型")
        if not finnhub_key:
            logger.info("   • 缺少金融数据API密钥，无法获取实时股票数据")

    logger.info("\n[yellow]示例程序 | Example Programs:[/yellow]")
    logger.info(
        "• python examples/demo/deepseek/analysis/example.py  # DeepSeek 分析演示"
    )
    logger.info(
        "• python examples/data/dir/config/demo/example.py    # 数据目录配置演示"
    )
    logger.info("• python scripts/installation/script.py              # 安装验证脚本")


@app.command(name="version", help="版本信息 | Version information")
def version():
    """
    显示版本信息
    Display version information
    """
    # 读取版本号
    try:
        with open("VERSION", "r", encoding="utf-8") as f:
            version = f.read().strip()
    except FileNotFoundError:
        version = "1.0.0"

    logger.info(
        "\n[bold blue]📊 TradingAgents 版本信息 | Version Information[/bold blue]"
    )
    logger.info(
        f"[green]版本 | Version:[/green] {version} [yellow](预览版 | Preview)[/yellow]"
    )
    logger.info("[green]发布日期 | Release Date:[/green] 2025-06-26")
    logger.info(
        "[green]框架 | Framework:[/green] 多智能体金融交易分析 | Multi-Agent Financial Trading Analysis"
    )
    logger.info("[green]支持的语言 | Languages:[/green] 中文 | English")
    logger.info(
        "[green]开发状态 | Development Status:[/green] [yellow]早期预览版，功能持续完善中[/yellow]"
    )
    logger.info(
        "[green]基于项目 | Based on:[/green] [blue]TauricResearch/TradingAgents[/blue]"
    )
    logger.info(
        "[green]创建目的 | Purpose:[/green] [cyan]更好地在中国推广TradingAgents[/cyan]"
    )
    logger.info("[green]主要功能 | Features:[/green]")
    logger.info("  • 🤖 多智能体协作分析 | Multi-agent collaborative analysis")
    logger.info("  • 🇨🇳 阿里百炼大模型支持 | Alibaba DashScope support")
    logger.info("  • 📈 实时股票数据分析 | Real-time stock data analysis")
    logger.info("  • 🧠 智能投资建议 | Intelligent investment recommendations")
    logger.debug("  • 🔍 风险评估 | Risk assessment")

    logger.warning("\n[yellow]⚠️  预览版本提醒 | Preview Version Notice:[/yellow]")
    logger.info("  • 这是早期预览版本，功能仍在完善中")
    logger.info("  • 建议仅在测试环境中使用")
    logger.info("  • 投资建议仅供参考，请谨慎决策")
    logger.info("  • 欢迎反馈问题和改进建议")

    logger.info("\n[blue]🙏 致敬源项目 | Tribute to Original Project:[/blue]")
    logger.info("  • 💎 感谢 Tauric Research 团队提供的珍贵源码")
    logger.info("  • 🔄 感谢持续的维护、更新和改进工作")
    logger.info("  • 🌍 感谢选择Apache 2.0协议的开源精神")
    logger.info("  • 🎯 本项目旨在更好地在中国推广TradingAgents")
    logger.info("  • 🔗 源项目: https://github.com/TauricResearch/TradingAgents")


@app.command(name="data-config", help="数据目录配置 | Data directory configuration")
def data_config(
    show: bool = typer.Option(
        False, "--show", "-s", help="显示当前配置 | Show current configuration"
    ),
    set_dir: Optional[str] = typer.Option(
        None, "--set", "-d", help="设置数据目录 | Set data directory"
    ),
    reset: bool = typer.Option(
        False, "--reset", "-r", help="重置为默认配置 | Reset to default configuration"
    ),
):
    """
    配置数据目录路径
    Configure data directory paths
    """
    config_manager = getattr(
        importlib.import_module("trader.config.manager"), "config_manager"
    )

    # 使用 config_manager 的方法
    get_data_dir = config_manager.get_data_dir
    set_data_dir = config_manager.set_data_dir

    logger.info(
        "\n[bold blue]📁 数据目录配置 | Data Directory Configuration[/bold blue]"
    )

    if reset:
        # 重置为默认配置
        default_data_dir = os.path.join(
            os.path.expanduser("~"), "Documents", "TradingAgents", "data"
        )
        set_data_dir(default_data_dir)
        logger.info(f"[green]✅ 已重置数据目录为默认路径: {default_data_dir}[/green]")
        return

    if set_dir:
        # 设置新的数据目录
        try:
            set_data_dir(set_dir)
            logger.info(f"[green]✅ 数据目录已设置为: {set_dir}[/green]")

            # 显示创建的目录结构
            if os.path.exists(set_dir):
                logger.info("\n[blue]📂 目录结构:[/blue]")
                for root, dirs, files in os.walk(set_dir):
                    level = root.replace(set_dir, "").count(os.sep)
                    if level > 2:  # 限制显示深度
                        continue
                    indent = "  " * level
                    logger.info(f"{indent}📁 {os.path.basename(root)}/")
        except Exception as e:
            logger.error(f"[red]❌ 设置数据目录失败: {e}[/red]")
        return

    # 显示当前配置（默认行为或使用--show）
    settings = config_manager.load_settings()
    get_data_dir()

    # 配置信息表格
    config_table = Table(show_header=True, header_style="bold magenta")
    config_table.add_column("配置项 | Configuration", style="cyan")
    config_table.add_column("路径 | Path", style="green")
    config_table.add_column("状态 | Status", style="yellow")

    directories = {
        "数据目录 | Data Directory": settings.get("data_dir", "未配置"),
        "缓存目录 | Cache Directory": settings.get("cache_dir", "未配置"),
        "结果目录 | Results Directory": settings.get("results_dir", "未配置"),
    }

    for name, path in directories.items():
        if path and path != "未配置":
            status = "✅ 存在" if os.path.exists(path) else "❌ 不存在"
        else:
            status = "⚠️ 未配置"
        config_table.add_row(name, str(path), status)

    console.print(config_table)

    # 环境变量信息
    logger.info("\n[blue]🌍 环境变量 | Environment Variables:[/blue]")
    env_table = Table(show_header=True, header_style="bold magenta")
    env_table.add_column("环境变量 | Variable", style="cyan")
    env_table.add_column("值 | Value", style="green")

    env_vars = {
        "TRADING_AGENTS_DATA_DIR": settings.TRADING_AGENTS_DATA_DIR or "未设置",
        "TRADING_AGENTS_CACHE_DIR": settings.TRADING_AGENTS_CACHE_DIR or "未设置",
        "TRADING_AGENTS_RESULTS_DIR": settings.TRADING_AGENTS_RESULTS_DIR or "未设置",
    }

    for var, value in env_vars.items():
        env_table.add_row(var, value)

    console.print(env_table)

    # 使用说明
    logger.info("\n[yellow]💡 使用说明 | Usage:[/yellow]")
    logger.info("• 设置数据目录: trading_agents data-config --set /path/to/data")
    logger.info("• 重置为默认: trading_agents data-config --reset")
    logger.info("• 查看当前配置: trading_agents data-config --show")
    logger.info("• 环境变量优先级最高 | Environment variables have highest priority")


@app.command(name="examples", help="示例程序 | Example programs")
def examples():
    """
    显示可用的示例程序
    Display available example programs
    """
    logger.info("\n[bold blue]📚 TradingAgents 示例程序 | Example Programs[/bold blue]")

    examples_table = Table(show_header=True, header_style="bold magenta")
    examples_table.add_column("类型 | Type", style="cyan")
    examples_table.add_column("文件名 | Filename", style="green")
    examples_table.add_column("说明 | Description")

    examples_table.add_row(
        "🤖 DeepSeek",
        "examples/demo/deepseek/analysis/example.py",
        "DeepSeek 股票分析演示 | DeepSeek stock analysis demo",
    )
    examples_table.add_row(
        "📁 配置演示",
        "examples/data/dir/config/demo/example.py",
        "数据目录配置演示 | Data directory configuration demo",
    )
    examples_table.add_row(
        "📈 股票查询",
        "examples/stock/query/example.py",
        "股票查询演示 | Stock query demo",
    )
    examples_table.add_row(
        "🧪 安装验证",
        "scripts/installation/script.py",
        "安装验证脚本 | Installation verification script",
    )
    examples_table.add_row(
        "🧪 集成测试",
        "tests/integration/",
        "pytest 集成测试目录 | pytest integration tests",
    )

    console.print(examples_table)

    logger.info("\n[yellow]运行示例 | Run Examples:[/yellow]")
    logger.info("1. 确保已配置API密钥 | Ensure API keys are configured")
    logger.info("2. 选择合适的示例程序运行 | Choose appropriate example to run")
    logger.info("3. 推荐从中文版本开始 | Recommended to start with Chinese version")


@app.command(name="test", help="运行测试 | Run tests")
def test():
    """
    运行系统测试
    Run system tests
    """
    logger.info("\n[bold blue]🧪 TradingAgents 测试 | Tests[/bold blue]")

    logger.info("[yellow]正在运行单元测试... | Running unit tests...[/yellow]")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/unit"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        if result.returncode == 0:
            logger.info("[green]✅ 测试通过 | Tests passed[/green]")
            console.print(result.stdout)
        else:
            logger.error("[red]❌ 测试失败 | Tests failed[/red]")
            console.print(result.stderr)

    except Exception as e:
        logger.error(f"[red]❌ 测试执行错误 | Test execution error: {e}[/red]")
        logger.info("\n[yellow]手动运行测试 | Manual test execution:[/yellow]")
        logger.info("python -m pytest tests/unit")


@app.command(name="help", help="中文帮助 | Chinese help")
def help_chinese():
    """
    显示中文帮助信息
    Display Chinese help information
    """
    logger.info("\n[bold blue]📖 TradingAgents 中文帮助 | Chinese Help[/bold blue]")

    logger.info("\n[bold yellow]🚀 快速开始 | Quick Start:[/bold yellow]")
    logger.info("1. [cyan]python -m cli.main config[/cyan]     # 查看配置信息")
    logger.info("2. [cyan]python -m cli.main examples[/cyan]   # 查看示例程序")
    logger.info("3. [cyan]python -m cli.main test[/cyan]       # 运行测试")
    logger.info("4. [cyan]python -m cli.main analyze[/cyan]    # 开始股票分析")

    logger.info("\n[bold yellow]📋 主要命令 | Main Commands:[/bold yellow]")

    commands_table = Table(show_header=True, header_style="bold magenta")
    commands_table.add_column("命令 | Command", style="cyan")
    commands_table.add_column("功能 | Function", style="green")
    commands_table.add_column("说明 | Description")

    commands_table.add_row(
        "analyze", "股票分析 | Stock Analysis", "启动交互式多智能体股票分析工具"
    )
    commands_table.add_row(
        "config", "配置设置 | Configuration", "查看和配置LLM提供商、API密钥等设置"
    )
    commands_table.add_row(
        "examples", "示例程序 | Examples", "查看可用的演示程序和使用说明"
    )
    commands_table.add_row(
        "test", "运行测试 | Run Tests", "执行单元测试，验证基础功能正常"
    )
    commands_table.add_row(
        "version", "版本信息 | Version", "显示软件版本和功能特性信息"
    )

    console.print(commands_table)

    logger.info("\n[bold yellow]🇨🇳 推荐使用阿里百炼大模型:[/bold yellow]")
    logger.info("• 无需翻墙，网络稳定")
    logger.info("• 中文理解能力强")
    logger.info("• 成本相对较低")
    logger.info("• 符合国内合规要求")

    logger.info("\n[bold yellow]📞 获取帮助 | Get Help:[/bold yellow]")
    logger.info("• 项目文档: docs/ 目录")
    logger.info("• 示例程序: examples/ 目录")
    logger.info("• 集成测试: tests/ 目录")
    logger.info("• GitHub: https://github.com/TauricResearch/TradingAgents")


def main():
    """主函数 - 默认进入分析模式"""

    # 如果没有参数，直接进入分析模式
    if len(sys.argv) == 1:
        run_analysis()
    else:
        # 有参数时使用typer处理命令
        try:
            app()
        except SystemExit as e:
            # 只在退出码为2（typer的未知命令错误）时提供智能建议
            if e.code == 2 and len(sys.argv) > 1:
                unknown_command = sys.argv[1]
                available_commands = [
                    "analyze",
                    "config",
                    "version",
                    "data-config",
                    "examples",
                    "test",
                    "help",
                ]

                # 使用difflib找到最相似的命令
                suggestions = get_close_matches(
                    unknown_command, available_commands, n=3, cutoff=0.6
                )

                if suggestions:
                    logger.error(f"\n[red]❌ 未知命令: '{unknown_command}'[/red]")
                    logger.info("[yellow]💡 您是否想要使用以下命令之一？[/yellow]")
                    for suggestion in suggestions:
                        logger.info(
                            f"   • [cyan]python -m cli.main {suggestion}[/cyan]"
                        )
                    logger.info(
                        "\n[dim]使用 [cyan]python -m cli.main help[/cyan] 查看所有可用命令[/dim]"
                    )
                else:
                    logger.error(f"\n[red]❌ 未知命令: '{unknown_command}'[/red]")
                    logger.info(
                        "[yellow]使用 [cyan]python -m cli.main help[/cyan] 查看所有可用命令[/yellow]"
                    )
            raise e


if __name__ == "__main__":
    main()
