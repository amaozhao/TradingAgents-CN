# ruff: noqa: F401,F403,F405,F821
class _GoogleToolCallHandlerMixin2:
    @staticmethod
    def generate_final_analysis_report(llm, messages: List, analyst_name: str) -> str:
        """
        生成最终分析报告 - 增强版，支持重试和模型切换

        Args:
            llm: LLM实例
            messages: 消息列表
            analyst_name: 分析师名称

        Returns:
            str: 分析报告
        """
        if not GoogleToolCallHandler.is_google_model(llm):
            logger.warning(f"⚠️ [{analyst_name}] 非Google模型，跳过Google工具处理器")
            return ""

        # 重试配置
        max_retries = 3
        retry_delay = 2  # 秒

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"🔍 [{analyst_name}] ===== 最终分析报告生成开始 (尝试 {attempt + 1}/{max_retries}) ====="
                )
                logger.debug(f"🔍 [{analyst_name}] LLM类型: {type(llm).__name__}")
                logger.debug(
                    f"🔍 [{analyst_name}] LLM模型: {getattr(llm, 'model', 'unknown')}"
                )
                logger.debug(f"🔍 [{analyst_name}] 消息数量: {len(messages)}")

                # 记录消息类型和长度
                for i, msg in enumerate(messages):
                    msg_type = type(msg).__name__
                    if hasattr(msg, "content"):
                        content_length = len(str(msg.content)) if msg.content else 0
                        logger.debug(
                            f"🔍 [{analyst_name}] 消息{i + 1}: {msg_type}, 长度: {content_length}"
                        )
                    else:
                        logger.debug(
                            f"🔍 [{analyst_name}] 消息{i + 1}: {msg_type}, 无content属性"
                        )

                # 构建分析提示 - 根据尝试次数调整
                if attempt == 0:
                    analysis_prompt = f"""
                    基于以上工具调用的结果，请为{analyst_name}生成一份详细的分析报告。

                    要求：
                    1. 综合分析所有工具返回的数据
                    2. 提供清晰的投资建议和风险评估
                    3. 报告应该结构化且易于理解
                    4. 包含具体的数据支撑和分析逻辑

                    请生成完整的分析报告：
                    """
                elif attempt == 1:
                    analysis_prompt = f"""
                    请简要分析{analyst_name}的工具调用结果并提供投资建议。
                    要求：简洁明了，包含关键数据和建议。
                    """
                else:
                    analysis_prompt = f"""
                    请为{analyst_name}提供一个简短的分析总结。
                    """

                logger.debug(
                    f"🔍 [{analyst_name}] 分析提示预览: {analysis_prompt[:100]}..."
                )

                # 优化消息序列
                optimized_messages = GoogleToolCallHandler._optimize_message_sequence(
                    messages, analysis_prompt
                )

                logger.info(
                    f"[{analyst_name}] 🚀 正在调用LLM.invoke() (尝试 {attempt + 1}/{max_retries})..."
                )

                # 调用LLM生成报告
                time = importlib.import_module("time")
                start_time = time.time()
                result = llm.invoke(optimized_messages)
                end_time = time.time()

                logger.info(
                    f"[{analyst_name}] ✅ LLM.invoke()调用完成 (耗时: {end_time - start_time:.2f}秒)"
                )

                # 详细检查返回结果
                logger.debug(
                    f"🔍 [{analyst_name}] 返回结果类型: {type(result).__name__}"
                )
                logger.debug(f"🔍 [{analyst_name}] 返回结果属性: {dir(result)}")

                if hasattr(result, "content"):
                    content = result.content
                    logger.debug(f"🔍 [{analyst_name}] 内容类型: {type(content)}")
                    logger.debug(
                        f"🔍 [{analyst_name}] 内容长度: {len(content) if content else 0}"
                    )

                    if not content or len(content.strip()) == 0:
                        logger.warning(
                            f"[{analyst_name}] ⚠️ Google模型返回内容为空 (尝试 {attempt + 1}/{max_retries})"
                        )

                        if attempt < max_retries - 1:
                            logger.info(
                                f"[{analyst_name}] 🔄 等待{retry_delay}秒后重试..."
                            )
                            time.sleep(retry_delay)
                            continue
                        else:
                            logger.warning(
                                f"[{analyst_name}] ⚠️ Google模型最终分析报告生成失败 - 所有重试均返回空内容"
                            )
                            # 使用降级报告
                            fallback_report = (
                                GoogleToolCallHandler._generate_fallback_report(
                                    messages, analyst_name
                                )
                            )
                            logger.info(
                                f"[{analyst_name}] 🔄 使用降级报告，长度: {len(fallback_report)} 字符"
                            )
                            return fallback_report
                    else:
                        logger.info(
                            f"[{analyst_name}] ✅ 成功生成分析报告，长度: {len(content)} 字符"
                        )
                        return content
                else:
                    logger.error(
                        f"[{analyst_name}] ❌ 返回结果没有content属性 (尝试 {attempt + 1}/{max_retries})"
                    )

                    if attempt < max_retries - 1:
                        logger.info(f"[{analyst_name}] 🔄 等待{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        fallback_report = (
                            GoogleToolCallHandler._generate_fallback_report(
                                messages, analyst_name
                            )
                        )
                        logger.info(
                            f"[{analyst_name}] 🔄 使用降级报告，长度: {len(fallback_report)} 字符"
                        )
                        return fallback_report

            except Exception as e:
                logger.error(
                    f"[{analyst_name}] ❌ LLM调用异常 (尝试 {attempt + 1}/{max_retries}): {e}"
                )
                logger.error(f"[{analyst_name}] ❌ 异常类型: {type(e).__name__}")
                logger.error(
                    f"[{analyst_name}] ❌ 完整异常信息:\n{traceback.format_exc()}"
                )

                if attempt < max_retries - 1:
                    logger.info(f"[{analyst_name}] 🔄 等待{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                    continue
                else:
                    # 使用降级报告
                    fallback_report = GoogleToolCallHandler._generate_fallback_report(
                        messages, analyst_name
                    )
                    logger.info(
                        f"[{analyst_name}] 🔄 使用降级报告，长度: {len(fallback_report)} 字符"
                    )
                    return fallback_report

        # 如果所有重试都失败，返回降级报告
        fallback_report = GoogleToolCallHandler._generate_fallback_report(
            messages, analyst_name
        )
        logger.info(
            f"[{analyst_name}] 🔄 所有重试失败，使用降级报告，长度: {len(fallback_report)} 字符"
        )
        return fallback_report

    @staticmethod
    def _optimize_message_sequence(messages: List, analysis_prompt: str) -> List:
        """
        优化消息序列，确保在合理长度内

        Args:
            messages: 原始消息列表
            analysis_prompt: 分析提示

        Returns:
            List: 优化后的消息列表
        """
        # 计算总长度
        total_length = sum(
            len(str(msg.content)) for msg in messages if hasattr(msg, "content")
        )
        total_length += len(analysis_prompt)

        if total_length <= 50000:
            # 长度合理，直接添加分析提示
            return messages + [HumanMessage(content=analysis_prompt)]

        # 需要优化：保留关键消息
        optimized_messages: List[Any] = []

        # 保留最后的用户消息
        for msg in messages:
            if isinstance(msg, HumanMessage):
                optimized_messages = [msg]
                break

        # 保留AI消息和工具消息，但截断过长内容
        for msg in messages:
            if isinstance(msg, (AIMessage, ToolMessage)):
                if hasattr(msg, "content") and len(str(msg.content)) > 5000:
                    # 截断过长内容
                    truncated_content = (
                        str(msg.content)[:5000] + "\n\n[注：数据已截断以确保处理效率]"
                    )
                    if isinstance(msg, AIMessage):
                        optimized_msg = AIMessage(content=truncated_content)
                    else:
                        optimized_msg = ToolMessage(
                            content=truncated_content,
                            tool_call_id=getattr(msg, "tool_call_id", "unknown"),
                        )
                    optimized_messages.append(optimized_msg)
                else:
                    optimized_messages.append(msg)

        # 添加分析提示
        optimized_messages.append(HumanMessage(content=analysis_prompt))

        return optimized_messages

    @staticmethod
    def _generate_fallback_report(messages: List, analyst_name: str) -> str:
        """
        生成降级报告

        Args:
            messages: 消息列表
            analyst_name: 分析师名称

        Returns:
            str: 降级报告
        """
        ToolMessage = getattr(
            importlib.import_module("langchain_core.messages"), "ToolMessage"
        )

        # 提取工具结果
        tool_results = []
        for msg in messages:
            if isinstance(msg, ToolMessage) and hasattr(msg, "content"):
                content = str(msg.content)
                if len(content) > 1000:
                    content = content[:1000] + "\n\n[注：数据已截断]"
                tool_results.append(content)

        if tool_results:
            tool_summary = "\n\n".join(
                [
                    f"工具结果 {i + 1}:\n{result}"
                    for i, result in enumerate(tool_results)
                ]
            )
            report = f"{analyst_name}工具调用完成，获得以下数据：\n\n{tool_summary}\n\n注：由于模型响应异常，此为基于工具数据的简化报告。"
        else:
            report = f"{analyst_name}分析完成，但未能获取到有效的工具数据。建议检查数据源或重新尝试分析。"

        return report

    @staticmethod
    def create_analysis_prompt(
        ticker: str,
        company_name: str,
        analyst_type: str,
        specific_requirements: str = "",
    ) -> str:
        """
        创建标准的分析提示词

        Args:
            ticker: 股票代码
            company_name: 公司名称
            analyst_type: 分析师类型（如"技术分析"、"基本面分析"等）
            specific_requirements: 特定要求

        Returns:
            str: 分析提示词
        """

        base_prompt = f"""现在请基于上述工具获取的数据，生成详细的{analyst_type}报告。

**股票信息：**
- 公司名称：{company_name}
- 股票代码：{ticker}

**分析要求：**
1. 报告必须基于工具返回的真实数据进行分析
2. 包含具体的数值和专业分析
3. 提供明确的投资建议和风险提示
4. 报告长度不少于800字
5. 使用中文撰写
6. 确保在分析中正确使用公司名称"{company_name}"和股票代码"{ticker}"

{specific_requirements}

请生成专业、详细的{analyst_type}报告。"""

        return base_prompt
