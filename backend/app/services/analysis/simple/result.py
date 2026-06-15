from .common import (
    Any,
    Dict,
    SingleAnalysisRequest,
    logger,
    uuid,
)
from app.db.document import normalize_payload


def build_analysis_result(
    request: SingleAnalysisRequest,
    analysis_date: str,
    state: Any,
    decision: Any,
    execution_time: float,
    task_id: str | None = None,
) -> Dict[str, Any]:
    # 从state中提取reports字段
    reports = {}
    try:
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
            if hasattr(state, field):
                value = getattr(state, field, "")
            elif isinstance(state, dict) and field in state:
                value = state[field]
            else:
                value = ""

            if (
                isinstance(value, str) and len(value.strip()) > 10
            ):  # 只保存有实际内容的报告
                reports[field] = value.strip()
                logger.info(
                    f"📊 [REPORTS] 提取报告: {field} - 长度: {len(value.strip())}"
                )
            else:
                logger.debug(f"⚠️ [REPORTS] 跳过报告: {field} - 内容为空或太短")

        # 处理研究团队辩论状态报告
        if hasattr(state, "investment_debate_state") or (
            isinstance(state, dict) and "investment_debate_state" in state
        ):
            debate_state = (
                getattr(state, "investment_debate_state", None)
                if hasattr(state, "investment_debate_state")
                else state.get("investment_debate_state")
            )
            if debate_state:
                # 提取多头研究员历史
                if hasattr(debate_state, "bull_history"):
                    bull_content = getattr(debate_state, "bull_history", "")
                elif isinstance(debate_state, dict) and "bull_history" in debate_state:
                    bull_content = debate_state["bull_history"]
                else:
                    bull_content = ""

                if bull_content and len(bull_content.strip()) > 10:
                    reports["bull_researcher"] = bull_content.strip()
                    logger.info(
                        f"📊 [REPORTS] 提取报告: bull_researcher - 长度: {len(bull_content.strip())}"
                    )

                # 提取空头研究员历史
                if hasattr(debate_state, "bear_history"):
                    bear_content = getattr(debate_state, "bear_history", "")
                elif isinstance(debate_state, dict) and "bear_history" in debate_state:
                    bear_content = debate_state["bear_history"]
                else:
                    bear_content = ""

                if bear_content and len(bear_content.strip()) > 10:
                    reports["bear_researcher"] = bear_content.strip()
                    logger.info(
                        f"📊 [REPORTS] 提取报告: bear_researcher - 长度: {len(bear_content.strip())}"
                    )

                # 提取研究经理决策
                if hasattr(debate_state, "judge_decision"):
                    decision_content = getattr(debate_state, "judge_decision", "")
                elif (
                    isinstance(debate_state, dict) and "judge_decision" in debate_state
                ):
                    decision_content = debate_state["judge_decision"]
                else:
                    decision_content = str(debate_state)

                if decision_content and len(decision_content.strip()) > 10:
                    reports["research_team_decision"] = decision_content.strip()
                    logger.info(
                        f"📊 [REPORTS] 提取报告: research_team_decision - 长度: {len(decision_content.strip())}"
                    )

        # 处理风险管理团队辩论状态报告
        if hasattr(state, "risk_debate_state") or (
            isinstance(state, dict) and "risk_debate_state" in state
        ):
            risk_state = (
                getattr(state, "risk_debate_state", None)
                if hasattr(state, "risk_debate_state")
                else state.get("risk_debate_state")
            )
            if risk_state:
                # 提取激进分析师历史
                if hasattr(risk_state, "risky_history"):
                    risky_content = getattr(risk_state, "risky_history", "")
                elif isinstance(risk_state, dict) and "risky_history" in risk_state:
                    risky_content = risk_state["risky_history"]
                else:
                    risky_content = ""

                if risky_content and len(risky_content.strip()) > 10:
                    reports["risky_analyst"] = risky_content.strip()
                    logger.info(
                        f"📊 [REPORTS] 提取报告: risky_analyst - 长度: {len(risky_content.strip())}"
                    )

                # 提取保守分析师历史
                if hasattr(risk_state, "safe_history"):
                    safe_content = getattr(risk_state, "safe_history", "")
                elif isinstance(risk_state, dict) and "safe_history" in risk_state:
                    safe_content = risk_state["safe_history"]
                else:
                    safe_content = ""

                if safe_content and len(safe_content.strip()) > 10:
                    reports["safe_analyst"] = safe_content.strip()
                    logger.info(
                        f"📊 [REPORTS] 提取报告: safe_analyst - 长度: {len(safe_content.strip())}"
                    )

                # 提取中性分析师历史
                if hasattr(risk_state, "neutral_history"):
                    neutral_content = getattr(risk_state, "neutral_history", "")
                elif isinstance(risk_state, dict) and "neutral_history" in risk_state:
                    neutral_content = risk_state["neutral_history"]
                else:
                    neutral_content = ""

                if neutral_content and len(neutral_content.strip()) > 10:
                    reports["neutral_analyst"] = neutral_content.strip()
                    logger.info(
                        f"📊 [REPORTS] 提取报告: neutral_analyst - 长度: {len(neutral_content.strip())}"
                    )

                # 提取投资组合经理决策
                if hasattr(risk_state, "judge_decision"):
                    risk_decision = getattr(risk_state, "judge_decision", "")
                elif isinstance(risk_state, dict) and "judge_decision" in risk_state:
                    risk_decision = risk_state["judge_decision"]
                else:
                    risk_decision = str(risk_state)

                if risk_decision and len(risk_decision.strip()) > 10:
                    reports["risk_management_decision"] = risk_decision.strip()
                    logger.info(
                        f"📊 [REPORTS] 提取报告: risk_management_decision - 长度: {len(risk_decision.strip())}"
                    )

        logger.info(
            f"📊 [REPORTS] 从state中提取到 {len(reports)} 个报告: {list(reports.keys())}"
        )

    except Exception as e:
        logger.warning(f"⚠️ 提取reports时出错: {e}")
        # 降级到从detailed_analysis提取
        try:
            if isinstance(decision, dict):
                for key, value in decision.items():
                    if isinstance(value, str) and len(value) > 50:
                        reports[key] = value
                logger.info(f"📊 降级：从decision中提取到 {len(reports)} 个报告")
        except Exception as fallback_error:
            logger.warning(f"⚠️ 降级提取也失败: {fallback_error}")

    # 🔥 格式化decision数据（参考web目录的实现）
    formatted_decision = {}
    try:
        if isinstance(decision, dict):
            # 处理目标价格
            target_price = decision.get("target_price")
            if target_price is not None and target_price != "N/A":
                try:
                    if isinstance(target_price, str):
                        # 移除货币符号和空格
                        clean_price = (
                            target_price.replace("$", "")
                            .replace("¥", "")
                            .replace("￥", "")
                            .strip()
                        )
                        target_price = (
                            float(clean_price)
                            if clean_price and clean_price != "None"
                            else None
                        )
                    elif isinstance(target_price, (int, float)):
                        target_price = float(target_price)
                    else:
                        target_price = None
                except (ValueError, TypeError):
                    target_price = None
            else:
                target_price = None

            # 将英文投资建议转换为中文
            action_translation = {
                "BUY": "买入",
                "SELL": "卖出",
                "HOLD": "持有",
                "buy": "买入",
                "sell": "卖出",
                "hold": "持有",
            }
            action = decision.get("action", "持有")
            chinese_action = action_translation.get(action, action)

            formatted_decision = {
                "action": chinese_action,
                "confidence": decision.get("confidence", 0.5),
                "risk_score": decision.get("risk_score", 0.3),
                "target_price": target_price,
                "reasoning": decision.get("reasoning", "暂无分析推理"),
            }

            logger.info(f"🎯 [DEBUG] 格式化后的decision: {formatted_decision}")
        else:
            # 处理其他类型
            formatted_decision = {
                "action": "持有",
                "confidence": 0.5,
                "risk_score": 0.3,
                "target_price": None,
                "reasoning": "暂无分析推理",
            }
            logger.warning(f"⚠️ Decision不是字典类型: {type(decision)}")
    except Exception as e:
        logger.error(f"❌ 格式化decision失败: {e}")
        formatted_decision = {
            "action": "持有",
            "confidence": 0.5,
            "risk_score": 0.3,
            "target_price": None,
            "reasoning": "暂无分析推理",
        }

    # 🔥 按照web目录的方式生成summary和recommendation
    summary = ""
    recommendation = ""

    # 1. 优先从reports中的final_trade_decision提取summary（与web目录保持一致）
    if isinstance(reports, dict) and "final_trade_decision" in reports:
        final_decision_content = reports["final_trade_decision"]
        if isinstance(final_decision_content, str) and len(final_decision_content) > 50:
            # 提取前200个字符作为摘要（与web目录完全一致）
            summary = (
                final_decision_content[:200].replace("#", "").replace("*", "").strip()
            )
            if len(final_decision_content) > 200:
                summary += "..."
            logger.info(
                f"📝 [SUMMARY] 从final_trade_decision提取摘要: {len(summary)}字符"
            )

    # 2. 如果没有final_trade_decision，从state中提取
    if not summary and isinstance(state, dict):
        final_decision = state.get("final_trade_decision", "")
        if isinstance(final_decision, str) and len(final_decision) > 50:
            summary = final_decision[:200].replace("#", "").replace("*", "").strip()
            if len(final_decision) > 200:
                summary += "..."
            logger.info(
                f"📝 [SUMMARY] 从state.final_trade_decision提取摘要: {len(summary)}字符"
            )

    # 3. 生成recommendation（从decision的reasoning）
    if isinstance(formatted_decision, dict):
        action = formatted_decision.get("action", "持有")
        target_price = formatted_decision.get("target_price")
        reasoning = formatted_decision.get("reasoning", "")

        # 生成投资建议
        recommendation = f"投资建议：{action}。"
        if target_price:
            recommendation += f"目标价格：{target_price}元。"
        if reasoning:
            recommendation += f"决策依据：{reasoning}"
        logger.info(f"💡 [RECOMMENDATION] 生成投资建议: {len(recommendation)}字符")

    # 4. 如果还是没有，从其他报告中提取
    if not summary and isinstance(reports, dict):
        # 尝试从其他报告中提取摘要
        for report_name, content in reports.items():
            if isinstance(content, str) and len(content) > 100:
                summary = content[:200].replace("#", "").replace("*", "").strip()
                if len(content) > 200:
                    summary += "..."
                logger.info(f"📝 [SUMMARY] 从{report_name}提取摘要: {len(summary)}字符")
                break

    # 5. 最后的备用方案
    if not summary:
        summary = f"对{request.stock_code}的分析已完成，请查看详细报告。"
        logger.warning("⚠️ [SUMMARY] 使用备用摘要")

    if not recommendation:
        recommendation = "请参考详细分析报告做出投资决策。"
        logger.warning("⚠️ [RECOMMENDATION] 使用备用建议")

    # 从决策中提取模型信息
    model_info = (
        decision.get("model_info", "Unknown")
        if isinstance(decision, dict)
        else "Unknown"
    )
    serializable_decision = normalize_payload(decision)
    serializable_state = normalize_payload(state)

    # 构建结果
    result = {
        "analysis_id": str(uuid.uuid4()),
        "stock_code": request.stock_code,
        "stock_symbol": request.stock_code,  # 添加stock_symbol字段以保持兼容性
        "analysis_date": analysis_date,
        "summary": summary,
        "recommendation": recommendation,
        "confidence_score": formatted_decision.get("confidence", 0.0)
        if isinstance(formatted_decision, dict)
        else 0.0,
        "risk_level": "中等",  # 可以根据risk_score计算
        "key_points": [],  # 可以从reasoning中提取关键点
        "detailed_analysis": serializable_decision,
        "execution_time": execution_time,
        "tokens_used": decision.get("tokens_used", 0)
        if isinstance(decision, dict)
        else 0,
        "state": serializable_state,
        # 添加分析师信息
        "analysts": request.parameters.selected_analysts if request.parameters else [],
        "research_depth": request.parameters.research_depth
        if request.parameters
        else "快速",
        # 添加提取的报告内容
        "reports": reports,
        # 🔥 关键修复：添加格式化后的decision字段！
        "decision": formatted_decision,
        # 🔥 添加模型信息字段
        "model_info": model_info,
        # 🆕 性能指标数据
        "performance_metrics": serializable_state.get("performance_metrics", {})
        if isinstance(serializable_state, dict)
        else {},
    }

    task_label = task_id or result["analysis_id"]
    logger.info(f"✅ [线程池] 分析完成: {task_label} - 耗时{execution_time:.2f}秒")

    # 🔍 调试：检查返回的result结构
    logger.info(f"🔍 [DEBUG] 返回result的键: {list(result.keys())}")
    logger.info(f"🔍 [DEBUG] 返回result中有decision: {bool(result.get('decision'))}")
    if result.get("decision"):
        decision = result["decision"]
        logger.info(f"🔍 [DEBUG] 返回decision内容: {decision}")

    return result
