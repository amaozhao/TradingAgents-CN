from .common import importlib, render_sidebar_logout, st


def render_sidebar_controls():
    default_show_guide = not (
        st.session_state.get("analysis_running", False)
        or st.session_state.get("analysis") is not None
    )
    if "user_set_guide_preference" not in st.session_state:
        st.session_state.user_set_guide_preference = False
        st.session_state.show_guide_preference = default_show_guide
    show_guide = st.sidebar.checkbox(
        "📖 显示使用指南",
        value=st.session_state.get("show_guide_preference", default_show_guide),
        help="显示/隐藏右侧使用指南",
        key="guide_checkbox",
    )
    if show_guide != st.session_state.get("show_guide_preference", default_show_guide):
        st.session_state.user_set_guide_preference = True
        st.session_state.show_guide_preference = show_guide
    st.sidebar.markdown("---")
    if st.sidebar.button(
        "🧹 清理分析状态", help="清理僵尸分析状态，解决页面持续刷新问题"
    ):
        # 清理session state
        st.session_state.analysis_running = False
        st.session_state.current_analysis_id = None
        st.session_state.analysis = None

        # 清理所有自动刷新状态
        keys_to_remove = []
        for key in st.session_state.keys():
            if "auto_refresh" in key:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del st.session_state[key]

        # 清理死亡线程
        cleanup_dead_analysis_threads = getattr(
            importlib.import_module("utils.threads"), "cleanup_dead_analysis_threads"
        )
        cleanup_dead_analysis_threads()

        st.sidebar.success("✅ 分析状态已清理")
        st.rerun()
    render_sidebar_logout()
    return show_guide


def get_content_columns(show_guide):
    if show_guide:
        col1, col2 = st.columns([2, 1])
    else:
        col1 = st.container()
        col2 = None
    return col1, col2


def render_usage_guide(show_guide, col2):
    if show_guide and col2 is not None:
        with col2:
            st.markdown("### ℹ️ 使用指南")

            # 快速开始指南
            with st.expander("🎯 快速开始", expanded=True):
                st.markdown("""
                ### 📋 操作步骤

                1. **输入股票代码**
                   - A股示例: `000001` (平安银行), `600519` (贵州茅台), `000858` (五粮液)
                   - 美股示例: `AAPL` (苹果), `TSLA` (特斯拉), `MSFT` (微软)
                   - 港股示例: `00700` (腾讯), `09988` (阿里巴巴)

                   ⚠️ **重要提示**: 输入股票代码后，请按 **回车键** 确认输入！

                2. **选择分析日期**
                   - 默认为今天
                   - 可选择历史日期进行回测分析

                3. **选择分析师团队**
                   - 至少选择一个分析师
                   - 建议选择多个分析师获得全面分析

                4. **设置研究深度**
                   - 1-2级: 快速概览
                   - 3级: 标准分析 (推荐)
                   - 4-5级: 深度研究

                5. **点击开始分析**
                   - 等待AI分析完成
                   - 查看详细分析报告

                ### 💡 使用技巧

                - **A股默认**: 系统默认分析A股，无需特殊设置
                - **代码格式**: A股使用6位数字代码 (如 `000001`)
                - **实时数据**: 获取最新的市场数据和新闻
                - **多维分析**: 结合技术面、基本面、情绪面分析
                """)

            # 分析师说明
            with st.expander("👥 分析师团队说明"):
                st.markdown("""
                ### 🎯 专业分析师团队

                - **📈 市场分析师**:
                  - 技术指标分析 (K线、均线、MACD等)
                  - 价格趋势预测
                  - 支撑阻力位分析

                - **💭 社交媒体分析师**:
                  - 投资者情绪监测
                  - 社交媒体热度分析
                  - 市场情绪指标

                - **📰 新闻分析师**:
                  - 重大新闻事件影响
                  - 政策解读分析
                  - 行业动态跟踪

                - **💰 基本面分析师**:
                  - 财务报表分析
                  - 估值模型计算
                  - 行业对比分析
                  - 盈利能力评估

                💡 **建议**: 选择多个分析师可获得更全面的投资建议
                """)

            # 模型选择说明
            with st.expander("🧠 AI模型说明"):
                st.markdown("""
                ### 🤖 智能模型选择

                - **qwen-turbo**:
                  - 快速响应，适合快速查询
                  - 成本较低，适合频繁使用
                  - 响应时间: 2-5秒

                - **qwen-plus**:
                  - 平衡性能，推荐日常使用 ⭐
                  - 准确性与速度兼顾
                  - 响应时间: 5-10秒

                - **qwen-max**:
                  - 最强性能，适合深度分析
                  - 最高准确性和分析深度
                  - 响应时间: 10-20秒

                💡 **推荐**: 日常分析使用 `qwen-plus`，重要决策使用 `qwen-max`
                """)

            # 常见问题
            with st.expander("❓ 常见问题"):
                st.markdown("""
                ### 🔍 常见问题解答

                **Q: 为什么输入股票代码没有反应？**
                A: 请确保输入代码后按 **回车键** 确认，这是Streamlit的默认行为。

                **Q: A股代码格式是什么？**
                A: A股使用6位数字代码，如 `000001`、`600519`、`000858` 等。

                **Q: 分析需要多长时间？**
                A: 根据研究深度和模型选择，通常需要30秒到2分钟不等。

                **Q: 可以分析港股吗？**
                A: 可以，输入5位港股代码，如 `00700`、`09988` 等。

                **Q: 历史数据可以追溯多久？**
                A: 通常可以获取近5年的历史数据进行分析。
                """)

            # 风险提示
            st.warning("""
            ⚠️ **投资风险提示**

            - 本系统提供的分析结果仅供参考，不构成投资建议
            - 投资有风险，入市需谨慎，请理性投资
            - 请结合多方信息和专业建议进行投资决策
            - 重大投资决策建议咨询专业的投资顾问
            - AI分析存在局限性，市场变化难以完全预测
            """)

        # 显示系统状态
        if st.session_state.last_analysis_time:
            st.info(
                f"🕒 上次分析时间: {st.session_state.last_analysis_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
