from .imports import (
    PROJECT_ROOT,
    TOKEN_TRACKING_ENABLED,
    datetime,
    get_logger_manager,
    importlib,
    logger,
    os,
    settings,
    st,
    token_tracker,
    uuid,
)

def translate_analyst_labels(text):
    """将分析师的英文标签转换为中文"""
    if not text:
        return text

    # 分析师标签翻译映射
    translations = {
        "Bull Analyst:": "看涨分析师:",
        "Bear Analyst:": "看跌分析师:",
        "Risky Analyst:": "激进风险分析师:",
        "Safe Analyst:": "保守风险分析师:",
        "Neutral Analyst:": "中性风险分析师:",
        "Research Manager:": "研究经理:",
        "Portfolio Manager:": "投资组合经理:",
        "Risk Judge:": "风险管理委员会:",
        "Trader:": "交易员:",
    }

    # 替换所有英文标签
    for english, chinese in translations.items():
        text = text.replace(english, chinese)

    return text


def extract_risk_assessment(state):
    """从分析状态中提取风险评估数据"""
    try:
        risk_debate_state = state.get("risk_debate_state", {})

        if not risk_debate_state:
            return None

        # 提取各个风险分析师的观点并进行中文化
        risky_analysis = translate_analyst_labels(risk_debate_state.get("risky_history", ""))
        safe_analysis = translate_analyst_labels(risk_debate_state.get("safe_history", ""))
        neutral_analysis = translate_analyst_labels(risk_debate_state.get("neutral_history", ""))
        judge_decision = translate_analyst_labels(risk_debate_state.get("judge_decision", ""))

        # 格式化风险评估报告
        risk_assessment = f"""
## ⚠️ 风险评估报告

### 🔴 激进风险分析师观点
{risky_analysis if risky_analysis else "暂无激进风险分析"}

### 🟡 中性风险分析师观点
{neutral_analysis if neutral_analysis else "暂无中性风险分析"}

### 🟢 保守风险分析师观点
{safe_analysis if safe_analysis else "暂无保守风险分析"}

### 🏛️ 风险管理委员会最终决议
{judge_decision if judge_decision else "暂无风险管理决议"}

---
*风险评估基于多角度分析，请结合个人风险承受能力做出投资决策*
        """.strip()

        return risk_assessment

    except Exception as e:
        logger.info(f"提取风险评估数据时出错: {e}")
        return None


