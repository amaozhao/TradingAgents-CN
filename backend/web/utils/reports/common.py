from app.utils.reports import reports

from .imports import (
    DOCKER_ADAPTER_AVAILABLE,
    POSTGRES_REPORT_AVAILABLE,
    Any,
    Dict,
    datetime,
    get_docker_status_info,
    importlib,
    json,
    logger,
    postgres_report_manager,
    settings,
    st,
)


def _format_team_decision_content(content: Dict[str, Any], module_key: str) -> str:
    title = "研究团队决策" if module_key == "investment_debate_state" else "风险管理团队决策"
    lines = [f"## {title}", ""]
    for key, value in content.items():
        heading = key.replace("_", " ").title()
        lines.extend([f"### {heading}", "", str(value), ""])
    return "\n".join(lines)

def save_modular_reports_to_results_dir(results: Dict[str, Any], stock_symbol: str) -> Dict[str, str]:
    """保存分模块报告到results目录（CLI版本格式）"""
    try:
        os = importlib.import_module("os")
        Path = getattr(importlib.import_module("pathlib"), "Path")

        # 获取项目根目录
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent

        # 获取results目录配置
        results_dir_env = settings.TRADING_AGENTS_RESULTS_DIR
        if results_dir_env:
            if not os.path.isabs(results_dir_env):
                results_dir = project_root / results_dir_env
            else:
                results_dir = Path(results_dir_env)
        else:
            results_dir = project_root / "results"

        # 创建股票专用目录
        analysis_date = datetime.now().strftime("%Y-%m-%d")
        stock_dir = results_dir / stock_symbol / analysis_date
        reports_dir = stock_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # 创建message_tool.log文件
        log_file = stock_dir / "message_tool.log"
        log_file.touch(exist_ok=True)

        state = results.get("state", {})
        saved_files = {}

        # 定义报告模块映射（与CLI版本保持一致）
        report_modules = {
            "market_report": {
                "filename": "market_report.md",
                "title": f"{stock_symbol} 股票技术分析报告",
                "state_key": "market_report",
            },
            "sentiment_report": {
                "filename": "sentiment_report.md",
                "title": f"{stock_symbol} 市场情绪分析报告",
                "state_key": "sentiment_report",
            },
            "news_report": {
                "filename": "news_report.md",
                "title": f"{stock_symbol} 新闻事件分析报告",
                "state_key": "news_report",
            },
            "fundamentals_report": {
                "filename": "fundamentals_report.md",
                "title": f"{stock_symbol} 基本面分析报告",
                "state_key": "fundamentals_report",
            },
            "investment_plan": {
                "filename": "investment_plan.md",
                "title": f"{stock_symbol} 投资决策报告",
                "state_key": "investment_plan",
            },
            "trader_investment_plan": {
                "filename": "trader_investment_plan.md",
                "title": f"{stock_symbol} 交易计划报告",
                "state_key": "trader_investment_plan",
            },
            "final_trade_decision": {
                "filename": "final_trade_decision.md",
                "title": f"{stock_symbol} 最终投资决策",
                "state_key": "final_trade_decision",
            },
            # 添加团队决策报告模块
            "investment_debate_state": {
                "filename": "research_team_decision.md",
                "title": f"{stock_symbol} 研究团队决策报告",
                "state_key": "investment_debate_state",
            },
            "risk_debate_state": {
                "filename": "risk_management_decision.md",
                "title": f"{stock_symbol} 风险管理团队决策报告",
                "state_key": "risk_debate_state",
            },
        }

        # 生成各个模块的报告文件
        for module_key, module_info in report_modules.items():
            content = state.get(module_info["state_key"])

            if content:
                # 生成模块报告内容
                if isinstance(content, str):
                    # 检查内容是否已经包含标题，避免重复添加
                    if content.strip().startswith("#"):
                        report_content = content
                    else:
                        report_content = f"# {module_info['title']}\n\n{content}"
                elif isinstance(content, dict):
                    report_content = f"# {module_info['title']}\n\n"
                    # 特殊处理团队决策报告的字典结构
                    if module_key in ["investment_debate_state", "risk_debate_state"]:
                        report_content += _format_team_decision_content(content, module_key)
                    else:
                        for sub_key, sub_value in content.items():
                            report_content += f"## {sub_key.replace('_', ' ').title()}\n\n{sub_value}\n\n"
                else:
                    report_content = f"# {module_info['title']}\n\n{str(content)}"

                # 保存文件
                file_path = reports_dir / module_info["filename"]
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(report_content)

                saved_files[module_key] = str(file_path)
                logger.info(f"✅ 保存模块报告: {file_path}")

        # 如果有决策信息，也保存最终决策报告
        decision = results.get("decision", {})
        if decision:
            decision_content = f"# {stock_symbol} 最终投资决策\n\n"

            if isinstance(decision, dict):
                decision_content += "## 投资建议\n\n"
                decision_content += f"**行动**: {decision.get('action', 'N/A')}\n\n"
                decision_content += f"**置信度**: {decision.get('confidence', 0):.1%}\n\n"
                decision_content += f"**风险评分**: {decision.get('risk_score', 0):.1%}\n\n"
                decision_content += f"**目标价位**: {decision.get('target_price', 'N/A')}\n\n"
                decision_content += f"## 分析推理\n\n{decision.get('reasoning', '暂无分析推理')}\n\n"
            else:
                decision_content += f"{str(decision)}\n\n"

            decision_file = reports_dir / "final_trade_decision.md"
            with open(decision_file, "w", encoding="utf-8") as f:
                f.write(decision_content)

            saved_files["final_trade_decision"] = str(decision_file)
            logger.info(f"✅ 保存最终决策: {decision_file}")

        # 保存分析元数据文件，包含研究深度等信息
        metadata = {
            "stock_symbol": stock_symbol,
            "analysis_date": analysis_date,
            "timestamp": datetime.now().isoformat(),
            "research_depth": results.get("research_depth", 1),
            "analysts": results.get("analysts", []),
            "status": "completed",
            "reports_count": len(saved_files),
            "report_types": list(saved_files.keys()),
        }

        metadata_file = reports_dir.parent / "analysis_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 保存分析元数据: {metadata_file}")
        logger.info(f"✅ 分模块报告保存完成，共保存 {len(saved_files)} 个文件")
        logger.info(f"📁 保存目录: {os.path.normpath(str(reports_dir))}")

        # 同时保存到PostgreSQL document store
        logger.info("🔍 [PostgreSQL调试] 开始PostgreSQL保存流程")
        logger.info(f"🔍 [PostgreSQL调试] POSTGRES_REPORT_AVAILABLE: {POSTGRES_REPORT_AVAILABLE}")
        logger.info(f"🔍 [PostgreSQL调试] postgres_report_manager存在: {postgres_report_manager is not None}")

        if POSTGRES_REPORT_AVAILABLE and postgres_report_manager:
            logger.info(f"🔍 [PostgreSQL调试] PostgreSQL报告管理器连接状态: {postgres_report_manager.connected}")
            try:
                # 收集所有报告内容
                reports_content = {}

                logger.info(f"🔍 [PostgreSQL调试] 开始读取 {len(saved_files)} 个报告文件")
                # 读取已保存的文件内容
                for module_key, file_path in saved_files.items():
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            reports_content[module_key] = content
                            logger.info(f"🔍 [PostgreSQL调试] 成功读取 {module_key}: {len(content)} 字符")
                    except Exception as e:
                        logger.warning(f"⚠️ 读取报告文件失败 {file_path}: {e}")

                # 保存到PostgreSQL document store
                if reports_content:
                    logger.info(
                        f"🔍 [PostgreSQL调试] 准备保存到PostgreSQL document store，报告数量: {len(reports_content)}"
                    )
                    logger.info(f"🔍 [PostgreSQL调试] 报告类型: {list(reports_content.keys())}")

                    success = postgres_report_manager.save_analysis_report(
                        stock_symbol=stock_symbol,
                        analysis=results,
                        reports=reports_content,
                    )

                    if success:
                        logger.info("✅ 分析报告已同时保存到PostgreSQL document store")
                    else:
                        logger.warning("⚠️ PostgreSQL保存失败，但文件保存成功")
                else:
                    logger.warning("⚠️ 没有报告内容可保存到PostgreSQL document store")

            except Exception as e:
                logger.error(f"❌ PostgreSQL保存过程出错: {e}")
                traceback = importlib.import_module("traceback")
                logger.error(f"❌ PostgreSQL保存详细错误: {traceback.format_exc()}")
                # 不影响文件保存的成功返回
        else:
            logger.warning(
                f"⚠️ PostgreSQL保存跳过 - AVAILABLE: {POSTGRES_REPORT_AVAILABLE}, Manager: {postgres_report_manager is not None}"
            )

        return saved_files

    except Exception as e:
        logger.error(f"❌ 保存分模块报告失败: {e}")
        traceback = importlib.import_module("traceback")
        logger.error(f"❌ 详细错误: {traceback.format_exc()}")
        return {}


