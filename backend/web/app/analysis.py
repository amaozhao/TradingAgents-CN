from .common import (
    AsyncProgressTracker,
    datetime,
    display_unified_progress,
    importlib,
    logger,
    render_form,
    render_results,
    run_stock_analysis,
    set_persistent_analysis_id,
    settings,
    st,
    time,
    validate_analysis_params,
)


def ensure_api_keys(api_status):
    if not api_status["all_configured"]:
        st.error("⚠️ API密钥配置不完整，请先配置必要的API密钥")

        with st.expander("📋 API密钥配置指南", expanded=True):
            st.markdown("""
            ### 🔑 必需的API密钥

            1. **阿里百炼API密钥** (DASHSCOPE_API_KEY)
               - 获取地址: https://dashscope.aliyun.com/
               - 用途: AI模型推理

            2. **金融数据API密钥** (FINNHUB_API_KEY)
               - 获取地址: https://finnhub.io/
               - 用途: 获取股票数据

            ### ⚙️ 配置方法

            1. 复制 `backend/.env.example` 为 `backend/.env`
            2. 编辑 `backend/.env` 文件，填入您的真实API密钥
            3. 重启Web应用

            ```bash
            # .env 文件示例
            DASHSCOPE_API_KEY=sk-your-dashscope-key
            FINNHUB_API_KEY=your-finnhub-key
            ```
            """)

        # 显示当前API密钥状态
        st.subheader("🔍 当前API密钥状态")
        for key, status in api_status["details"].items():
            if status["configured"]:
                st.success(f"✅ {key}: {status['display']}")
            else:
                st.error(f"❌ {key}: 未配置")

        return

    return True


