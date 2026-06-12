from .imports import (
    POSTGRES_AVAILABLE,
    Dict,
    List,
    Path,
    PostgreSQLReportManager,
    datetime,
    importlib,
    json,
    logger,
    st,
)


def get_analysis_dir() -> Path:
    analysis_dir = Path.cwd() / "data" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    return analysis_dir

def render_detailed_analysis_content(selected_result):
    """渲染详细分析结果内容"""
    st.subheader("📊 完整分析数据")

    # 检查是否有报告数据（支持文件系统和PostgreSQL）
    if "reports" in selected_result and selected_result["reports"]:
        # 显示文件系统中的报告
        reports = selected_result["reports"]

        if not reports:
            st.warning("该分析结果没有可用的报告内容")
            return

        # 调试信息：显示所有可用的报告
        print(f"🔍 [弹窗调试] 数据来源: {selected_result.get('source', '未知')}")
        print(f"🔍 [弹窗调试] 可用报告数量: {len(reports)}")
        print(f"🔍 [弹窗调试] 报告类型: {list(reports.keys())}")

        # 创建标签页显示不同的报告
        report_tabs = list(reports.keys())

        # 为报告名称添加中文标题和图标
        report_display_names = {
            "final_trade_decision": "🎯 最终交易决策",
            "fundamentals_report": "💰 基本面分析",
            "technical_report": "📈 技术面分析",
            "market_sentiment_report": "💭 市场情绪分析",
            "risk_assessment_report": "⚠️ 风险评估",
            "price_target_report": "🎯 目标价格分析",
            "summary_report": "📋 分析摘要",
            "news_analysis_report": "📰 新闻分析",
            "social_media_report": "📱 社交媒体分析",
        }

        # 创建显示名称列表
        tab_names = []
        for report_key in report_tabs:
            display_name = report_display_names.get(report_key, f"📄 {report_key.replace('_', ' ').title()}")
            tab_names.append(display_name)
            print(f"🔍 [弹窗调试] 添加标签: {display_name}")

        print(f"🔍 [弹窗调试] 总标签数: {len(tab_names)}")

        if len(tab_names) == 1:
            # 只有一个报告，直接显示
            st.markdown(f"### {tab_names[0]}")
            st.markdown("---")
            st.markdown(reports[report_tabs[0]])
        else:
            # 多个报告，使用标签页
            tabs = st.tabs(tab_names)

            for i, (tab, report_key) in enumerate(zip(tabs, report_tabs)):
                with tab:
                    st.markdown(reports[report_key])

        return

    # 添加自定义CSS样式美化标签页
    st.markdown(
        """
    <style>
    /* 标签页容器样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f8f9fa;
        padding: 8px;
        border-radius: 10px;
        margin-bottom: 20px;
    }

    /* 单个标签页样式 */
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 8px 16px;
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e1e5e9;
        color: #495057;
        font-weight: 500;
        transition: all 0.3s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    /* 标签页悬停效果 */
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e3f2fd;
        border-color: #2196f3;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(33,150,243,0.2);
    }

    /* 选中的标签页样式 */
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-color: #667eea !important;
        box-shadow: 0 4px 12px rgba(102,126,234,0.3) !important;
        transform: translateY(-2px);
    }

    /* 标签页内容区域 */
    .stTabs [data-baseweb="tab-panel"] {
        padding: 20px;
        background-color: #ffffff;
        border-radius: 10px;
        border: 1px solid #e1e5e9;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    /* 标签页文字样式 */
    .stTabs [data-baseweb="tab"] p {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
    }

    /* 选中标签页的文字样式 */
    .stTabs [aria-selected="true"] p {
        color: white !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # 定义分析模块
    analysis_modules = [
        {
            "key": "market_report",
            "title": "📈 市场技术分析",
            "icon": "📈",
            "description": "技术指标、价格趋势、支撑阻力位分析",
        },
        {
            "key": "fundamentals_report",
            "title": "💰 基本面分析",
            "icon": "💰",
            "description": "财务数据、估值水平、盈利能力分析",
        },
        {
            "key": "sentiment_report",
            "title": "💭 市场情绪分析",
            "icon": "💭",
            "description": "投资者情绪、社交媒体情绪指标",
        },
        {
            "key": "news_report",
            "title": "📰 新闻事件分析",
            "icon": "📰",
            "description": "相关新闻事件、市场动态影响分析",
        },
        {
            "key": "risk_assessment",
            "title": "⚠️ 风险评估",
            "icon": "⚠️",
            "description": "风险因素识别、风险等级评估",
        },
        {
            "key": "investment_plan",
            "title": "📋 投资建议",
            "icon": "📋",
            "description": "具体投资策略、仓位管理建议",
        },
        {
            "key": "investment_debate_state",
            "title": "🔬 研究团队决策",
            "icon": "🔬",
            "description": "多头/空头研究员辩论分析，研究经理综合决策",
        },
        {
            "key": "trader_investment_plan",
            "title": "💼 交易团队计划",
            "icon": "💼",
            "description": "专业交易员制定的具体交易执行计划",
        },
        {
            "key": "risk_debate_state",
            "title": "⚖️ 风险管理团队",
            "icon": "⚖️",
            "description": "激进/保守/中性分析师风险评估，投资组合经理最终决策",
        },
        {
            "key": "final_trade_decision",
            "title": "🎯 最终交易决策",
            "icon": "🎯",
            "description": "综合所有团队分析后的最终投资决策",
        },
    ]

    # 过滤出有数据的模块
    available_modules = []
    for module in analysis_modules:
        if module["key"] in selected_result and selected_result[module["key"]]:
            # 检查字典类型的数据是否有实际内容
            if isinstance(selected_result[module["key"]], dict):
                # 对于字典，检查是否有非空的值
                has_content = any(v for v in selected_result[module["key"]].values() if v)
                if has_content:
                    available_modules.append(module)
            else:
                # 对于字符串或其他类型，直接添加
                available_modules.append(module)

    if not available_modules:
        # 如果没有预定义模块的数据，显示所有可用的分析数据
        st.info("📊 显示完整分析报告数据")

        # 排除一些基础字段，只显示分析相关的数据
        excluded_keys = {
            "analysis_id",
            "timestamp",
            "stock_symbol",
            "analysts",
            "research_depth",
            "status",
            "summary",
            "performance",
            "is_favorite",
            "tags",
            "full_data",
        }

        # 获取所有分析相关的数据
        analysis_data = {}
        for key, value in selected_result.items():
            if key not in excluded_keys and value:
                analysis_data[key] = value

        # 如果有full_data字段，优先使用它
        if "full_data" in selected_result and selected_result["full_data"]:
            full_data = selected_result["full_data"]
            if isinstance(full_data, dict):
                for key, value in full_data.items():
                    if key not in excluded_keys and value:
                        analysis_data[key] = value

        if analysis_data:
            # 创建动态标签页显示所有分析数据
            tab_names = []
            tab_data = []

            for key, value in analysis_data.items():
                # 格式化标签页名称
                tab_name = key.replace("_", " ").title()
                if "report" in key.lower():
                    tab_name = f"📊 {tab_name}"
                elif "analysis" in key.lower():
                    tab_name = f"🔍 {tab_name}"
                elif "decision" in key.lower():
                    tab_name = f"🎯 {tab_name}"
                elif "plan" in key.lower():
                    tab_name = f"📋 {tab_name}"
                else:
                    tab_name = f"📄 {tab_name}"

                tab_names.append(tab_name)
                tab_data.append((key, value))

            # 创建标签页
            tabs = st.tabs(tab_names)

            for i, (tab, (key, value)) in enumerate(zip(tabs, tab_data)):
                with tab:
                    st.markdown(f"## {tab_names[i]}")
                    st.markdown("---")

                    # 根据数据类型显示内容
                    if isinstance(value, str):
                        # 如果是长文本，使用markdown显示
                        if len(value) > 100:
                            st.markdown(value)
                        else:
                            st.write(value)
                    elif isinstance(value, dict):
                        # 字典类型，递归显示
                        for sub_key, sub_value in value.items():
                            if sub_value:
                                st.subheader(sub_key.replace("_", " ").title())
                                if isinstance(sub_value, str):
                                    st.markdown(sub_value)
                                else:
                                    st.write(sub_value)
                    elif isinstance(value, list):
                        # 列表类型
                        for idx, item in enumerate(value):
                            st.subheader(f"项目 {idx + 1}")
                            if isinstance(item, str):
                                st.markdown(item)
                            else:
                                st.write(item)
                    else:
                        # 其他类型直接显示
                        st.write(value)
        else:
            # 如果真的没有任何分析数据，显示原始JSON
            st.warning("📊 该分析结果暂无详细报告数据")
            with st.expander("查看原始数据"):
                st.json(selected_result)
        return

    # 只为有数据的模块创建标签页
    tabs = st.tabs([module["title"] for module in available_modules])

    for i, (tab, module) in enumerate(zip(tabs, available_modules)):
        with tab:
            # 在内容区域显示图标和描述
            st.markdown(f"## {module['icon']} {module['title']}")
            st.markdown(f"*{module['description']}*")
            st.markdown("---")

            # 格式化显示内容
            content = selected_result[module["key"]]
            if isinstance(content, str):
                st.markdown(content)
            elif isinstance(content, dict):
                # 特殊处理团队决策报告的字典结构
                if module["key"] == "investment_debate_state":
                    render_investment_debate_content(content)
                elif module["key"] == "risk_debate_state":
                    render_risk_debate_content(content)
                else:
                    # 普通字典格式化显示
                    for key, value in content.items():
                        if value:  # 只显示非空值
                            st.subheader(key.replace("_", " ").title())
                            if isinstance(value, str):
                                st.markdown(value)
                            else:
                                st.write(value)
            else:
                st.write(content)


def render_investment_debate_content(content):
    """渲染投资辩论内容"""
    if "bull_analyst_report" in content and content["bull_analyst_report"]:
        st.subheader("🐂 多头分析师观点")
        st.markdown(content["bull_analyst_report"])

    if "bear_analyst_report" in content and content["bear_analyst_report"]:
        st.subheader("🐻 空头分析师观点")
        st.markdown(content["bear_analyst_report"])

    if "research_manager_decision" in content and content["research_manager_decision"]:
        st.subheader("👨‍💼 研究经理决策")
        st.markdown(content["research_manager_decision"])


def render_risk_debate_content(content):
    """渲染风险辩论内容"""
    if "aggressive_analyst_report" in content and content["aggressive_analyst_report"]:
        st.subheader("🔥 激进分析师观点")
        st.markdown(content["aggressive_analyst_report"])

    if "conservative_analyst_report" in content and content["conservative_analyst_report"]:
        st.subheader("🛡️ 保守分析师观点")
        st.markdown(content["conservative_analyst_report"])

    if "neutral_analyst_report" in content and content["neutral_analyst_report"]:
        st.subheader("⚖️ 中性分析师观点")
        st.markdown(content["neutral_analyst_report"])

    if "portfolio_manager_decision" in content and content["portfolio_manager_decision"]:
        st.subheader("👨‍💼 投资组合经理决策")
        st.markdown(content["portfolio_manager_decision"])


def save_analysis_result(
    analysis_id: str,
    stock_symbol: str,
    analysts: List[str],
    research_depth: int,
    result_data: Dict,
    status: str = "completed",
):
    """保存分析结果"""
    try:
        safe_serialize = getattr(importlib.import_module("web.utils.progress"), "safe_serialize")

        # 创建结果条目，使用安全序列化
        result_entry = {
            "analysis_id": analysis_id,
            "timestamp": datetime.now().timestamp(),
            "stock_symbol": stock_symbol,
            "analysts": analysts,
            "research_depth": research_depth,
            "status": status,
            "summary": safe_serialize(result_data.get("summary", "")),
            "performance": safe_serialize(result_data.get("performance", {})),
            "full_data": safe_serialize(result_data),
        }

        # 1. 保存到文件系统（保持兼容性）
        results_dir = get_analysis_dir()
        result_file = results_dir / f"analysis_{analysis_id}.json"

        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result_entry, f, ensure_ascii=False, indent=2)

        # 2. 保存到PostgreSQL document store（如果可用）
        if POSTGRES_AVAILABLE:
            try:
                print(f"💾 [PostgreSQL保存] 开始保存分析结果: {analysis_id}")
                postgres_manager = PostgreSQLReportManager()

                # 使用标准的save_analysis_report方法，确保数据结构一致
                analysis = {
                    "stock_symbol": result_entry.get("stock_symbol", ""),
                    "analysts": result_entry.get("analysts", []),
                    "research_depth": result_entry.get("research_depth", 1),
                    "summary": result_entry.get("summary", ""),
                    "model_info": result_entry.get("model_info", "Unknown"),  # 🔥 添加模型信息字段
                }

                # 尝试从文件系统读取报告内容
                reports = {}
                try:
                    # 构建报告目录路径
                    Path = getattr(importlib.import_module("pathlib"), "Path")
                    os = importlib.import_module("os")

                    # 获取当前日期
                    current_date = datetime.now().strftime("%Y-%m-%d")

                    # 构建报告路径
                    project_root = Path(__file__).resolve().parents[3]
                    reports_dir = project_root / "data" / "analysis" / stock_symbol / current_date / "reports"

                    # 确保路径在Windows上正确显示（避免双反斜杠）
                    reports_dir_str = os.path.normpath(str(reports_dir))
                    print(f"🔍 [PostgreSQL保存] 查找报告目录: {reports_dir_str}")

                    if reports_dir.exists():
                        # 读取所有报告文件
                        for report_file in reports_dir.glob("*.md"):
                            try:
                                with open(report_file, "r", encoding="utf-8") as f:
                                    content = f.read()
                                    report_name = report_file.stem
                                    reports[report_name] = content
                                    print(f"✅ [PostgreSQL保存] 读取报告: {report_name} ({len(content)} 字符)")
                            except Exception as e:
                                print(f"⚠️ [PostgreSQL保存] 读取报告文件失败 {report_file}: {e}")

                        print(f"📊 [PostgreSQL保存] 共读取 {len(reports)} 个报告文件")
                    else:
                        print(f"⚠️ [PostgreSQL保存] 报告目录不存在: {reports_dir_str}")

                except Exception as e:
                    print(f"⚠️ [PostgreSQL保存] 读取报告文件异常: {e}")
                    reports = {}

                # 使用标准保存方法，确保字段结构一致
                success = postgres_manager.save_analysis_report(
                    stock_symbol=result_entry.get("stock_symbol", ""),
                    analysis=analysis,
                    reports=reports,
                )

                if success:
                    print(
                        f"✅ [PostgreSQL保存] 分析结果已保存到PostgreSQL document store: {analysis_id} (包含 {len(reports)} 个报告)"
                    )
                else:
                    print(f"❌ [PostgreSQL保存] 保存失败: {analysis_id}")

            except Exception as e:
                print(f"❌ [PostgreSQL保存] 保存异常: {e}")
                logger.error(f"PostgreSQL保存异常: {e}")

        return True

    except Exception as e:
        print(f"❌ [保存分析结果] 保存失败: {e}")
        logger.error(f"保存分析结果异常: {e}")
        return False


def show_expanded_detail(result):
    """显示展开的详情内容"""

    # 创建详情容器
    with st.container():
        st.markdown("---")
        st.markdown("### 📊 详细分析报告")

        # 检查是否有报告数据
        if "reports" not in result or not result["reports"]:
            # 如果没有reports字段，检查是否有其他分析数据
            if result.get("summary"):
                st.subheader("📝 分析摘要")
                st.markdown(result["summary"])

            # 检查是否有full_data中的报告
            if "full_data" in result and result["full_data"]:
                full_data = result["full_data"]
                if isinstance(full_data, dict):
                    # 显示full_data中的分析内容
                    analysis_fields = [
                        ("market_report", "📈 市场分析"),
                        ("fundamentals_report", "💰 基本面分析"),
                        ("sentiment_report", "💭 情感分析"),
                        ("news_report", "📰 新闻分析"),
                        ("risk_assessment", "⚠️ 风险评估"),
                        ("investment_plan", "📋 投资建议"),
                        ("final_trade_decision", "🎯 最终决策"),
                    ]

                    available_reports = []
                    for field_key, field_name in analysis_fields:
                        if field_key in full_data and full_data[field_key]:
                            available_reports.append((field_key, field_name, full_data[field_key]))

                    if available_reports:
                        # 创建标签页显示分析内容
                        tab_names = [name for _, name, _ in available_reports]
                        tabs = st.tabs(tab_names)

                        for i, (tab, (field_key, field_name, content)) in enumerate(zip(tabs, available_reports)):
                            with tab:
                                if isinstance(content, str):
                                    st.markdown(content)
                                elif isinstance(content, dict):
                                    for key, value in content.items():
                                        if value:
                                            st.subheader(key.replace("_", " ").title())
                                            st.markdown(str(value))
                                else:
                                    st.write(content)
                    else:
                        st.info("暂无详细分析报告")
                else:
                    st.info("暂无详细分析报告")
            else:
                st.info("暂无详细分析报告")
            return

        # 获取报告数据
        reports = result["reports"]

        # 为报告名称添加中文标题和图标
        report_display_names = {
            "final_trade_decision": "🎯 最终交易决策",
            "fundamentals_report": "💰 基本面分析",
            "technical_report": "📈 技术面分析",
            "market_sentiment_report": "💭 市场情绪分析",
            "risk_assessment_report": "⚠️ 风险评估",
            "price_target_report": "🎯 目标价格分析",
            "summary_report": "📋 分析摘要",
            "news_analysis_report": "📰 新闻分析",
            "news_report": "📰 新闻分析",
            "market_report": "📈 市场分析",
            "social_media_report": "📱 社交媒体分析",
            "bull_state": "🐂 多头观点",
            "bear_state": "🐻 空头观点",
            "trader_state": "💼 交易员分析",
            "invest_judge_state": "⚖️ 投资判断",
            "research_team_state": "🔬 研究团队观点",
            "risk_debate_state": "⚠️ 风险管理讨论",
            "research_team_decision": "🔬 研究团队决策",
            "risk_management_decision": "🛡️ 风险管理决策",
            "investment_plan": "📋 投资计划",
            "trader_investment_plan": "💼 交易员投资计划",
            "investment_debate_state": "💬 投资讨论状态",
        }

        # 创建标签页显示不同的报告
        report_tabs = list(reports.keys())
        tab_names = []
        for report_key in report_tabs:
            display_name = report_display_names.get(report_key, f"📄 {report_key.replace('_', ' ').title()}")
            tab_names.append(display_name)

        if len(tab_names) == 1:
            # 只有一个报告，直接显示内容（不添加额外标题，避免重复）
            report_content = reports[report_tabs[0]]
            # 如果报告内容已经包含标题，直接显示；否则添加标题
            if not report_content.strip().startswith("#"):
                st.markdown(f"### {tab_names[0]}")
                st.markdown("---")
            st.markdown(report_content)
        else:
            # 多个报告，使用标签页
            tabs = st.tabs(tab_names)

            for i, (tab, report_key) in enumerate(zip(tabs, report_tabs)):
                with tab:
                    st.markdown(reports[report_key])

        st.markdown("---")