def run_stock_analysis(
    stock_symbol,
    analysis_date,
    analysts,
    research_depth,
    llm_provider,
    llm_model,
    market_type="美股",
    progress_callback=None,
):
    """执行股票分析

    Args:
        stock_symbol: 股票代码
        analysis_date: 分析日期
        analysts: 分析师列表
        research_depth: 研究深度
        llm_provider: LLM提供商 (dashscope/deepseek/google)
        llm_model: 大模型名称
        progress_callback: 进度回调函数，用于更新UI状态
    """

    def update_progress(message, step=None, total_steps=None):
        """更新进度"""
        if progress_callback:
            progress_callback(message, step, total_steps)
        logger.info(f"[进度] {message}")

    # 生成会话ID用于Token跟踪和日志关联
    session_id = f"analysis_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 1. 数据预获取和验证阶段
    update_progress("🔍 验证股票代码并预获取数据...", 1, 10)

    try:
        prepare_stock_data = getattr(importlib.import_module("trader.utils.validation"), "prepare_stock_data")

        # 预获取股票数据（默认30天历史数据）
        preparation_result = prepare_stock_data(
            stock_code=stock_symbol,
            market_type=market_type,
            period_days=30,  # 可以根据research_depth调整
            analysis_date=analysis_date,
        )

        if not preparation_result.is_valid:
            error_msg = f"❌ 股票数据验证失败: {preparation_result.error_message}"
            update_progress(error_msg)
            logger.error(f"[{session_id}] {error_msg}")

            return {
                "success": False,
                "error": preparation_result.error_message,
                "suggestion": preparation_result.suggestion,
                "stock_symbol": stock_symbol,
                "analysis_date": analysis_date,
                "session_id": session_id,
            }

        # 数据预获取成功
        success_msg = f"✅ 数据准备完成: {preparation_result.stock_name} ({preparation_result.market_type})"
        update_progress(success_msg)  # 使用智能检测，不再硬编码步骤
        logger.info(f"[{session_id}] {success_msg}")
        logger.info(f"[{session_id}] 缓存状态: {preparation_result.cache_status}")

    except Exception as e:
        error_msg = f"❌ 数据预获取过程中发生错误: {str(e)}"
        update_progress(error_msg)
        logger.error(f"[{session_id}] {error_msg}")

        return {
            "success": False,
            "error": error_msg,
            "suggestion": "请检查网络连接或稍后重试",
            "stock_symbol": stock_symbol,
            "analysis_date": analysis_date,
            "session_id": session_id,
        }

    # 记录分析开始的详细日志
    logger_manager = get_logger_manager()
    time = importlib.import_module("time")
    analysis_start_time = time.time()

    logger_manager.log_analysis_start(logger, stock_symbol, "comprehensive_analysis", session_id)

    logger.info(
        "🚀 [分析开始] 股票分析启动",
        extra={
            "stock_symbol": stock_symbol,
            "analysis_date": analysis_date,
            "analysts": analysts,
            "research_depth": research_depth,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "market_type": market_type,
            "session_id": session_id,
            "event_type": "web_analysis_start",
        },
    )

    update_progress("🚀 开始股票分析...")

    # 估算Token使用（用于成本预估）
    if TOKEN_TRACKING_ENABLED:
        estimated_input = 2000 * len(analysts)  # 估算每个分析师2000个输入token
        estimated_output = 1000 * len(analysts)  # 估算每个分析师1000个输出token
        estimated_cost_result = token_tracker.estimate_cost(llm_provider, llm_model, estimated_input, estimated_output)

        # estimate_cost 返回 tuple (cost, currency)
        if isinstance(estimated_cost_result, tuple):
            estimated_cost, currency = estimated_cost_result
        else:
            estimated_cost = estimated_cost_result

        update_progress(f"💰 预估分析成本: ¥{estimated_cost:.4f}")

    # 验证 Settings 配置
    update_progress("检查 Settings 配置...")
    dashscope_key = settings.DASHSCOPE_API_KEY
    finnhub_key = settings.FINNHUB_API_KEY

    logger.info("Settings 配置检查:")
    logger.info(f"  DASHSCOPE_API_KEY: {'已设置' if dashscope_key else '未设置'}")
    logger.info(f"  FINNHUB_API_KEY: {'已设置' if finnhub_key else '未设置'}")

    if not dashscope_key:
        raise ValueError("DASHSCOPE_API_KEY 环境变量未设置")
    if not finnhub_key:
        raise ValueError("FINNHUB_API_KEY 环境变量未设置")

    update_progress("环境变量验证通过")

    try:
        # 导入必要的模块
        TradingAgentsGraph = getattr(importlib.import_module("trader.graph.trading"), "TradingAgentsGraph")
        DEFAULT_CONFIG = getattr(importlib.import_module("trader.default"), "DEFAULT_CONFIG")

        # 创建配置
        update_progress("配置分析参数...")
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = llm_provider
        config["deep_think_llm"] = llm_model
        config["quick_think_llm"] = llm_model
        # 根据研究深度调整配置
        if research_depth == 1:  # 1级 - 快速分析
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 1
            # 禁用记忆以加速
            config["memory_enabled"] = False

            # 统一使用在线工具，避免离线工具的各种问题
            config["online_tools"] = True  # 所有市场都使用统一工具
            logger.info(f"🔧 [快速分析] {market_type}使用统一工具，确保数据源正确和稳定性")
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-turbo"  # 使用最快模型
                config["deep_think_llm"] = "qwen-plus"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"  # DeepSeek只有一个模型
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 2:  # 2级 - 基础分析
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 1
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen-plus"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
        elif research_depth == 3:  # 3级 - 标准分析 (默认)
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 2
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen3-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 4:  # 4级 - 深度分析
            config["max_debate_rounds"] = 2
            config["max_risk_discuss_rounds"] = 2
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen3-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        else:  # 5级 - 全面分析
            config["max_debate_rounds"] = 3
            config["max_risk_discuss_rounds"] = 3
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen3-max"
                config["deep_think_llm"] = "qwen3-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"

        # 根据LLM提供商设置不同的配置
        if llm_provider == "dashscope":
            config["backend_url"] = "https://dashscope.aliyuncs.com/api/v1"
        elif llm_provider == "deepseek":
            config["backend_url"] = "https://api.deepseek.com"
        elif llm_provider == "qianfan":
            # 千帆（文心一言）配置
            config["backend_url"] = "https://aip.baidubce.com"
            # 根据研究深度设置千帆模型
            if research_depth <= 2:  # 快速和基础分析
                config["quick_think_llm"] = "ernie-3.5-8k"
                config["deep_think_llm"] = "ernie-3.5-8k"
            elif research_depth <= 4:  # 标准和深度分析
                config["quick_think_llm"] = "ernie-3.5-8k"
                config["deep_think_llm"] = "ernie-4.0-turbo-8k"
            else:  # 全面分析
                config["quick_think_llm"] = "ernie-4.0-turbo-8k"
                config["deep_think_llm"] = "ernie-4.0-turbo-8k"

            logger.info(f"🤖 [千帆] 快速模型: {config['quick_think_llm']}")
            logger.info(f"🤖 [千帆] 深度模型: {config['deep_think_llm']}")
        elif llm_provider == "google":
            # Google AI不需要backend_url，使用默认的OpenAI格式
            config["backend_url"] = "https://api.openai.com/v1"

            # 根据研究深度优化Google模型选择
            if research_depth == 1:  # 快速分析 - 使用最快模型
                config["quick_think_llm"] = "gemini-2.5-flash-lite-preview-06-17"  # 1.45s
                config["deep_think_llm"] = "gemini-2.0-flash"  # 1.87s
            elif research_depth == 2:  # 基础分析 - 使用快速模型
                config["quick_think_llm"] = "gemini-2.0-flash"  # 1.87s
                config["deep_think_llm"] = "gemini-1.5-pro"  # 2.25s
            elif research_depth == 3:  # 标准分析 - 平衡性能
                config["quick_think_llm"] = "gemini-1.5-pro"  # 2.25s
                config["deep_think_llm"] = "gemini-2.5-flash"  # 2.73s
            elif research_depth == 4:  # 深度分析 - 使用强大模型
                config["quick_think_llm"] = "gemini-2.5-flash"  # 2.73s
                config["deep_think_llm"] = "gemini-2.5-pro"  # 16.68s
            else:  # 全面分析 - 使用最强模型
                config["quick_think_llm"] = "gemini-2.5-pro"  # 16.68s
                config["deep_think_llm"] = "gemini-2.5-pro"  # 16.68s

            logger.info(f"🤖 [Google AI] 快速模型: {config['quick_think_llm']}")
            logger.info(f"🤖 [Google AI] 深度模型: {config['deep_think_llm']}")
        elif llm_provider == "openai":
            # OpenAI官方API
            config["backend_url"] = "https://api.openai.com/v1"
            logger.info(f"🤖 [OpenAI] 使用模型: {llm_model}")
            logger.info("🤖 [OpenAI] API端点: https://api.openai.com/v1")
        elif llm_provider == "openrouter":
            # OpenRouter使用OpenAI兼容API
            config["backend_url"] = "https://openrouter.ai/api/v1"
            logger.info(f"🌐 [OpenRouter] 使用模型: {llm_model}")
            logger.info("🌐 [OpenRouter] API端点: https://openrouter.ai/api/v1")
        elif llm_provider == "siliconflow":
            config["backend_url"] = "https://api.siliconflow.cn/v1"
            logger.info(f"🌐 [SiliconFlow] 使用模型: {llm_model}")
            logger.info("🌐 [SiliconFlow] API端点: https://api.siliconflow.cn/v1")
        elif llm_provider == "custom_openai":
            # 自定义OpenAI端点
            custom_base_url = st.session_state.get("custom_openai_base_url", "https://api.openai.com/v1")
            config["backend_url"] = custom_base_url
            config["custom_openai_base_url"] = custom_base_url
            logger.info(f"🔧 [自定义OpenAI] 使用模型: {llm_model}")
            logger.info(f"🔧 [自定义OpenAI] API端点: {custom_base_url}")

        # 修复路径问题 - 优先使用 Settings 配置
        # 数据目录：优先使用 Settings，否则使用默认路径
        if not config.get("data_dir") or config["data_dir"] == "./data":
            env_data_dir = settings.TRADING_AGENTS_DATA_DIR
            if env_data_dir:
                # 如果环境变量是相对路径，相对于项目根目录解析
                if not os.path.isabs(env_data_dir):
                    config["data_dir"] = str(PROJECT_ROOT / env_data_dir)
                else:
                    config["data_dir"] = env_data_dir
            else:
                config["data_dir"] = str(PROJECT_ROOT / "data")

        # 结果目录：优先使用 Settings，否则使用默认路径
        if not config.get("results_dir") or config["results_dir"] == "./results":
            env_results_dir = settings.TRADING_AGENTS_RESULTS_DIR
            if env_results_dir:
                # 如果环境变量是相对路径，相对于项目根目录解析
                if not os.path.isabs(env_results_dir):
                    config["results_dir"] = str(PROJECT_ROOT / env_results_dir)
                else:
                    config["results_dir"] = env_results_dir
            else:
                config["results_dir"] = str(PROJECT_ROOT / "results")

        # 缓存目录：优先使用 Settings，否则使用默认路径
        if not config.get("data_cache_dir"):
            env_cache_dir = settings.TRADING_AGENTS_CACHE_DIR
            if env_cache_dir:
                # 如果环境变量是相对路径，相对于项目根目录解析
                if not os.path.isabs(env_cache_dir):
                    config["data_cache_dir"] = str(PROJECT_ROOT / env_cache_dir)
                else:
                    config["data_cache_dir"] = env_cache_dir
            else:
                config["data_cache_dir"] = str(PROJECT_ROOT / "trader" / "dataflows" / "data_cache")

        # 确保目录存在
        update_progress("📁 创建必要的目录...")
        os.makedirs(config["data_dir"], exist_ok=True)
        os.makedirs(config["results_dir"], exist_ok=True)
        os.makedirs(config["data_cache_dir"], exist_ok=True)

        logger.info("📁 目录配置:")
        logger.info(f"  - 数据目录: {config['data_dir']}")
        logger.info(f"  - 结果目录: {config['results_dir']}")
        logger.info(f"  - 缓存目录: {config['data_cache_dir']}")
        logger.info(f"  - Settings TRADING_AGENTS_RESULTS_DIR: {settings.TRADING_AGENTS_RESULTS_DIR or '未设置'}")

        logger.info(f"使用配置: {config}")
        logger.info(f"分析师列表: {analysts}")
        logger.info(f"股票代码: {stock_symbol}")
        logger.info(f"分析日期: {analysis_date}")

        # 根据市场类型调整股票代码格式
        logger.debug("🔍 [RUNNER DEBUG] ===== 股票代码格式化 =====")
        logger.debug(f"🔍 [RUNNER DEBUG] 原始股票代码: '{stock_symbol}'")
        logger.debug(f"🔍 [RUNNER DEBUG] 市场类型: '{market_type}'")

        if market_type == "A股":
            # A股代码不需要特殊处理，保持原样
            formatted_symbol = stock_symbol
            logger.debug(f"🔍 [RUNNER DEBUG] A股代码保持原样: '{formatted_symbol}'")
            update_progress(f"🇨🇳 准备分析A股: {formatted_symbol}")
        elif market_type == "港股":
            # 港股代码转为大写，确保.HK后缀
            formatted_symbol = stock_symbol.upper()
            if not formatted_symbol.endswith(".HK"):
                # 如果是纯数字，添加.HK后缀
                if formatted_symbol.isdigit():
                    formatted_symbol = f"{formatted_symbol.zfill(4)}.HK"
            update_progress(f"🇭🇰 准备分析港股: {formatted_symbol}")
        else:
            # 美股代码转为大写
            formatted_symbol = stock_symbol.upper()
            logger.debug(f"🔍 [RUNNER DEBUG] 美股代码转大写: '{stock_symbol}' -> '{formatted_symbol}'")
            update_progress(f"🇺🇸 准备分析美股: {formatted_symbol}")

        logger.debug(f"🔍 [RUNNER DEBUG] 最终传递给分析引擎的股票代码: '{formatted_symbol}'")

        # 初始化交易图
        update_progress("🔧 初始化分析引擎...")
        graph = TradingAgentsGraph(analysts, config=config, debug=False)

        # 执行分析
        update_progress(f"📊 开始分析 {formatted_symbol} 股票，这可能需要几分钟时间...")
        logger.debug("🔍 [RUNNER DEBUG] ===== 调用graph.propagate =====")
        logger.debug("🔍 [RUNNER DEBUG] 传递给graph.propagate的参数:")
        logger.debug(f"🔍 [RUNNER DEBUG]   symbol: '{formatted_symbol}'")
        logger.debug(f"🔍 [RUNNER DEBUG]   date: '{analysis_date}'")

        state, decision = graph.propagate(formatted_symbol, analysis_date)

        # 调试信息
        logger.debug(f"🔍 [DEBUG] 分析完成，decision类型: {type(decision)}")
        logger.debug(f"🔍 [DEBUG] decision内容: {decision}")

        # 格式化结果
        update_progress("📋 分析完成，正在整理结果...")

        # 提取风险评估数据
        risk_assessment = extract_risk_assessment(state)

        # 将风险评估添加到状态中
        if risk_assessment:
            state["risk_assessment"] = risk_assessment

        # 记录Token使用（实际使用量，这里使用估算值）
        if TOKEN_TRACKING_ENABLED:
            # 在实际应用中，这些值应该从LLM响应中获取
            # 这里使用基于分析师数量和研究深度的估算
            actual_input_tokens = len(analysts) * (
                1500 if research_depth == "快速" else 2500 if research_depth == "标准" else 4000
            )
            actual_output_tokens = len(analysts) * (
                800 if research_depth == "快速" else 1200 if research_depth == "标准" else 2000
            )

            usage_record = token_tracker.track_usage(
                provider=llm_provider,
                model_name=llm_model,
                input_tokens=actual_input_tokens,
                output_tokens=actual_output_tokens,
                session_id=session_id,
                analysis_type=f"{market_type}_analysis",
            )

            if usage_record:
                update_progress(f"💰 记录使用成本: ¥{usage_record.cost:.4f}")

        # 从决策中提取模型信息
        model_info = decision.get("model_info", "Unknown") if isinstance(decision, dict) else "Unknown"

        results = {
            "stock_symbol": stock_symbol,
            "analysis_date": analysis_date,
            "analysts": analysts,
            "research_depth": research_depth,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "model_info": model_info,  # 🔥 添加模型信息字段
            "state": state,
            "decision": decision,
            "success": True,
            "error": None,
            "session_id": session_id if TOKEN_TRACKING_ENABLED else None,
        }

        # 记录分析完成的详细日志
        analysis_duration = time.time() - analysis_start_time

        # 计算总成本（如果有Token跟踪）
        total_cost = 0.0
        if TOKEN_TRACKING_ENABLED:
            try:
                total_cost = token_tracker.get_session_cost(session_id)
            except Exception:
                pass

        logger_manager.log_analysis_complete(
            logger,
            stock_symbol,
            "comprehensive_analysis",
            session_id,
            analysis_duration,
            total_cost,
        )

        logger.info(
            "✅ [分析完成] 股票分析成功完成",
            extra={
                "stock_symbol": stock_symbol,
                "session_id": session_id,
                "duration": analysis_duration,
                "total_cost": total_cost,
                "analysts_used": analysts,
                "success": True,
                "event_type": "web_analysis_complete",
            },
        )

        # 保存分析报告到本地和PostgreSQL
        try:
            update_progress("💾 正在保存分析报告...")
            save_analysis_report = getattr(importlib.import_module("web.utils.reports"), "save_analysis_report")
            save_modular_reports_to_results_dir = getattr(
                importlib.import_module("web.utils.reports"),
                "save_modular_reports_to_results_dir",
            )

            # 1. 保存分模块报告到本地目录
            logger.info("📁 [本地保存] 开始保存分模块报告到本地目录")
            local_files = save_modular_reports_to_results_dir(results, stock_symbol)
            if local_files:
                logger.info(f"✅ [本地保存] 已保存 {len(local_files)} 个本地报告文件")
                for module, path in local_files.items():
                    logger.info(f"  - {module}: {path}")
            else:
                logger.warning("⚠️ [本地保存] 本地报告文件保存失败")

            # 2. 保存分析报告到PostgreSQL
            logger.info("🗄️ [PostgreSQL保存] 开始保存分析报告到PostgreSQL")
            save_success = save_analysis_report(stock_symbol=stock_symbol, analysis=results)

            if save_success:
                logger.info("✅ [PostgreSQL保存] 分析报告已成功保存到PostgreSQL")
                update_progress("✅ 分析报告已保存到数据库和本地文件")
            else:
                logger.warning("⚠️ [PostgreSQL保存] PostgreSQL报告保存失败")
                if local_files:
                    update_progress("✅ 本地报告已保存，但数据库保存失败")
                else:
                    update_progress("⚠️ 报告保存失败，但分析已完成")

        except Exception as save_error:
            logger.error(f"❌ [报告保存] 保存分析报告时发生错误: {str(save_error)}")
            update_progress("⚠️ 报告保存出错，但分析已完成")

        update_progress("✅ 分析成功完成！")
        return results

    except Exception as e:
        # 记录分析失败的详细日志
        analysis_duration = time.time() - analysis_start_time

        logger_manager.log_module_error(
            logger,
            "comprehensive_analysis",
            stock_symbol,
            session_id,
            analysis_duration,
            str(e),
        )

        logger.error(
            "❌ [分析失败] 股票分析执行失败",
            extra={
                "stock_symbol": stock_symbol,
                "session_id": session_id,
                "duration": analysis_duration,
                "error": str(e),
                "error_type": type(e).__name__,
                "analysts_used": analysts,
                "success": False,
                "event_type": "web_analysis_error",
            },
            exc_info=True,
        )

        # 如果真实分析失败，返回错误信息而不是误导性演示数据
        return {
            "stock_symbol": stock_symbol,
            "analysis_date": analysis_date,
            "analysts": analysts,
            "research_depth": research_depth,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "state": {},  # 空状态，将显示占位符
            "decision": {},  # 空决策
            "success": False,
            "error": str(e),
            "is_demo": False,
            "error_reason": f"分析失败: {str(e)}",
        }