def render_analysis_workspace(col1, config):
    with col1:
        # 1. 分析配置区域

        st.header("⚙️ 分析配置")

        # 渲染分析表单
        try:
            form_data = render_form()

            # 验证表单数据格式
            if not isinstance(form_data, dict):
                st.error(f"⚠️ 表单数据格式异常: {type(form_data)}")
                form_data = {"submitted": False}

        except Exception as e:
            st.error(f"❌ 表单渲染失败: {e}")
            form_data = {"submitted": False}

        # 避免显示调试信息
        if form_data and form_data != {"submitted": False}:
            # 只在调试模式下显示表单数据
            if settings.DEBUG_MODE:
                st.write("Debug - Form data:", form_data)

        # 添加接收日志
        if form_data.get("submitted", False):
            logger.debug("🔍 [APP DEBUG] ===== 主应用接收表单数据 =====")
            logger.debug(f"🔍 [APP DEBUG] 接收到的form_data: {form_data}")
            logger.debug(f"🔍 [APP DEBUG] 股票代码: '{form_data['stock_symbol']}'")
            logger.debug(f"🔍 [APP DEBUG] 市场类型: '{form_data['market_type']}'")

        # 检查是否提交了表单
        if form_data.get("submitted", False) and not st.session_state.get(
            "analysis_running", False
        ):
            # 只有在没有分析运行时才处理新的提交
            # 验证分析参数
            is_valid, validation_errors = validate_analysis_params(
                stock_symbol=form_data["stock_symbol"],
                analysis_date=form_data["analysis_date"],
                analysts=form_data["analysts"],
                research_depth=form_data["research_depth"],
                market_type=form_data.get("market_type", "美股"),
            )

            if not is_valid:
                # 显示验证错误
                for error in validation_errors:
                    st.error(error)
            else:
                # 执行分析
                st.session_state.analysis_running = True

                # 清空旧的分析结果
                st.session_state.analysis = None
                logger.info("🧹 [新分析] 清空旧的分析结果")

                # 自动隐藏使用指南（除非用户明确设置要显示）
                if not st.session_state.get("user_set_guide_preference", False):
                    st.session_state.show_guide_preference = False
                    logger.info("📖 [界面] 开始分析，自动隐藏使用指南")

                # 生成分析ID
                uuid = importlib.import_module("uuid")
                analysis_id = f"analysis_{uuid.uuid4().hex[:8]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # 保存分析ID和表单配置到session state和cookie
                form_config = st.session_state.get("form_config", {})
                set_persistent_analysis_id(
                    analysis_id=analysis_id,
                    status="running",
                    stock_symbol=form_data["stock_symbol"],
                    market_type=form_data.get("market_type", "美股"),
                    form_config=form_config,
                )

                # 创建异步进度跟踪器
                async_tracker = AsyncProgressTracker(
                    analysis_id=analysis_id,
                    analysts=form_data["analysts"],
                    research_depth=form_data["research_depth"],
                    llm_provider=config["llm_provider"],
                )

                # 创建进度回调函数
                def progress_callback(
                    message: str, step: int = None, total_steps: int = None
                ):
                    async_tracker.update_progress(message, step)

                # 显示启动成功消息和加载动效
                st.success(f"🚀 分析已启动！分析ID: {analysis_id}")

                # 添加加载动效
                with st.spinner("🔄 正在初始化分析..."):
                    time.sleep(1.5)  # 让用户看到反馈

                st.info(
                    f"📊 正在分析: {form_data.get('market_type', '美股')} {form_data['stock_symbol']}"
                )
                st.info("""
                ⏱️ 页面将在6秒后自动刷新...

                📋 **查看分析进度：**
                刷新后请向下滚动到 "📊 股票分析" 部分查看实时进度
                """)

                # 确保AsyncProgressTracker已经保存初始状态
                time.sleep(0.1)  # 等待100毫秒确保数据已写入

                # 设置分析状态
                st.session_state.analysis_running = True
                st.session_state.current_analysis_id = analysis_id
                st.session_state.last_stock_symbol = form_data["stock_symbol"]
                st.session_state.last_market_type = form_data.get("market_type", "美股")

                # 自动启用自动刷新选项（设置所有可能的key）
                auto_refresh_keys = [
                    f"auto_refresh_unified_{analysis_id}",
                    f"auto_refresh_unified_default_{analysis_id}",
                    f"auto_refresh_static_{analysis_id}",
                    f"auto_refresh_streamlit_{analysis_id}",
                ]
                for key in auto_refresh_keys:
                    st.session_state[key] = True

                # 在后台线程中运行分析（立即启动，不等待倒计时）
                threading = importlib.import_module("threading")

                def run_analysis_in_background():
                    try:
                        results = run_stock_analysis(
                            stock_symbol=form_data["stock_symbol"],
                            analysis_date=form_data["analysis_date"],
                            analysts=form_data["analysts"],
                            research_depth=form_data["research_depth"],
                            llm_provider=config["llm_provider"],
                            market_type=form_data.get("market_type", "美股"),
                            llm_model=config["llm_model"],
                            progress_callback=progress_callback,
                        )

                        # 标记分析完成并保存结果（不访问session state）
                        async_tracker.mark_completed(
                            "✅ 分析成功完成！", results=results
                        )

                        # 自动保存分析结果到历史记录
                        try:
                            save_analysis_result = getattr(
                                importlib.import_module("components.analysis"),
                                "save_analysis_result",
                            )

                            save_success = save_analysis_result(
                                analysis_id=analysis_id,
                                stock_symbol=form_data["stock_symbol"],
                                analysts=form_data["analysts"],
                                research_depth=form_data["research_depth"],
                                result_data=results,
                                status="completed",
                            )

                            if save_success:
                                logger.info(
                                    f"💾 [后台保存] 分析结果已保存到历史记录: {analysis_id}"
                                )
                            else:
                                logger.warning(f"⚠️ [后台保存] 保存失败: {analysis_id}")

                        except Exception as save_error:
                            logger.error(f"❌ [后台保存] 保存异常: {save_error}")

                        logger.info(f"✅ [分析完成] 股票分析成功完成: {analysis_id}")

                    except Exception as e:
                        # 标记分析失败（不访问session state）
                        async_tracker.mark_failed(str(e))

                        # 保存失败的分析记录
                        try:
                            save_analysis_result = getattr(
                                importlib.import_module("components.analysis"),
                                "save_analysis_result",
                            )

                            save_analysis_result(
                                analysis_id=analysis_id,
                                stock_symbol=form_data["stock_symbol"],
                                analysts=form_data["analysts"],
                                research_depth=form_data["research_depth"],
                                result_data={"error": str(e)},
                                status="failed",
                            )
                            logger.info(
                                f"💾 [失败记录] 分析失败记录已保存: {analysis_id}"
                            )

                        except Exception as save_error:
                            logger.error(f"❌ [失败记录] 保存异常: {save_error}")

                        logger.error(f"❌ [分析失败] {analysis_id}: {e}")

                    finally:
                        # 分析结束后注销线程
                        unregister_analysis_thread = getattr(
                            importlib.import_module("utils.threads"),
                            "unregister_analysis_thread",
                        )
                        unregister_analysis_thread(analysis_id)
                        logger.info(f"🧵 [线程清理] 分析线程已注销: {analysis_id}")

                # 启动后台分析线程
                analysis_thread = threading.Thread(target=run_analysis_in_background)
                analysis_thread.daemon = (
                    True  # 设置为守护线程，这样主程序退出时线程也会退出
                )
                analysis_thread.start()

                # 注册线程到跟踪器
                register_analysis_thread = getattr(
                    importlib.import_module("utils.threads"), "register_analysis_thread"
                )
                register_analysis_thread(analysis_id, analysis_thread)

                logger.info(f"🧵 [后台分析] 分析线程已启动: {analysis_id}")

                # 分析已在后台线程中启动，显示启动信息并刷新页面
                st.success("🚀 分析已启动！正在后台运行...")

                # 显示启动信息
                st.info("⏱️ 页面将自动刷新显示分析进度...")

                # 等待2秒让用户看到启动信息，然后刷新页面
                time.sleep(2)
                st.rerun()

        # 2. 股票分析区域（只有在有分析ID时才显示）
        current_analysis_id = st.session_state.get("current_analysis_id")
        if current_analysis_id:
            st.markdown("---")

            st.header("📊 股票分析")

            # 使用线程检测来获取真实状态
            check_analysis_status = getattr(
                importlib.import_module("utils.threads"), "check_analysis_status"
            )
            actual_status = check_analysis_status(current_analysis_id)
            is_running = actual_status == "running"

            # 同步session state状态
            if st.session_state.get("analysis_running", False) != is_running:
                st.session_state.analysis_running = is_running
                logger.info(
                    f"🔄 [状态同步] 更新分析状态: {is_running} (基于线程检测: {actual_status})"
                )

            # 获取进度数据用于显示
            get_progress_by_id = getattr(
                importlib.import_module("utils.progress"), "get_progress_by_id"
            )
            progress_data = get_progress_by_id(current_analysis_id)

            # 显示分析信息
            if is_running:
                st.info(f"🔄 正在分析: {current_analysis_id}")
            else:
                if actual_status == "completed":
                    st.success(f"✅ 分析完成: {current_analysis_id}")

                elif actual_status == "failed":
                    st.error(f"❌ 分析失败: {current_analysis_id}")
                else:
                    st.warning(f"⚠️ 分析状态未知: {current_analysis_id}")

            # 显示进度（根据状态决定是否显示刷新控件）
            progress_col1, progress_col2 = st.columns([4, 1])
            with progress_col1:
                st.markdown("### 📊 分析进度")

            is_completed = display_unified_progress(
                current_analysis_id, show_refresh_controls=is_running
            )

            # 如果分析正在进行，显示提示信息（不添加额外的自动刷新）
            if is_running:
                st.info("⏱️ 分析正在进行中，可以使用下方的自动刷新功能查看进度更新...")

            # 如果分析刚完成，尝试恢复结果
            if is_completed and not st.session_state.get("analysis") and progress_data:
                if "raw_results" in progress_data:
                    try:
                        format_analysis = getattr(
                            importlib.import_module("utils.analysis"), "format_analysis"
                        )
                        raw_results = progress_data["raw_results"]
                        formatted_results = format_analysis(raw_results)
                        if formatted_results:
                            st.session_state.analysis = formatted_results
                            st.session_state.analysis_running = False
                            logger.info(
                                f"📊 [结果同步] 恢复分析结果: {current_analysis_id}"
                            )

                            # 自动保存分析结果到历史记录
                            try:
                                save_analysis_result = getattr(
                                    importlib.import_module("components.analysis"),
                                    "save_analysis_result",
                                )

                                # 从进度数据中获取分析参数
                                stock_symbol = progress_data.get(
                                    "stock_symbol",
                                    st.session_state.get(
                                        "last_stock_symbol", "unknown"
                                    ),
                                )
                                analysts = progress_data.get("analysts", [])
                                research_depth = progress_data.get("research_depth", 3)

                                # 保存分析结果
                                save_success = save_analysis_result(
                                    analysis_id=current_analysis_id,
                                    stock_symbol=stock_symbol,
                                    analysts=analysts,
                                    research_depth=research_depth,
                                    result_data=raw_results,
                                    status="completed",
                                )

                                if save_success:
                                    logger.info(
                                        f"💾 [结果保存] 分析结果已保存到历史记录: {current_analysis_id}"
                                    )
                                else:
                                    logger.warning(
                                        f"⚠️ [结果保存] 保存失败: {current_analysis_id}"
                                    )

                            except Exception as save_error:
                                logger.error(f"❌ [结果保存] 保存异常: {save_error}")

                            # 检查是否已经刷新过，避免重复刷新
                            refresh_key = f"results_refreshed_{current_analysis_id}"
                            if not st.session_state.get(refresh_key, False):
                                st.session_state[refresh_key] = True
                                st.success("📊 分析结果已恢复并保存，正在刷新页面...")
                                # 使用st.rerun()代替meta refresh，保持侧边栏状态
                                time.sleep(1)
                                st.rerun()
                            else:
                                # 已经刷新过，不再刷新
                                st.success("📊 分析结果已恢复并保存！")
                    except Exception as e:
                        logger.warning(f"⚠️ [结果同步] 恢复失败: {e}")

            if is_completed and st.session_state.get("analysis_running", False):
                # 分析刚完成，更新状态
                st.session_state.analysis_running = False
                st.success("🎉 分析完成！正在刷新页面显示报告...")

                # 使用st.rerun()代替meta refresh，保持侧边栏状态
                time.sleep(1)
                st.rerun()

        # 3. 分析报告区域（只有在有结果且分析完成时才显示）

        current_analysis_id = st.session_state.get("current_analysis_id")
        analysis = st.session_state.get("analysis")
        analysis_running = st.session_state.get("analysis_running", False)

        # 检查是否应该显示分析报告
        # 1. 有分析结果且不在运行中
        # 2. 或者用户点击了"查看报告"按钮
        show_results_button_clicked = st.session_state.get("show_analysis", False)

        should_show_results = (
            analysis and not analysis_running and current_analysis_id
        ) or (show_results_button_clicked and analysis)

        # 调试日志
        logger.info("🔍 [布局调试] 分析报告显示检查:")
        logger.info(f"  - analysis存在: {bool(analysis)}")
        logger.info(f"  - analysis_running: {analysis_running}")
        logger.info(f"  - current_analysis_id: {current_analysis_id}")
        logger.info(f"  - show_results_button_clicked: {show_results_button_clicked}")
        logger.info(f"  - should_show_results: {should_show_results}")

        if should_show_results:
            st.markdown("---")
            st.header("📋 分析报告")
            render_results(analysis)
            logger.info("✅ [布局] 分析报告已显示")

            # 清除查看报告按钮状态，避免重复触发
            if show_results_button_clicked:
                st.session_state.show_analysis = False
