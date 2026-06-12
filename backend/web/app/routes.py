from .common import importlib, require_permission, settings, st


def route_page(page):
    if page == "⚙️ 配置管理":
        # 检查配置权限
        if not require_permission("config"):
            return
        try:
            render_config = getattr(
                importlib.import_module("modules.config"), "render_config"
            )
            render_config()
        except ImportError as e:
            st.error(f"配置管理模块加载失败: {e}")
            st.info("请确保已安装所有依赖包")
        return
    elif page == "💾 缓存管理":
        # 检查管理员权限
        if not require_permission("admin"):
            return
        try:
            cache_main = getattr(importlib.import_module("modules.cache"), "main")
            cache_main()
        except ImportError as e:
            st.error(f"缓存管理页面加载失败: {e}")
        return
    elif page == "💰 Token统计":
        # 检查配置权限
        if not require_permission("config"):
            return
        try:
            render_tokens = getattr(
                importlib.import_module("modules.tokens"), "render_tokens"
            )
            render_tokens()
        except ImportError as e:
            st.error(f"Token统计页面加载失败: {e}")
            st.info("请确保已安装所有依赖包")
        return
    elif page == "📋 操作日志":
        # 检查管理员权限
        if not require_permission("admin"):
            return
        try:
            render_operations = getattr(
                importlib.import_module("components.operation"), "render_operations"
            )
            render_operations()
        except ImportError as e:
            st.error(f"操作日志模块加载失败: {e}")
            st.info("请确保已安装所有依赖包")
        return
    elif page == "📈 分析结果":
        # 检查分析权限
        if not require_permission("analysis"):
            return
        try:
            render_analysis = getattr(
                importlib.import_module("components.analysis"), "render_analysis"
            )
            render_analysis()
        except ImportError as e:
            st.error(f"分析结果模块加载失败: {e}")
            st.info("请确保已安装所有依赖包")
        return
    elif page == "🔧 系统状态":
        # 检查管理员权限
        if not require_permission("admin"):
            return
        st.header("🔧 系统状态")

        # 展示股票基础信息同步状态
        requests = importlib.import_module("requests")
        backend_url = settings.WEBAPI_BASE_URL
        try:
            resp = requests.get(
                f"{backend_url}/api/sync/stock_basics/status", timeout=5
            )
            if resp.ok:
                data = resp.json().get("data", {})
                st.subheader("📦 股票基础信息同步状态")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("状态", data.get("status", "unknown"))
                with col2:
                    st.metric("总处理", data.get("total", 0))
                with col3:
                    st.metric("错误数", data.get("errors", 0))

                st.write("- 开始时间:", data.get("started_at", ""))
                st.write("- 结束时间:", data.get("finished_at", ""))
                st.write("- 交易日期:", data.get("last_trade_date", ""))

                # 手动触发按钮
                if st.button("🔄 手动运行全量同步"):
                    with st.spinner("正在触发后端同步..."):
                        try:
                            run_resp = requests.post(
                                f"{backend_url}/api/sync/stock_basics/run", timeout=10
                            )
                            if run_resp.ok:
                                st.success("已触发同步任务，请稍后刷新查看状态")
                            else:
                                st.error(
                                    f"触发失败: {run_resp.status_code} {run_resp.text}"
                                )
                        except Exception as e:
                            st.error(f"触发异常: {e}")
            else:
                st.warning(f"无法获取同步状态: {resp.status_code}")
        except Exception as e:
            st.warning(f"同步状态查询失败: {e}")
        return

    return False
