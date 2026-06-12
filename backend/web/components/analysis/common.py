from .base import render_detailed_analysis_content
from .imports import Any, Dict, List, datetime, go, importlib, json, pd, px, st


def safe_timestamp_to_datetime(value: object) -> datetime:
    """将历史记录中的时间戳兼容转换为 datetime。"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (OSError, OverflowError, ValueError):
            return datetime.fromtimestamp(0)
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.fromtimestamp(0)
    return datetime.fromtimestamp(0)


def _tags_path():
    Path = getattr(importlib.import_module("pathlib"), "Path")
    return Path.cwd() / "data" / "analysis_tags.json"


def load_tags() -> Dict[str, List[str]]:
    path = _tags_path()
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    result: Dict[str, List[str]] = {}
    for key, value in loaded.items():
        if isinstance(key, str) and isinstance(value, list):
            result[key] = [str(item) for item in value]
    return result


def _save_tags(tags: Dict[str, List[str]]) -> None:
    path = _tags_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")


def add_tag_to_analysis(analysis_id: str, tag: str) -> None:
    tags = load_tags()
    values = tags.setdefault(analysis_id, [])
    if tag not in values:
        values.append(tag)
        _save_tags(tags)


def remove_tag_from_analysis(analysis_id: str, tag: str) -> None:
    tags = load_tags()
    values = tags.get(analysis_id)
    if not values or tag not in values:
        return
    values.remove(tag)
    if values:
        tags[analysis_id] = values
    else:
        tags.pop(analysis_id, None)
    _save_tags(tags)

def _render_results_comparison_legacy(results: List[Dict[str, Any]]):
    """渲染结果对比功能"""

    st.subheader("🔄 分析结果对比")

    if len(results) < 2:
        st.warning("至少需要2个分析结果才能进行对比")
        return

    # 选择要对比的结果
    col1, col2 = st.columns(2)

    result_options = []
    for i, result in enumerate(results[:20]):  # 限制选项数量
        option = f"{result.get('stock_symbol', 'unknown')} - {safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%m-%d %H:%M')}"
        result_options.append((option, i))

    with col1:
        st.write("**选择结果A**")
        selected_a = st.selectbox("结果A", result_options, format_func=lambda x: x[0], key="compare_a")
        result_a = results[selected_a[1]]

    with col2:
        st.write("**选择结果B**")
        selected_b = st.selectbox("结果B", result_options, format_func=lambda x: x[0], key="compare_b")
        result_b = results[selected_b[1]]

    if selected_a[1] == selected_b[1]:
        st.warning("请选择不同的分析结果进行对比")
        return

    # 对比显示
    st.markdown("---")

    # 基本信息对比
    st.subheader("📋 基本信息对比")

    comparison_data = {
        "项目": ["股票代码", "分析时间", "分析师", "研究深度", "状态"],
        "结果A": [
            result_a.get("stock_symbol", "unknown"),
            safe_timestamp_to_datetime(result_a.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M"),
            ", ".join(result_a.get("analysts", [])),
            str(result_a.get("research_depth", "unknown")),
            "完成" if result_a.get("status") == "completed" else "失败",
        ],
        "结果B": [
            result_b.get("stock_symbol", "unknown"),
            safe_timestamp_to_datetime(result_b.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M"),
            ", ".join(result_b.get("analysts", [])),
            str(result_b.get("research_depth", "unknown")),
            "完成" if result_b.get("status") == "completed" else "失败",
        ],
    }

    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True)

    # 摘要对比
    if result_a.get("summary") or result_b.get("summary"):
        st.subheader("📝 分析摘要对比")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**结果A摘要**")
            st.text_area(
                "",
                value=result_a.get("summary", "暂无摘要"),
                height=200,
                key="summary_a",
                disabled=True,
            )

        with col2:
            st.write("**结果B摘要**")
            st.text_area(
                "",
                value=result_b.get("summary", "暂无摘要"),
                height=200,
                key="summary_b",
                disabled=True,
            )

    # 性能对比
    perf_a = result_a.get("performance", {})
    perf_b = result_b.get("performance", {})

    if perf_a or perf_b:
        st.subheader("⚡ 性能指标对比")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**结果A性能**")
            if perf_a:
                st.json(perf_a)
            else:
                st.info("暂无性能数据")

        with col2:
            st.write("**结果B性能**")
            if perf_b:
                st.json(perf_b)
            else:
                st.info("暂无性能数据")


def render_results_charts(results: List[Dict[str, Any]]):
    """渲染分析结果统计图表"""

    st.subheader("📈 统计图表")

    # 按股票统计
    st.subheader("📊 按股票统计")
    stock_counts = {}
    for result in results:
        stock = result.get("stock_symbol", "unknown")
        stock_counts[stock] = stock_counts.get(stock, 0) + 1

    if stock_counts:
        # 只显示前10个最常分析的股票
        top_stocks = sorted(stock_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        stocks = [item[0] for item in top_stocks]
        counts = [item[1] for item in top_stocks]

        fig_bar = px.bar(
            x=stocks,
            y=counts,
            title="最常分析的股票 (前10名)",
            labels={"x": "股票代码", "y": "分析次数"},
            color=counts,
            color_continuous_scale="viridis",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # 按时间统计
    st.subheader("📅 每日分析趋势")
    daily_results = {}
    for result in results:
        date_str = safe_timestamp_to_datetime(result.get("timestamp", 0)).strftime("%Y-%m-%d")
        daily_results[date_str] = daily_results.get(date_str, 0) + 1

    if daily_results:
        dates = sorted(daily_results.keys())
        counts = [daily_results[date] for date in dates]

        fig_line = go.Figure()
        fig_line.add_trace(
            go.Scatter(
                x=dates,
                y=counts,
                mode="lines+markers",
                name="每日分析数",
                line=dict(color="#2E8B57", width=3),
                marker=dict(size=8, color="#FF6B6B"),
                fill="tonexty",
            )
        )
        fig_line.update_layout(
            title="每日分析趋势",
            xaxis_title="日期",
            yaxis_title="分析数量",
            hovermode="x unified",
        )
        st.plotly_chart(fig_line, use_container_width=True)

    # 按分析师类型统计
    st.subheader("👥 分析师使用分布")
    analyst_counts = {}
    for result in results:
        analysts = result.get("analysts", [])
        for analyst in analysts:
            analyst_counts[analyst] = analyst_counts.get(analyst, 0) + 1

    if analyst_counts:
        fig_pie = px.pie(
            values=list(analyst_counts.values()),
            names=list(analyst_counts.keys()),
            title="分析师使用分布",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # 成功率统计
    st.subheader("✅ 分析成功率统计")
    success_data = {"成功": 0, "失败": 0}
    for result in results:
        if result.get("status") == "completed":
            success_data["成功"] += 1
        else:
            success_data["失败"] += 1

    if success_data["成功"] + success_data["失败"] > 0:
        fig_success = px.pie(
            values=list(success_data.values()),
            names=list(success_data.keys()),
            title="分析成功率",
            color_discrete_map={"成功": "#4CAF50", "失败": "#F44336"},
        )
        st.plotly_chart(fig_success, use_container_width=True)

    # 标签使用统计
    tags_data = load_tags()
    if tags_data:
        st.subheader("🏷️ 标签使用统计")
        tag_counts = {}
        for tag_list in tags_data.values():
            for tag in tag_list:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        if tag_counts:
            # 只显示前10个最常用的标签
            top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            tags = [item[0] for item in top_tags]
            counts = [item[1] for item in top_tags]

            fig_tags = px.bar(
                x=tags,
                y=counts,
                title="最常用标签 (前10名)",
                labels={"x": "标签", "y": "使用次数"},
                color=counts,
                color_continuous_scale="plasma",
            )
            fig_tags.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_tags, use_container_width=True)


def render_tags_management(results: List[Dict[str, Any]]):
    """渲染标签管理功能"""

    st.subheader("🏷️ 标签管理")

    # 获取所有标签
    all_tags = set()
    tags_data = load_tags()
    for tag_list in tags_data.values():
        all_tags.update(tag_list)

    # 标签统计
    if all_tags:
        st.write("**现有标签统计**")
        tag_counts = {}
        for tag_list in tags_data.values():
            for tag in tag_list:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # 显示标签云
        col1, col2 = st.columns([2, 1])

        with col1:
            # 创建标签云可视化
            if tag_counts:
                fig = px.bar(
                    x=list(tag_counts.keys()),
                    y=list(tag_counts.values()),
                    title="标签使用频率",
                    labels={"x": "标签", "y": "使用次数"},
                )
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.write("**标签列表**")
            for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
                st.write(f"• {tag} ({count})")

    # 批量标签操作
    st.markdown("---")
    st.write("**批量标签操作**")

    # 选择要操作的结果
    if results:
        selected_results = st.multiselect(
            "选择分析结果",
            options=range(len(results)),
            format_func=lambda i: (
                f"{results[i].get('stock_symbol', 'unknown')} - {safe_timestamp_to_datetime(results[i].get('timestamp', 0)).strftime('%m-%d %H:%M')}"
            ),
            max_selections=10,
        )

        if selected_results:
            col1, col2 = st.columns(2)

            with col1:
                # 添加标签
                new_tag = st.text_input("新标签名称", placeholder="输入标签名称")
                if st.button("➕ 添加标签") and new_tag:
                    for idx in selected_results:
                        analysis_id = results[idx].get("analysis_id", "")
                        if analysis_id:
                            add_tag_to_analysis(analysis_id, new_tag)
                    st.success(f"已为 {len(selected_results)} 个结果添加标签: {new_tag}")
                    st.rerun()

            with col2:
                # 移除标签
                if all_tags:
                    remove_tag = st.selectbox("选择要移除的标签", sorted(all_tags))
                    if st.button("➖ 移除标签") and remove_tag:
                        for idx in selected_results:
                            analysis_id = results[idx].get("analysis_id", "")
                            if analysis_id:
                                remove_tag_from_analysis(analysis_id, remove_tag)
                        st.success(f"已从 {len(selected_results)} 个结果移除标签: {remove_tag}")
                        st.rerun()


def render_results_export(results: List[Dict[str, Any]]):
    """渲染分析结果导出功能"""

    st.subheader("📤 导出分析结果")

    if not results:
        st.warning("没有可导出的分析结果")
        return

    # 导出选项
    export_type = st.selectbox("选择导出内容", ["摘要信息", "完整数据"])
    export_format = st.selectbox("选择导出格式", ["CSV", "JSON", "Excel"])

    if st.button("📥 导出结果"):
        try:
            if export_type == "摘要信息":
                # 导出摘要信息
                summary_data = []
                for result in results:
                    summary_data.append({
                        "分析时间": safe_timestamp_to_datetime(result.get("timestamp", 0)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "股票代码": result.get("stock_symbol", "unknown"),
                        "分析师": ", ".join(result.get("analysts", [])),
                        "研究深度": result.get("research_depth", "unknown"),
                        "状态": result.get("status", "unknown"),
                        "摘要": result.get("summary", "")[:100] + "..."
                        if len(result.get("summary", "")) > 100
                        else result.get("summary", ""),
                    })

                if export_format == "CSV":
                    df = pd.DataFrame(summary_data)
                    csv_data = df.to_csv(index=False, encoding="utf-8-sig")

                    st.download_button(
                        label="下载 CSV 文件",
                        data=csv_data,
                        file_name=f"analysis_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )

                elif export_format == "JSON":
                    json_data = json.dumps(summary_data, ensure_ascii=False, indent=2)

                    st.download_button(
                        label="下载 JSON 文件",
                        data=json_data,
                        file_name=f"analysis_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                    )

                elif export_format == "Excel":
                    df = pd.DataFrame(summary_data)

                    BytesIO = getattr(importlib.import_module("io"), "BytesIO")
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df.to_excel(writer, index=False, sheet_name="分析摘要")

                    excel_data = output.getvalue()

                    st.download_button(
                        label="下载 Excel 文件",
                        data=excel_data,
                        file_name=f"analysis_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

            else:  # 完整数据
                if export_format == "JSON":
                    json_data = json.dumps(results, ensure_ascii=False, indent=2)

                    st.download_button(
                        label="下载完整数据 JSON 文件",
                        data=json_data,
                        file_name=f"analysis_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                    )
                else:
                    st.warning("完整数据只支持 JSON 格式导出")

            st.success(f"✅ {export_format} 文件准备完成，请点击下载按钮")

        except Exception as e:
            st.error(f"❌ 导出失败: {e}")


def render_results_comparison(results: List[Dict[str, Any]]):
    """渲染分析结果对比"""

    st.subheader("🔍 分析结果对比")

    if len(results) < 2:
        st.info("至少需要2个分析结果才能进行对比")
        return

    # 选择要对比的分析结果
    st.write("**选择要对比的分析结果：**")

    col1, col2 = st.columns(2)

    # 准备选项
    result_options = []
    for i, result in enumerate(results[:20]):  # 限制前20个
        option = f"{result.get('stock_symbol', 'unknown')} - {safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%m-%d %H:%M')}"
        result_options.append((option, i))

    with col1:
        st.write("**分析结果 A**")
        selected_a = st.selectbox(
            "选择第一个分析结果",
            result_options,
            format_func=lambda x: x[0],
            key="compare_a",
        )
        result_a = results[selected_a[1]]

    with col2:
        st.write("**分析结果 B**")
        selected_b = st.selectbox(
            "选择第二个分析结果",
            result_options,
            format_func=lambda x: x[0],
            key="compare_b",
        )
        result_b = results[selected_b[1]]

    if selected_a[1] == selected_b[1]:
        st.warning("请选择不同的分析结果进行对比")
        return

    # 基本信息对比
    st.subheader("📊 基本信息对比")

    comparison_data = {
        "项目": ["股票代码", "分析时间", "分析师数量", "研究深度", "状态", "标签数量"],
        "分析结果 A": [
            result_a.get("stock_symbol", "unknown"),
            safe_timestamp_to_datetime(result_a.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M"),
            len(result_a.get("analysts", [])),
            result_a.get("research_depth", "unknown"),
            "✅ 完成" if result_a.get("status") == "completed" else "❌ 失败",
            len(result_a.get("tags", [])),
        ],
        "分析结果 B": [
            result_b.get("stock_symbol", "unknown"),
            safe_timestamp_to_datetime(result_b.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M"),
            len(result_b.get("analysts", [])),
            result_b.get("research_depth", "unknown"),
            "✅ 完成" if result_b.get("status") == "completed" else "❌ 失败",
            len(result_b.get("tags", [])),
        ],
    }

    pd = importlib.import_module("pandas")
    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True)

    # 性能指标对比
    perf_a = result_a.get("performance", {})
    perf_b = result_b.get("performance", {})

    if perf_a or perf_b:
        st.subheader("⚡ 性能指标对比")

        # 合并所有性能指标键
        all_perf_keys = set(perf_a.keys()) | set(perf_b.keys())

        if all_perf_keys:
            perf_comparison = {
                "指标": list(all_perf_keys),
                "分析结果 A": [perf_a.get(key, "N/A") for key in all_perf_keys],
                "分析结果 B": [perf_b.get(key, "N/A") for key in all_perf_keys],
            }

            df_perf = pd.DataFrame(perf_comparison)
            st.dataframe(df_perf, use_container_width=True)

    # 标签对比
    tags_a = set(result_a.get("tags", []))
    tags_b = set(result_b.get("tags", []))

    if tags_a or tags_b:
        st.subheader("🏷️ 标签对比")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.write("**共同标签**")
            common_tags = tags_a & tags_b
            if common_tags:
                for tag in common_tags:
                    st.markdown(f"✅ `{tag}`")
            else:
                st.write("无共同标签")

        with col2:
            st.write("**仅在结果A中**")
            only_a = tags_a - tags_b
            if only_a:
                for tag in only_a:
                    st.markdown(f"🔵 `{tag}`")
            else:
                st.write("无独有标签")

        with col3:
            st.write("**仅在结果B中**")
            only_b = tags_b - tags_a
            if only_b:
                for tag in only_b:
                    st.markdown(f"🔴 `{tag}`")
            else:
                st.write("无独有标签")

    # 摘要对比
    summary_a = result_a.get("summary", "")
    summary_b = result_b.get("summary", "")

    if summary_a or summary_b:
        st.subheader("📝 分析摘要对比")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**分析结果 A 摘要**")
            if summary_a:
                st.markdown(summary_a)
            else:
                st.write("无摘要")

        with col2:
            st.write("**分析结果 B 摘要**")
            if summary_b:
                st.markdown(summary_b)
            else:
                st.write("无摘要")

    # 详细内容对比
    st.subheader("📊 详细内容对比")

    # 定义要对比的关键字段
    comparison_fields = [
        ("market_report", "📈 市场技术分析"),
        ("fundamentals_report", "💰 基本面分析"),
        ("sentiment_report", "💭 市场情绪分析"),
        ("news_report", "📰 新闻事件分析"),
        ("risk_assessment", "⚠️ 风险评估"),
        ("investment_plan", "📋 投资建议"),
        ("final_trade_decision", "🎯 最终交易决策"),
    ]

    # 创建对比标签页
    available_fields = []
    for field_key, field_name in comparison_fields:
        if (field_key in result_a and result_a[field_key]) or (field_key in result_b and result_b[field_key]):
            available_fields.append((field_key, field_name))

    if available_fields:
        tabs = st.tabs([field_name for _, field_name in available_fields])

        for i, (tab, (field_key, field_name)) in enumerate(zip(tabs, available_fields)):
            with tab:
                col1, col2 = st.columns(2)

                with col1:
                    st.write("**分析结果 A**")
                    content_a = result_a.get(field_key, "")
                    if content_a:
                        if isinstance(content_a, str):
                            st.markdown(content_a)
                        else:
                            st.write(content_a)
                    else:
                        st.write("无此项分析")

                with col2:
                    st.write("**分析结果 B**")
                    content_b = result_b.get(field_key, "")
                    if content_b:
                        if isinstance(content_b, str):
                            st.markdown(content_b)
                        else:
                            st.write(content_b)
                    else:
                        st.write("无此项分析")


def render_detailed_analysis(results: List[Dict[str, Any]]):
    """渲染详细分析"""

    st.subheader("📊 详细分析")

    if not results:
        st.info("没有可分析的数据")
        return

    # 选择要查看的分析结果
    result_options = []
    for i, result in enumerate(results[:50]):  # 显示前50个
        option = f"{result.get('stock_symbol', 'unknown')} - {safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%m-%d %H:%M')}"
        result_options.append((option, i))

    if result_options:
        selected_option = st.selectbox("选择分析结果", result_options, format_func=lambda x: x[0])
        selected_result = results[selected_option[1]]

        # 显示基本信息
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("股票代码", selected_result.get("stock_symbol", "unknown"))
            st.metric("分析师数量", len(selected_result.get("analysts", [])))

        with col2:
            analysis_time = safe_timestamp_to_datetime(selected_result.get("timestamp", 0))
            st.metric("分析时间", analysis_time.strftime("%m-%d %H:%M"))
            status = "✅ 完成" if selected_result.get("status") == "completed" else "❌ 失败"
            st.metric("状态", status)

        with col3:
            st.metric("研究深度", selected_result.get("research_depth", "unknown"))
            tags = selected_result.get("tags", [])
            st.metric("标签数量", len(tags))

        # 显示标签
        if tags:
            st.write("**标签**:")
            tag_cols = st.columns(min(len(tags), 5))
            for i, tag in enumerate(tags):
                with tag_cols[i % 5]:
                    st.markdown(f"`{tag}`")

        # 显示分析摘要
        if selected_result.get("summary"):
            st.subheader("📝 分析摘要")
            st.markdown(selected_result["summary"])

        # 显示性能指标
        performance = selected_result.get("performance", {})
        if performance:
            st.subheader("⚡ 性能指标")
            perf_cols = st.columns(len(performance))
            for i, (key, value) in enumerate(performance.items()):
                with perf_cols[i]:
                    st.metric(
                        key.replace("_", " ").title(),
                        f"{value:.2f}" if isinstance(value, (int, float)) else str(value),
                    )

        # 显示完整分析结果
        if st.checkbox("显示完整分析结果"):
            render_detailed_analysis_content(selected_result)