def save_report_to_results_dir(content: bytes, filename: str, stock_symbol: str) -> str:
    """保存报告到results目录"""
    try:
        os = importlib.import_module("os")
        Path = getattr(importlib.import_module("pathlib"), "Path")

        # 获取项目根目录（Web应用在web/子目录中运行）
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent  # web/utils/reports.py -> 项目根目录

        # 获取results目录配置
        results_dir_env = settings.TRADING_AGENTS_RESULTS_DIR
        if results_dir_env:
            # 如果环境变量是相对路径，相对于项目根目录解析
            if not os.path.isabs(results_dir_env):
                results_dir = project_root / results_dir_env
            else:
                results_dir = Path(results_dir_env)
        else:
            # 默认使用项目根目录下的results
            results_dir = project_root / "results"

        # 创建股票专用目录
        analysis_date = datetime.now().strftime("%Y-%m-%d")
        stock_dir = results_dir / stock_symbol / analysis_date / "reports"
        stock_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件
        file_path = stock_dir / filename
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"✅ 报告已保存到: {file_path}")
        logger.info(f"📁 项目根目录: {project_root}")
        logger.info(f"📁 Results目录: {results_dir}")
        logger.info(f"📁 环境变量TRADING_AGENTS_RESULTS_DIR: {results_dir_env}")

        return str(file_path)

    except Exception as e:
        logger.error(f"❌ 保存报告到results目录失败: {e}")
        traceback = importlib.import_module("traceback")
        logger.error(f"❌ 详细错误: {traceback.format_exc()}")
        return ""


