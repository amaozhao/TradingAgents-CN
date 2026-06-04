# ruff: noqa: F401,F403,F405,F821
@router.get("/tasks/{task_id}/result", response_model=ApiResponse)
async def get_task_result(  # pyright: ignore[reportGeneralTypeIssues]
    task_id: str, user: dict = Depends(get_current_user)
):
    """获取分析任务结果"""
    try:
        logger.info(f"🔍 [RESULT] 获取任务结果: {task_id}")
        logger.info(f"👤 [RESULT] 用户: {user}")

        analysis_service = get_simple_analysis_service()
        task_status = await analysis_service.get_task_status(task_id)

        result_data = None

        if task_status and task_status.get("status") == "completed":
            # 从内存中获取结果数据
            result_data = task_status.get("result_data")
            logger.info("📊 [RESULT] 从内存中获取到结果数据")

            # 🔍 调试：检查内存中的数据结构
            if result_data:
                logger.info(f"📊 [RESULT] 内存数据键: {list(result_data.keys())}")
                logger.info(
                    f"📊 [RESULT] 内存中有decision字段: {bool(result_data.get('decision'))}"
                )
                logger.info(
                    f"📊 [RESULT] 内存中summary长度: {len(result_data.get('summary', ''))}"
                )
                logger.info(
                    f"📊 [RESULT] 内存中recommendation长度: {len(result_data.get('recommendation', ''))}"
                )
                if result_data.get("decision"):
                    decision = result_data["decision"]
                    logger.info(
                        f"📊 [RESULT] 内存decision内容: action={decision.get('action')}, target_price={decision.get('target_price')}"
                    )
            else:
                logger.warning("⚠️ [RESULT] 内存中result_data为空")

        if not result_data:
            # 内存中没有找到，尝试从 PostgreSQL document store 中查找
            logger.info(
                f"📊 [RESULT] 内存中未找到，尝试从 PostgreSQL document store 查找: {task_id}"
            )

            # 从analysis_reports集合中查找（优先使用 task_id 匹配）
            postgres_result = await _get_analysis_report_by_task_id_for_read(task_id)

            if not postgres_result:
                # 兼容旧数据：旧记录可能没有 task_id，但 analysis_id 存在于 analysis_tasks.result
                tasks_doc_for_id = await _get_analysis_task_for_read(task_id)
                analysis_id = (
                    tasks_doc_for_id.get("result", {}).get("analysis_id")
                    if tasks_doc_for_id
                    else None
                )
                if analysis_id:
                    logger.info(
                        f"🔎 [RESULT] 按analysis_id兜底查询 analysis_reports: {analysis_id}"
                    )
                    postgres_result = (
                        await _get_analysis_report_by_analysis_id_for_read(analysis_id)
                    )

            if postgres_result:
                logger.info(
                    f"✅ [RESULT] 从 PostgreSQL document store 找到结果: {task_id}"
                )

                # 直接使用 document-store 中的数据结构（与web目录保持一致）
                result_data = {
                    "analysis_id": postgres_result.get("analysis_id"),
                    "stock_symbol": postgres_result.get("stock_symbol"),
                    "stock_code": postgres_result.get("stock_symbol"),  # 兼容性
                    "analysis_date": postgres_result.get("analysis_date"),
                    "summary": postgres_result.get("summary", ""),
                    "recommendation": postgres_result.get("recommendation", ""),
                    "confidence_score": postgres_result.get("confidence_score", 0.0),
                    "risk_level": postgres_result.get("risk_level", "中等"),
                    "key_points": postgres_result.get("key_points", []),
                    "execution_time": postgres_result.get("execution_time", 0),
                    "tokens_used": postgres_result.get("tokens_used", 0),
                    "analysts": postgres_result.get("analysts", []),
                    "research_depth": postgres_result.get("research_depth", "快速"),
                    "reports": postgres_result.get("reports", {}),
                    "created_at": postgres_result.get("created_at"),
                    "updated_at": postgres_result.get("updated_at"),
                    "status": postgres_result.get("status", "completed"),
                    "decision": postgres_result.get("decision", {}),
                    "source": "postgres",  # 标记数据来源
                }

                # 添加调试信息
                logger.info(
                    f"📊 [RESULT] PostgreSQL数据结构: {list(result_data.keys())}"
                )
                logger.info(
                    f"📊 [RESULT] PostgreSQL summary长度: {len(result_data['summary'])}"
                )
                logger.info(
                    f"📊 [RESULT] PostgreSQL recommendation长度: {len(result_data['recommendation'])}"
                )
                logger.info(
                    f"📊 [RESULT] PostgreSQL decision字段: {bool(result_data.get('decision'))}"
                )
                if result_data.get("decision"):
                    decision = result_data["decision"]
                    logger.info(
                        f"📊 [RESULT] PostgreSQL decision内容: action={decision.get('action')}, target_price={decision.get('target_price')}, confidence={decision.get('confidence')}"
                    )
            else:
                # 兜底：analysis_tasks 集合中的 result 字段
                tasks_doc = await _get_analysis_task_for_read(task_id)
                if tasks_doc and tasks_doc.get("result"):
                    r = tasks_doc["result"] or {}
                    logger.info("✅ [RESULT] 从analysis_tasks.result 找到结果")
                    # 获取股票代码 (优先使用symbol)
                    symbol = (
                        tasks_doc.get("symbol")
                        or tasks_doc.get("stock_code")
                        or r.get("stock_symbol")
                        or r.get("stock_code")
                    )
                    result_data = {
                        "analysis_id": r.get("analysis_id"),
                        "stock_symbol": symbol,
                        "stock_code": symbol,  # 兼容字段
                        "analysis_date": r.get("analysis_date"),
                        "summary": r.get("summary", ""),
                        "recommendation": r.get("recommendation", ""),
                        "confidence_score": r.get("confidence_score", 0.0),
                        "risk_level": r.get("risk_level", "中等"),
                        "key_points": r.get("key_points", []),
                        "execution_time": r.get("execution_time", 0),
                        "tokens_used": r.get("tokens_used", 0),
                        "analysts": r.get("analysts", []),
                        "research_depth": r.get("research_depth", "快速"),
                        "reports": r.get("reports", {}),
                        "state": r.get("state", {}),
                        "detailed_analysis": r.get("detailed_analysis", {}),
                        "created_at": tasks_doc.get("created_at"),
                        "updated_at": tasks_doc.get("completed_at"),
                        "status": r.get("status", "completed"),
                        "decision": r.get("decision", {}),
                        "source": "analysis_tasks",  # 数据来源标记
                    }

        if not result_data:
            logger.warning(f"❌ [RESULT] 所有数据源都未找到结果: {task_id}")
            raise HTTPException(status_code=404, detail="分析结果不存在")

        if not result_data:
            raise HTTPException(status_code=404, detail="分析结果不存在")

        # 处理reports字段 - 如果没有reports字段，优先尝试从文件系统加载，其次从state中提取
        if "reports" not in result_data or not result_data["reports"]:
            stock_symbol = result_data.get("stock_symbol") or result_data.get(
                "stock_code"
            )
            # analysis_date 可能是日期或时间戳字符串，这里只取日期部分
            analysis_date_raw = result_data.get("analysis_date")
            analysis_date = str(analysis_date_raw)[:10] if analysis_date_raw else None

            loaded_reports = {}
            try:
                # 1) 尝试从环境变量 TRADING_AGENTS_RESULTS_DIR 指定的位置读取
                base_env = os.getenv("TRADING_AGENTS_RESULTS_DIR")
                project_root = Path.cwd()
                if base_env:
                    base_path = Path(base_env)
                    if not base_path.is_absolute():
                        base_path = project_root / base_env
                else:
                    base_path = project_root / "results"

                candidate_dirs = []
                if stock_symbol and analysis_date:
                    candidate_dirs.append(
                        base_path / stock_symbol / analysis_date / "reports"
                    )
                # 2) 兼容其他保存路径
                if stock_symbol and analysis_date:
                    candidate_dirs.append(
                        project_root
                        / "data"
                        / "analysis"
                        / stock_symbol
                        / analysis_date
                        / "reports"
                    )
                    candidate_dirs.append(
                        project_root
                        / "data"
                        / "analysis"
                        / "detailed"
                        / stock_symbol
                        / analysis_date
                        / "reports"
                    )

                for d in candidate_dirs:
                    if d.exists() and d.is_dir():
                        for f in d.glob("*.md"):
                            try:
                                content = f.read_text(encoding="utf-8")
                                if content and content.strip():
                                    loaded_reports[f.stem] = content.strip()
                            except Exception:
                                pass
                if loaded_reports:
                    result_data["reports"] = loaded_reports
                    # 若 summary / recommendation 缺失，尝试从同名报告补全
                    if not result_data.get("summary") and loaded_reports.get("summary"):
                        result_data["summary"] = loaded_reports.get("summary")
                    if not result_data.get("recommendation") and loaded_reports.get(
                        "recommendation"
                    ):
                        result_data["recommendation"] = loaded_reports.get(
                            "recommendation"
                        )
                    logger.info(
                        f"📁 [RESULT] 从文件系统加载到 {len(loaded_reports)} 个报告: {list(loaded_reports.keys())}"
                    )
            except Exception as fs_err:
                logger.warning(f"⚠️ [RESULT] 从文件系统加载报告失败: {fs_err}")

            if "reports" not in result_data or not result_data["reports"]:
                logger.info("📊 [RESULT] reports字段缺失，尝试从state中提取")

                # 从state中提取报告内容
                reports = {}
                state = result_data.get("state", {})

                if isinstance(state, dict):
                    # 定义所有可能的报告字段
                    report_fields = [
                        "market_report",
                        "sentiment_report",
                        "news_report",
                        "fundamentals_report",
                        "investment_plan",
                        "trader_investment_plan",
                        "final_trade_decision",
                    ]

                    # 从state中提取报告内容
                    for field in report_fields:
                        value = state.get(field, "")
                        if isinstance(value, str) and len(value.strip()) > 10:
                            reports[field] = value.strip()

                    # 处理研究团队辩论状态报告
                    investment_debate_state = state.get("investment_debate_state", {})
                    if isinstance(investment_debate_state, dict):
                        # 提取多头研究员历史
                        bull_content = investment_debate_state.get("bull_history", "")
                        if (
                            isinstance(bull_content, str)
                            and len(bull_content.strip()) > 10
                        ):
                            reports["bull_researcher"] = bull_content.strip()

                        # 提取空头研究员历史
                        bear_content = investment_debate_state.get("bear_history", "")
                        if (
                            isinstance(bear_content, str)
                            and len(bear_content.strip()) > 10
                        ):
                            reports["bear_researcher"] = bear_content.strip()

                        # 提取研究经理决策
                        judge_decision = investment_debate_state.get(
                            "judge_decision", ""
                        )
                        if (
                            isinstance(judge_decision, str)
                            and len(judge_decision.strip()) > 10
                        ):
                            reports["research_team_decision"] = judge_decision.strip()

                    # 处理风险管理团队辩论状态报告
                    risk_debate_state = state.get("risk_debate_state", {})
                    if isinstance(risk_debate_state, dict):
                        # 提取激进分析师历史
                        risky_content = risk_debate_state.get("risky_history", "")
                        if (
                            isinstance(risky_content, str)
                            and len(risky_content.strip()) > 10
                        ):
                            reports["risky_analyst"] = risky_content.strip()

                        # 提取保守分析师历史
                        safe_content = risk_debate_state.get("safe_history", "")
                        if (
                            isinstance(safe_content, str)
                            and len(safe_content.strip()) > 10
                        ):
                            reports["safe_analyst"] = safe_content.strip()

                        # 提取中性分析师历史
                        neutral_content = risk_debate_state.get("neutral_history", "")
                        if (
                            isinstance(neutral_content, str)
                            and len(neutral_content.strip()) > 10
                        ):
                            reports["neutral_analyst"] = neutral_content.strip()

                        # 提取投资组合经理决策
                        risk_decision = risk_debate_state.get("judge_decision", "")
                        if (
                            isinstance(risk_decision, str)
                            and len(risk_decision.strip()) > 10
                        ):
                            reports["risk_management_decision"] = risk_decision.strip()

                    logger.info(
                        f"📊 [RESULT] 从state中提取到 {len(reports)} 个报告: {list(reports.keys())}"
                    )
                    result_data["reports"] = reports
                else:
                    logger.warning(f"⚠️ [RESULT] state字段不是字典类型: {type(state)}")

        # 确保reports字段中的所有内容都是字符串类型
        if "reports" in result_data and result_data["reports"]:
            reports = result_data["reports"]
            if isinstance(reports, dict):
                # 确保每个报告内容都是字符串且不为空
                cleaned_reports = {}
                for key, value in reports.items():
                    if isinstance(value, str) and value.strip():
                        # 确保字符串不为空
                        cleaned_reports[key] = value.strip()
                    elif value is not None:
                        # 如果不是字符串，转换为字符串
                        str_value = str(value).strip()
                        if str_value:  # 只保存非空字符串
                            cleaned_reports[key] = str_value
                    # 如果value为None或空字符串，则跳过该报告

                result_data["reports"] = cleaned_reports
                logger.info(
                    f"📊 [RESULT] 清理reports字段，包含 {len(cleaned_reports)} 个有效报告"
                )

                # 如果清理后没有有效报告，设置为空字典
                if not cleaned_reports:
                    logger.warning("⚠️ [RESULT] 清理后没有有效报告")
                    result_data["reports"] = {}
            else:
                logger.warning(f"⚠️ [RESULT] reports字段不是字典类型: {type(reports)}")
                result_data["reports"] = {}

        # 补全关键字段：recommendation/summary/key_points
        try:
            reports = result_data.get("reports", {}) or {}
            decision = result_data.get("decision", {}) or {}

            # recommendation 优先使用决策摘要或报告中的决策
            if not result_data.get("recommendation"):
                rec_candidates = []
                if isinstance(decision, dict) and decision.get("action"):
                    parts = [
                        f"操作: {decision.get('action')}",
                        f"目标价: {decision.get('target_price')}"
                        if decision.get("target_price")
                        else None,
                        f"置信度: {decision.get('confidence')}"
                        if decision.get("confidence") is not None
                        else None,
                    ]
                    rec_candidates.append("；".join([p for p in parts if p]))
                # 从报告中兜底
                for k in ["final_trade_decision", "investment_plan"]:
                    v = reports.get(k)
                    if isinstance(v, str) and len(v.strip()) > 10:
                        rec_candidates.append(v.strip())
                if rec_candidates:
                    # 取最有信息量的一条（最长）
                    result_data["recommendation"] = max(rec_candidates, key=len)[:2000]

            # summary 从若干报告拼接生成
            if not result_data.get("summary"):
                sum_candidates = []
                for k in [
                    "market_report",
                    "fundamentals_report",
                    "sentiment_report",
                    "news_report",
                ]:
                    v = reports.get(k)
                    if isinstance(v, str) and len(v.strip()) > 50:
                        sum_candidates.append(v.strip())
                if sum_candidates:
                    result_data["summary"] = ("\n\n".join(sum_candidates))[:3000]

            # key_points 兜底
            if not result_data.get("key_points"):
                kp = []
                if isinstance(decision, dict):
                    if decision.get("action"):
                        kp.append(f"操作建议: {decision.get('action')}")
                    if decision.get("target_price"):
                        kp.append(f"目标价: {decision.get('target_price')}")
                    if decision.get("confidence") is not None:
                        kp.append(f"置信度: {decision.get('confidence')}")
                # 从reports中截取前几句作为要点
                for k in ["investment_plan", "final_trade_decision"]:
                    v = reports.get(k)
                    if isinstance(v, str) and len(v.strip()) > 10:
                        kp.append(v.strip()[:120])
                if kp:
                    result_data["key_points"] = kp[:5]
        except Exception as fill_err:
            logger.warning(f"⚠️ [RESULT] 补全关键字段时出错: {fill_err}")

        # 进一步兜底：从 detailed_analysis 推断并补全
        try:
            if (
                not result_data.get("summary")
                or not result_data.get("recommendation")
                or not result_data.get("reports")
            ):
                da = result_data.get("detailed_analysis")
                # 若reports仍为空，放入一份原始详细分析，便于前端“查看报告详情”
                if (
                    (not result_data.get("reports"))
                    and isinstance(da, str)
                    and len(da.strip()) > 20
                ):
                    result_data["reports"] = {"detailed_analysis": da.strip()}
                elif (not result_data.get("reports")) and isinstance(da, dict) and da:
                    # 将字典的长文本项放入reports
                    extracted = {}
                    for k, v in da.items():
                        if isinstance(v, str) and len(v.strip()) > 20:
                            extracted[k] = v.strip()
                    if extracted:
                        result_data["reports"] = extracted

                # 补 summary
                if not result_data.get("summary"):
                    if isinstance(da, str) and da.strip():
                        result_data["summary"] = da.strip()[:3000]
                    elif isinstance(da, dict) and da:
                        # 取最长的文本作为摘要
                        texts = [
                            v.strip()
                            for v in da.values()
                            if isinstance(v, str) and v.strip()
                        ]
                        if texts:
                            result_data["summary"] = max(texts, key=len)[:3000]

                # 补 recommendation
                if not result_data.get("recommendation"):
                    rec = None
                    if isinstance(da, str):
                        # 简单基于关键字提取包含“建议”的段落
                        m = re.search(r"(投资建议|建议|结论)[:：]?\s*(.+)", da)
                        if m:
                            rec = m.group(0)
                    elif isinstance(da, dict):
                        for key in [
                            "final_trade_decision",
                            "investment_plan",
                            "结论",
                            "建议",
                        ]:
                            v = da.get(key)
                            if isinstance(v, str) and len(v.strip()) > 10:
                                rec = v.strip()
                                break
                    if rec:
                        result_data["recommendation"] = rec[:2000]
        except Exception as da_err:
            logger.warning(f"⚠️ [RESULT] 从detailed_analysis补全失败: {da_err}")

        # 严格的数据格式化和验证
        def safe_string(value, default=""):
            """安全地转换为字符串"""
            if value is None:
                return default
            if isinstance(value, str):
                return value
            return str(value)

        def safe_number(value, default=0):
            """安全地转换为数字"""
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return value
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        def safe_list(value, default=None):
            """安全地转换为列表"""
            if default is None:
                default = []
            if value is None:
                return default
            if isinstance(value, list):
                return value
            return default

        def safe_dict(value, default=None):
            """安全地转换为字典"""
            if default is None:
                default = {}
            if value is None:
                return default
            if isinstance(value, dict):
                return value
            return default

        # 🔍 调试：检查最终构建前的result_data
        logger.info(
            f"🔍 [FINAL] 构建最终结果前，result_data键: {list(result_data.keys())}"
        )
        logger.info(
            f"🔍 [FINAL] result_data中有decision: {bool(result_data.get('decision'))}"
        )
        if result_data.get("decision"):
            logger.info(f"🔍 [FINAL] decision内容: {result_data['decision']}")

        # 构建严格验证的结果数据
        final_result_data = {
            "analysis_id": safe_string(result_data.get("analysis_id"), "unknown"),
            "stock_symbol": safe_string(result_data.get("stock_symbol"), "UNKNOWN"),
            "stock_code": safe_string(result_data.get("stock_code"), "UNKNOWN"),
            "analysis_date": safe_string(
                result_data.get("analysis_date"), "2025-08-20"
            ),
            "summary": safe_string(result_data.get("summary"), "分析摘要暂无"),
            "recommendation": safe_string(
                result_data.get("recommendation"), "投资建议暂无"
            ),
            "confidence_score": safe_number(result_data.get("confidence_score"), 0.0),
            "risk_level": safe_string(result_data.get("risk_level"), "中等"),
            "key_points": safe_list(result_data.get("key_points")),
            "execution_time": safe_number(result_data.get("execution_time"), 0),
            "tokens_used": safe_number(result_data.get("tokens_used"), 0),
            "analysts": safe_list(result_data.get("analysts")),
            "research_depth": safe_string(result_data.get("research_depth"), "快速"),
            "detailed_analysis": safe_dict(result_data.get("detailed_analysis")),
            "state": safe_dict(result_data.get("state")),
            # 🔥 关键修复：添加decision字段！
            "decision": safe_dict(result_data.get("decision")),
        }

        # 特别处理reports字段 - 确保每个报告都是有效字符串
        reports_data = safe_dict(result_data.get("reports"))
        validated_reports = {}

        for report_key, report_content in reports_data.items():
            # 确保报告键是字符串
            safe_key = safe_string(report_key, "unknown_report")

            # 确保报告内容是非空字符串
            if report_content is None:
                validated_content = "报告内容暂无"
            elif isinstance(report_content, str):
                validated_content = (
                    report_content.strip() if report_content.strip() else "报告内容为空"
                )
            else:
                validated_content = (
                    str(report_content).strip()
                    if str(report_content).strip()
                    else "报告内容格式错误"
                )

            validated_reports[safe_key] = validated_content

        final_result_data["reports"] = validated_reports

        logger.info(f"✅ [RESULT] 成功获取任务结果: {task_id}")
        logger.info(
            f"📊 [RESULT] 最终返回 {len(final_result_data.get('reports', {}))} 个报告"
        )

        # 🔍 调试：检查最终返回的数据
        logger.info(f"🔍 [FINAL] 最终返回数据键: {list(final_result_data.keys())}")
        logger.info(
            f"🔍 [FINAL] 最终返回中有decision: {bool(final_result_data.get('decision'))}"
        )
        if final_result_data.get("decision"):
            logger.info(f"🔍 [FINAL] 最终decision内容: {final_result_data['decision']}")

        return {
            "success": True,
            "data": final_result_data,
            "message": "分析结果获取成功",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [RESULT] 获取任务结果失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