def render_export_buttons(results: Dict[str, Any]):
    """渲染导出按钮"""

    if not results:
        return

    st.markdown("---")
    st.subheader("📤 导出报告")

    # 检查导出功能是否可用
    if not reports.export_available:
        st.warning("⚠️ 导出功能需要安装额外依赖包")
        st.code("pip install pypandoc markdown")
        return

    # 检查pandoc是否可用
    if not reports.pandoc_available:
        st.warning("⚠️ Word和PDF导出需要pandoc工具")
        st.info("💡 您仍可以使用Markdown格式导出")

    # 显示Docker环境状态
    if reports.is_docker:
        if DOCKER_ADAPTER_AVAILABLE:
            docker_status = get_docker_status_info()
            if docker_status["dependencies_ok"] and docker_status["pdf_test_ok"]:
                st.success("🐳 Docker环境PDF支持已启用")
            else:
                st.warning(f"🐳 Docker环境PDF支持异常: {docker_status['dependency_message']}")
        else:
            st.warning("🐳 Docker环境检测到，但适配器不可用")

        with st.expander("📖 如何安装pandoc"):
            st.markdown("""
            **Windows用户:**
            ```bash
            # 使用Chocolatey (推荐)
            choco install pandoc

            # 或下载安装包
            # https://github.com/jgm/pandoc/releases
            ```

            **或者使用Python自动下载:**
            ```python
            import pypandoc

            pypandoc.download_pandoc()
            ```
            """)

        # 在Docker环境下，即使pandoc有问题也显示所有按钮，让用户尝试
        pass

    # 生成文件名
    stock_symbol = results.get("stock_symbol", "analysis")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📄 导出 Markdown", help="导出为Markdown格式"):
            logger.info(f"🖱️ [EXPORT] 用户点击Markdown导出按钮 - 股票: {stock_symbol}")
            logger.info(f"🖱️ 用户点击Markdown导出按钮 - 股票: {stock_symbol}")
            # 1. 保存分模块报告（CLI格式）
            logger.info("📁 开始保存分模块报告（CLI格式）...")
            modular_files = save_modular_reports_to_results_dir(results, stock_symbol)

            # 2. 生成汇总报告（下载用）
            content = reports.export_report(results, "markdown")
            if content:
                filename = f"{stock_symbol}_analysis_{timestamp}.md"
                logger.info(f"✅ [EXPORT] Markdown导出成功，文件名: {filename}")
                logger.info(f"✅ Markdown导出成功，文件名: {filename}")

                # 3. 保存汇总报告到results目录
                saved_path = save_report_to_results_dir(content, filename, stock_symbol)

                # 4. 显示保存结果
                if modular_files and saved_path:
                    st.success(f"✅ 已保存 {len(modular_files)} 个分模块报告 + 1个汇总报告")
                    with st.expander("📁 查看保存的文件"):
                        st.write("**分模块报告:**")
                        for module, path in modular_files.items():
                            st.write(f"- {module}: `{path}`")
                        st.write("**汇总报告:**")
                        st.write(f"- 汇总报告: `{saved_path}`")
                elif saved_path:
                    st.success(f"✅ 汇总报告已保存到: {saved_path}")

                st.download_button(
                    label="📥 下载 Markdown",
                    data=content,
                    file_name=filename,
                    mime="text/markdown",
                )
            else:
                logger.error("❌ [EXPORT] Markdown导出失败，content为空")
                logger.error("❌ Markdown导出失败，content为空")

    with col2:
        if st.button("📝 导出 Word", help="导出为Word文档格式"):
            logger.info(f"🖱️ [EXPORT] 用户点击Word导出按钮 - 股票: {stock_symbol}")
            logger.info(f"🖱️ 用户点击Word导出按钮 - 股票: {stock_symbol}")
            with st.spinner("正在生成Word文档，请稍候..."):
                try:
                    logger.info("🔄 [EXPORT] 开始Word导出流程...")
                    logger.info("🔄 开始Word导出流程...")

                    # 1. 保存分模块报告（CLI格式）
                    logger.info("📁 开始保存分模块报告（CLI格式）...")
                    modular_files = save_modular_reports_to_results_dir(results, stock_symbol)

                    # 2. 生成Word汇总报告
                    content = reports.export_report(results, "docx")
                    if content:
                        filename = f"{stock_symbol}_analysis_{timestamp}.docx"
                        logger.info(f"✅ [EXPORT] Word导出成功，文件名: {filename}, 大小: {len(content)} 字节")
                        logger.info(f"✅ Word导出成功，文件名: {filename}, 大小: {len(content)} 字节")

                        # 3. 保存Word汇总报告到results目录
                        saved_path = save_report_to_results_dir(content, filename, stock_symbol)

                        # 4. 显示保存结果
                        if modular_files and saved_path:
                            st.success(f"✅ 已保存 {len(modular_files)} 个分模块报告 + 1个Word汇总报告")
                            with st.expander("📁 查看保存的文件"):
                                st.write("**分模块报告:**")
                                for module, path in modular_files.items():
                                    st.write(f"- {module}: `{path}`")
                                st.write("**Word汇总报告:**")
                                st.write(f"- Word报告: `{saved_path}`")
                        elif saved_path:
                            st.success(f"✅ Word文档已保存到: {saved_path}")
                        else:
                            st.success("✅ Word文档生成成功！")

                        st.download_button(
                            label="📥 下载 Word",
                            data=content,
                            file_name=filename,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    else:
                        logger.error("❌ [EXPORT] Word导出失败，content为空")
                        logger.error("❌ Word导出失败，content为空")
                        st.error("❌ Word文档生成失败")
                except Exception as e:
                    logger.error(f"❌ [EXPORT] Word导出异常: {str(e)}")
                    logger.error(f"❌ Word导出异常: {str(e)}", exc_info=True)
                    st.error(f"❌ Word文档生成失败: {str(e)}")

                    # 显示详细错误信息
                    with st.expander("🔍 查看详细错误信息"):
                        st.text(str(e))

                    # 提供解决方案
                    with st.expander("💡 解决方案"):
                        st.markdown("""
                        **Word导出需要pandoc工具，请检查:**

                        1. **Docker环境**: 重新构建镜像确保包含pandoc
                        2. **本地环境**: 安装pandoc
                        ```bash
                        # Windows
                        choco install pandoc

                        # macOS
                        brew install pandoc

                        # Linux
                        sudo apt-get install pandoc
                        ```

                        3. **替代方案**: 使用Markdown格式导出
                        """)

    with col3:
        if st.button("📊 导出 PDF", help="导出为PDF格式 (需要额外工具)"):
            logger.info(f"🖱️ 用户点击PDF导出按钮 - 股票: {stock_symbol}")
            with st.spinner("正在生成PDF，请稍候..."):
                try:
                    logger.info("🔄 开始PDF导出流程...")

                    # 1. 保存分模块报告（CLI格式）
                    logger.info("📁 开始保存分模块报告（CLI格式）...")
                    modular_files = save_modular_reports_to_results_dir(results, stock_symbol)

                    # 2. 生成PDF汇总报告
                    content = reports.export_report(results, "pdf")
                    if content:
                        filename = f"{stock_symbol}_analysis_{timestamp}.pdf"
                        logger.info(f"✅ PDF导出成功，文件名: {filename}, 大小: {len(content)} 字节")

                        # 3. 保存PDF汇总报告到results目录
                        saved_path = save_report_to_results_dir(content, filename, stock_symbol)

                        # 4. 显示保存结果
                        if modular_files and saved_path:
                            st.success(f"✅ 已保存 {len(modular_files)} 个分模块报告 + 1个PDF汇总报告")
                            with st.expander("📁 查看保存的文件"):
                                st.write("**分模块报告:**")
                                for module, path in modular_files.items():
                                    st.write(f"- {module}: `{path}`")
                                st.write("**PDF汇总报告:**")
                                st.write(f"- PDF报告: `{saved_path}`")
                        elif saved_path:
                            st.success(f"✅ PDF已保存到: {saved_path}")
                        else:
                            st.success("✅ PDF生成成功！")

                        st.download_button(
                            label="📥 下载 PDF",
                            data=content,
                            file_name=filename,
                            mime="application/pdf",
                        )
                    else:
                        logger.error("❌ PDF导出失败，content为空")
                        st.error("❌ PDF生成失败")
                except Exception as e:
                    logger.error(f"❌ PDF导出异常: {str(e)}", exc_info=True)
                    st.error("❌ PDF生成失败")

                    # 显示详细错误信息
                    with st.expander("🔍 查看详细错误信息"):
                        st.text(str(e))

                    # 提供解决方案
                    with st.expander("💡 解决方案"):
                        st.markdown("""
                        **PDF导出需要额外的工具，请选择以下方案之一:**

                        **方案1: 安装wkhtmltopdf (推荐)**
                        ```bash
                        # Windows
                        choco install wkhtmltopdf

                        # macOS
                        brew install wkhtmltopdf

                        # Linux
                        sudo apt-get install wkhtmltopdf
                        ```

                        **方案2: 安装LaTeX**
                        ```bash
                        # Windows
                        choco install miktex

                        # macOS
                        brew install mactex

                        # Linux
                        sudo apt-get install texlive-full
                        ```

                        **方案3: 使用替代格式**
                        - 📄 Markdown格式 - 轻量级，兼容性好
                        - 📝 Word格式 - 适合进一步编辑
                        """)

                    # 建议使用其他格式
                    st.info("💡 建议：您可以先使用Markdown或Word格式导出，然后使用其他工具转换为PDF")


def save_analysis_report(stock_symbol: str, analysis: Dict[str, Any], report_content: str = None) -> bool:
    """
    保存分析报告到PostgreSQL document store

    Args:
        stock_symbol: 股票代码
        analysis: 分析结果字典
        report_content: 报告内容（可选，如果不提供则自动生成）

    Returns:
        bool: 保存是否成功
    """
    try:
        if not POSTGRES_REPORT_AVAILABLE or postgres_report_manager is None:
            logger.warning("PostgreSQL报告管理器不可用，无法保存报告")
            return False

        # 如果没有提供报告内容，则生成Markdown报告
        if report_content is None:
            report_content = reports.generate_markdown_report(analysis)

        # 调用PostgreSQL报告管理器保存报告
        # 将报告内容包装成字典格式
        reports_dict = {
            "markdown": report_content,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        success = postgres_report_manager.save_analysis_report(
            stock_symbol=stock_symbol, analysis=analysis, reports=reports_dict
        )

        if success:
            logger.info(f"✅ 分析报告已成功保存到PostgreSQL document store - 股票: {stock_symbol}")
        else:
            logger.error(f"❌ 分析报告保存到PostgreSQL document store失败 - 股票: {stock_symbol}")

        return success

    except Exception as e:
        logger.error(f"❌ 保存分析报告到PostgreSQL document store时发生异常 - 股票: {stock_symbol}, 错误: {str(e)}")
        return False
