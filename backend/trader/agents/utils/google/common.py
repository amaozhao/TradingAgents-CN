from .imports import AIMessage, Any, Dict, HumanMessage, List, ToolMessage, Tuple, importlib, logger


def _handler():
    handler = globals().get("GoogleToolCallHandler")
    if handler is not None:
        return handler
    from .models import GoogleToolCallHandler

    return GoogleToolCallHandler

def _message_content_text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return " ".join(parts)
    return str(content)


class _GoogleToolCallHandlerMixin1:
    @staticmethod
    def is_google_model(llm) -> bool:
        """检查是否为Google模型"""
        return "Google" in llm.__class__.__name__ or "ChatGoogleOpenAI" in llm.__class__.__name__

    @staticmethod
    def handle_google_tool_calls(
        result: AIMessage,
        llm: Any,
        tools: List[Any],
        state: Dict[str, Any],
        analysis_prompt_template: str,
        analyst_name: str = "分析师",
    ) -> Tuple[str, List[Any]]:
        """
        统一处理Google模型的工具调用

        Args:
            result: LLM的第一次调用结果
            llm: 语言模型实例
            tools: 可用工具列表
            state: 当前状态
            analysis_prompt_template: 分析提示词模板
            analyst_name: 分析师名称

        Returns:
            Tuple[str, List[Any]]: (分析报告, 消息列表)
        """

        # 验证输入参数
        logger.info(f"[{analyst_name}] 🔍 开始Google工具调用处理...")
        logger.debug(f"[{analyst_name}] 🔍 LLM类型: {llm.__class__.__name__}")
        logger.debug(f"[{analyst_name}] 🔍 工具数量: {len(tools) if tools else 0}")
        logger.debug(f"[{analyst_name}] 🔍 状态类型: {type(state).__name__ if state else None}")

        if not _handler().is_google_model(llm):
            logger.warning(f"[{analyst_name}] ⚠️ 非Google模型，跳过特殊处理")
            logger.debug(f"[{analyst_name}] 🔍 模型检查失败: {llm.__class__.__name__}")
            # 非Google模型，返回原始内容
            return _message_content_text(result), [result]

        logger.info(f"[{analyst_name}] ✅ 确认为Google模型")
        logger.debug(f"[{analyst_name}] 🔍 结果类型: {type(result).__name__}")
        logger.debug(f"[{analyst_name}] 🔍 结果属性: {[attr for attr in dir(result) if not attr.startswith('_')]}")

        # 检查API调用是否成功
        if not hasattr(result, "content"):
            logger.error(f"[{analyst_name}] ❌ Google模型API调用失败，无返回内容")
            logger.debug(f"[{analyst_name}] 🔍 结果对象缺少content属性")
            return "Google模型API调用失败", []

        # 检查是否有工具调用
        if not hasattr(result, "tool_calls"):
            logger.warning(f"[{analyst_name}] ⚠️ 结果对象没有tool_calls属性")
            logger.debug(f"[{analyst_name}] 🔍 可用属性: {[attr for attr in dir(result) if not attr.startswith('_')]}")
            return _message_content_text(result), [result]

        if not result.tool_calls:
            # 改进：提供更详细的诊断信息
            logger.info(f"[{analyst_name}] ℹ️ Google模型未调用工具，可能原因：")
            logger.info(f"[{analyst_name}]   - 输入消息为空或格式不正确")
            logger.info(f"[{analyst_name}]   - 模型认为不需要调用工具")
            logger.info(f"[{analyst_name}]   - 工具绑定可能存在问题")

            # 检查输入消息
            if "messages" in state:
                messages = state["messages"]
                if not messages:
                    logger.warning(f"[{analyst_name}] ⚠️ 输入消息列表为空")
                else:
                    logger.info(f"[{analyst_name}] 📝 输入消息数量: {len(messages)}")
                    for i, msg in enumerate(messages):
                        msg_type = type(msg).__name__
                        content_preview = str(msg.content)[:100] if hasattr(msg, "content") else "无内容"
                        logger.info(f"[{analyst_name}]   消息 {i + 1}: {msg_type} - {content_preview}...")

            # 检查内容是否为分析报告
            content = _message_content_text(result)
            logger.info(f"[{analyst_name}] 🔍 检查返回内容是否为分析报告...")
            logger.debug(f"[{analyst_name}] 🔍 内容类型: {type(content)}")
            logger.debug(f"[{analyst_name}] 🔍 内容长度: {len(content) if content else 0}")

            # 检查内容是否包含分析报告的特征
            is_analysis_report = False
            analysis_keywords = [
                "分析",
                "报告",
                "总结",
                "评估",
                "建议",
                "风险",
                "趋势",
                "市场",
                "股票",
                "投资",
            ]

            if content:
                # 检查内容长度和关键词
                if len(content) > 200:  # 假设分析报告至少有200个字符
                    keyword_count = sum(1 for keyword in analysis_keywords if keyword in content)
                    is_analysis_report = keyword_count >= 3  # 至少包含3个关键词

                logger.info(f"[{analyst_name}] 🔍 内容判断为{'分析报告' if is_analysis_report else '非分析报告'}")

                if is_analysis_report:
                    logger.info(f"[{analyst_name}] ✅ Google模型直接返回了分析报告，长度: {len(content)} 字符")
                    return content, [result]

            # 返回原始内容，但添加说明
            return _message_content_text(result), [result]

        logger.info(f"[{analyst_name}] 🔧 Google模型调用了 {len(result.tool_calls)} 个工具")

        # 记录工具调用详情
        for i, tool_call in enumerate(result.tool_calls):
            logger.info(f"[{analyst_name}] 工具 {i + 1}:")
            logger.info(f"[{analyst_name}]   ID: {tool_call.get('id', 'N/A')}")
            logger.info(f"[{analyst_name}]   名称: {tool_call.get('name', 'N/A')}")
            logger.info(f"[{analyst_name}]   参数: {tool_call.get('args', {})}")

        try:
            # 执行工具调用
            tool_messages = []
            tool_results = []
            executed_tools = set()  # 防止重复调用同一工具

            logger.info(f"[{analyst_name}] 🔧 开始执行 {len(result.tool_calls)} 个工具调用...")

            # 验证工具调用格式
            valid_tool_calls = []
            for i, tool_call in enumerate(result.tool_calls):
                if _handler()._validate_tool_call(tool_call, i, analyst_name):
                    valid_tool_calls.append(tool_call)
                else:
                    # 尝试修复工具调用
                    fixed_tool_call = _handler()._fix_tool_call(tool_call, i, analyst_name)
                    if fixed_tool_call:
                        valid_tool_calls.append(fixed_tool_call)

            logger.info(f"[{analyst_name}] 🔧 有效工具调用: {len(valid_tool_calls)}/{len(result.tool_calls)}")

            for i, tool_call in enumerate(valid_tool_calls):
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id")

                # 防止重复调用同一工具（特别是统一市场数据工具）
                tool_signature = f"{tool_name}_{hash(str(tool_args))}"
                if tool_signature in executed_tools:
                    logger.warning(f"[{analyst_name}] ⚠️ 跳过重复工具调用: {tool_name}")
                    continue
                executed_tools.add(tool_signature)

                logger.info(f"[{analyst_name}] 🛠️ 执行工具 {i + 1}/{len(valid_tool_calls)}: {tool_name}")
                logger.info(f"[{analyst_name}] 参数: {tool_args}")
                logger.debug(f"[{analyst_name}] 🔧 工具调用详情: {tool_call}")

                # 找到对应的工具并执行
                tool_result = None
                available_tools = []

                for tool in tools:
                    current_tool_name = _handler()._get_tool_name(tool)
                    available_tools.append(current_tool_name)

                    if current_tool_name == tool_name:
                        try:
                            logger.debug(f"[{analyst_name}] 🔧 找到工具: {tool.__class__.__name__}")
                            logger.debug(f"[{analyst_name}] 🔧 工具类型检查...")

                            # 检查工具类型并相应调用
                            if hasattr(tool, "invoke"):
                                # LangChain工具，使用invoke方法
                                logger.info(f"[{analyst_name}] 🚀 正在调用LangChain工具.invoke()...")
                                tool_result = tool.invoke(tool_args)
                                logger.info(
                                    f"[{analyst_name}] ✅ LangChain工具执行成功，结果长度: {len(str(tool_result))} 字符"
                                )
                                logger.debug(f"[{analyst_name}] 🔧 工具结果类型: {type(tool_result)}")
                            elif callable(tool):
                                # 普通Python函数，直接调用
                                logger.info(f"[{analyst_name}] 🚀 正在调用Python函数工具...")
                                tool_result = tool(**tool_args)
                                logger.info(
                                    f"[{analyst_name}] ✅ Python函数工具执行成功，结果长度: {len(str(tool_result))} 字符"
                                )
                                logger.debug(f"[{analyst_name}] 🔧 工具结果类型: {type(tool_result)}")
                            else:
                                logger.error(f"[{analyst_name}] ❌ 工具类型不支持: {type(tool)}")
                                tool_result = f"工具类型不支持: {type(tool)}"
                            break
                        except Exception as tool_error:
                            logger.error(f"[{analyst_name}] ❌ 工具执行失败: {tool_error}")
                            logger.error(f"[{analyst_name}] ❌ 异常类型: {type(tool_error).__name__}")
                            logger.error(f"[{analyst_name}] ❌ 异常详情: {str(tool_error)}")

                            # 记录详细的异常堆栈
                            traceback = importlib.import_module("traceback")
                            error_traceback = traceback.format_exc()
                            logger.error(f"[{analyst_name}] ❌ 工具执行异常堆栈:\n{error_traceback}")

                            tool_result = f"工具执行失败: {str(tool_error)}"

                logger.debug(f"[{analyst_name}] 🔧 可用工具列表: {available_tools}")

                if tool_result is None:
                    tool_result = f"未找到工具: {tool_name}"
                    logger.warning(f"[{analyst_name}] ⚠️ 未找到工具: {tool_name}")
                    logger.debug(f"[{analyst_name}] ⚠️ 工具名称不匹配，期望: {tool_name}, 可用: {available_tools}")

                # 创建工具消息
                tool_message = ToolMessage(content=str(tool_result), tool_call_id=tool_id)
                tool_messages.append(tool_message)
                tool_results.append(tool_result)
                logger.debug(f"[{analyst_name}] 🔧 创建工具消息，ID: {tool_message.tool_call_id}")

            logger.info(f"[{analyst_name}] 🔧 工具调用完成，成功: {len(tool_results)}, 总计: {len(result.tool_calls)}")

            # 第二次调用模型生成最终分析报告
            logger.info(f"[{analyst_name}] 🚀 基于工具结果生成最终分析报告...")

            # 🔧 [优化] 不累积历史消息，只保留当前分析所需的消息
            # 原因：
            # 1. 基本面分析师不需要其他分析师的历史消息
            # 2. 避免消息过长（之前累积到 55,096 字符）
            # 3. 降低 token 消耗和成本
            # 4. 后续有 Research Manager 负责综合所有分析师的报告
            safe_messages = []

            # 只保留初始的用户消息（如果有）
            if "messages" in state and state["messages"]:
                # 只保留第一条 HumanMessage（通常是初始任务描述）
                for msg in state["messages"]:
                    if isinstance(msg, HumanMessage):
                        safe_messages.append(msg)
                        logger.debug(f"[{analyst_name}] 📝 保留初始用户消息")
                        break

            # 添加当前结果（AI 的工具调用）
            if hasattr(result, "content"):
                safe_messages.append(result)
                logger.debug(f"[{analyst_name}] 📝 添加 AI 工具调用消息")

            # 添加工具消息（工具执行结果）
            safe_messages.extend(tool_messages)
            logger.debug(f"[{analyst_name}] 📝 添加 {len(tool_messages)} 条工具消息")

            # 添加分析提示
            safe_messages.append(HumanMessage(content=analysis_prompt_template))
            logger.debug(f"[{analyst_name}] 📝 添加分析提示")

            # 记录消息序列信息
            total_length = sum(len(str(msg.content)) for msg in safe_messages if hasattr(msg, "content"))
            logger.info(f"[{analyst_name}] 📊 消息序列: {len(safe_messages)} 条消息, 总长度: {total_length:,} 字符")

            # 检查消息序列是否为空
            if not safe_messages:
                logger.error(f"[{analyst_name}] ❌ 消息序列为空，无法生成分析报告")
                tool_summary = "\n\n".join([
                    f"工具结果 {i + 1}:\n{str(result)}" for i, result in enumerate(tool_results)
                ])
                report = f"{analyst_name}工具调用完成，获得以下数据：\n\n{tool_summary}"
                return report, [result] + tool_messages

            # 生成最终分析报告
            try:
                logger.info(f"[{analyst_name}] 🔄 开始调用Google模型生成最终分析报告...")
                logger.debug(f"[{analyst_name}] 📋 LLM类型: {llm.__class__.__name__}")
                logger.debug(f"[{analyst_name}] 📋 消息数量: {len(safe_messages)}")

                # 记录每个消息的类型和长度
                for i, msg in enumerate(safe_messages):
                    msg_type = msg.__class__.__name__
                    msg_length = len(str(msg.content)) if hasattr(msg, "content") else 0
                    logger.debug(f"[{analyst_name}] 📋 消息 {i + 1}: {msg_type}, 长度: {msg_length}")

                # 记录分析提示的内容（前200字符）
                analysis_msg = safe_messages[-1] if safe_messages else None
                if analysis_msg and hasattr(analysis_msg, "content"):
                    prompt_preview = (
                        str(analysis_msg.content)[:200] + "..."
                        if len(str(analysis_msg.content)) > 200
                        else str(analysis_msg.content)
                    )
                    logger.debug(f"[{analyst_name}] 📋 分析提示预览: {prompt_preview}")

                logger.info(f"[{analyst_name}] 🚀 正在调用LLM.invoke()...")
                final_result = llm.invoke(safe_messages)
                logger.info(f"[{analyst_name}] ✅ LLM.invoke()调用完成")

                # 详细检查返回结果
                logger.debug(f"[{analyst_name}] 🔍 检查LLM返回结果...")
                logger.debug(f"[{analyst_name}] 🔍 返回结果类型: {type(final_result)}")
                logger.debug(f"[{analyst_name}] 🔍 返回结果属性: {dir(final_result)}")

                if hasattr(final_result, "content"):
                    content = final_result.content
                    logger.debug(f"[{analyst_name}] 🔍 内容类型: {type(content)}")
                    logger.debug(f"[{analyst_name}] 🔍 内容长度: {len(content) if content else 0}")
                    logger.debug(f"[{analyst_name}] 🔍 内容是否为空: {not content}")

                    if content:
                        content_preview = content[:200] + "..." if len(content) > 200 else content
                        logger.debug(f"[{analyst_name}] 🔍 内容预览: {content_preview}")

                        report = content
                        logger.info(f"[{analyst_name}] ✅ Google模型最终分析报告生成成功，长度: {len(report)} 字符")

                        # 返回完整的消息序列
                        all_messages = [result] + tool_messages + [final_result]
                        return report, all_messages
                    else:
                        logger.warning(f"[{analyst_name}] ⚠️ Google模型返回内容为空")
                        logger.debug(f"[{analyst_name}] 🔍 空内容详情: repr={repr(content)}")
                else:
                    logger.warning(f"[{analyst_name}] ⚠️ Google模型返回结果没有content属性")
                    logger.debug(
                        f"[{analyst_name}] 🔍 可用属性: {[attr for attr in dir(final_result) if not attr.startswith('_')]}"
                    )

                # 如果到这里，说明内容为空或没有content属性
                logger.warning(f"[{analyst_name}] ⚠️ Google模型最终分析报告生成失败 - 内容为空")
                # 降级处理：基于工具结果生成简单报告
                tool_summary = "\n\n".join([
                    f"工具结果 {i + 1}:\n{str(result)}" for i, result in enumerate(tool_results)
                ])
                report = f"{analyst_name}工具调用完成，获得以下数据：\n\n{tool_summary}"
                logger.info(f"[{analyst_name}] 🔄 使用降级报告，长度: {len(report)} 字符")
                return report, [result] + tool_messages

            except Exception as final_error:
                logger.error(f"[{analyst_name}] ❌ 最终分析报告生成失败: {final_error}")
                logger.error(f"[{analyst_name}] ❌ 异常类型: {type(final_error).__name__}")
                logger.error(f"[{analyst_name}] ❌ 异常详情: {str(final_error)}")

                # 记录详细的异常堆栈
                traceback = importlib.import_module("traceback")
                error_traceback = traceback.format_exc()
                logger.error(f"[{analyst_name}] ❌ 异常堆栈:\n{error_traceback}")

                # 降级处理：基于工具结果生成简单报告
                tool_summary = "\n\n".join([
                    f"工具结果 {i + 1}:\n{str(result)}" for i, result in enumerate(tool_results)
                ])
                report = f"{analyst_name}工具调用完成，获得以下数据：\n\n{tool_summary}"
                logger.info(f"[{analyst_name}] 🔄 异常后使用降级报告，长度: {len(report)} 字符")
                return report, [result] + tool_messages

        except Exception as e:
            logger.error(f"[{analyst_name}] ❌ Google模型工具调用处理失败: {e}")
            traceback = importlib.import_module("traceback")
            traceback.print_exc()

            # 降级处理：返回工具调用信息
            tool_names = [tc.get("name", "unknown") for tc in result.tool_calls]
            report = f"{analyst_name}调用了工具 {tool_names} 但处理失败: {str(e)}"
            return report, [result]

    @staticmethod
    def _get_tool_name(tool):
        """获取工具名称"""
        if hasattr(tool, "name"):
            return tool.name
        elif hasattr(tool, "__name__"):
            return tool.__name__
        else:
            return str(tool)

    @staticmethod
    def _validate_tool_call(tool_call, index, analyst_name):
        """验证工具调用格式"""
        try:
            if not isinstance(tool_call, dict):
                logger.warning(f"[{analyst_name}] ⚠️ 工具调用 {index} 不是字典格式: {type(tool_call)}")
                return False

            # 检查必需字段
            required_fields = ["name", "args", "id"]
            for field in required_fields:
                if field not in tool_call:
                    logger.warning(f"[{analyst_name}] ⚠️ 工具调用 {index} 缺少字段 '{field}': {tool_call}")
                    return False

            # 检查工具名称
            tool_name = tool_call.get("name")
            if not isinstance(tool_name, str) or not tool_name.strip():
                logger.warning(f"[{analyst_name}] ⚠️ 工具调用 {index} 工具名称无效: {tool_name}")
                return False

            # 检查参数
            tool_args = tool_call.get("args")
            if not isinstance(tool_args, dict):
                logger.warning(f"[{analyst_name}] ⚠️ 工具调用 {index} 参数不是字典格式: {type(tool_args)}")
                return False

            # 检查ID
            tool_id = tool_call.get("id")
            if not isinstance(tool_id, str) or not tool_id.strip():
                logger.warning(f"[{analyst_name}] ⚠️ 工具调用 {index} ID无效: {tool_id}")
                return False

            logger.debug(f"[{analyst_name}] ✅ 工具调用 {index} 验证通过: {tool_name}")
            return True

        except Exception as e:
            logger.error(f"[{analyst_name}] ❌ 工具调用 {index} 验证异常: {e}")
            return False

    @staticmethod
    def _fix_tool_call(tool_call, index, analyst_name):
        """尝试修复工具调用格式"""
        try:
            logger.info(f"[{analyst_name}] 🔧 尝试修复工具调用 {index}: {tool_call}")

            if not isinstance(tool_call, dict):
                logger.warning(f"[{analyst_name}] ❌ 无法修复非字典格式的工具调用: {type(tool_call)}")
                return None

            fixed_tool_call = tool_call.copy()

            # 修复工具名称
            if "name" not in fixed_tool_call or not isinstance(fixed_tool_call["name"], str):
                if "function" in fixed_tool_call and isinstance(fixed_tool_call["function"], dict):
                    # OpenAI格式转换
                    function_data = fixed_tool_call["function"]
                    if "name" in function_data:
                        fixed_tool_call["name"] = function_data["name"]
                        if "arguments" in function_data:
                            json = importlib.import_module("json")
                            try:
                                if isinstance(function_data["arguments"], str):
                                    fixed_tool_call["args"] = json.loads(function_data["arguments"])
                                else:
                                    fixed_tool_call["args"] = function_data["arguments"]
                            except json.JSONDecodeError:
                                fixed_tool_call["args"] = {}
                else:
                    logger.warning(f"[{analyst_name}] ❌ 无法确定工具名称")
                    return None

            # 修复参数
            if "args" not in fixed_tool_call:
                fixed_tool_call["args"] = {}
            elif not isinstance(fixed_tool_call["args"], dict):
                try:
                    json = importlib.import_module("json")
                    if isinstance(fixed_tool_call["args"], str):
                        fixed_tool_call["args"] = json.loads(fixed_tool_call["args"])
                    else:
                        fixed_tool_call["args"] = {}
                except Exception:
                    fixed_tool_call["args"] = {}

            # 修复ID
            if "id" not in fixed_tool_call or not isinstance(fixed_tool_call["id"], str):
                uuid = importlib.import_module("uuid")
                fixed_tool_call["id"] = f"call_{uuid.uuid4().hex[:8]}"

            # 验证修复后的工具调用
            if _handler()._validate_tool_call(fixed_tool_call, index, analyst_name):
                logger.info(f"[{analyst_name}] ✅ 工具调用 {index} 修复成功: {fixed_tool_call['name']}")
                return fixed_tool_call
            else:
                logger.warning(f"[{analyst_name}] ❌ 工具调用 {index} 修复失败")
                return None

        except Exception as e:
            logger.error(f"[{analyst_name}] ❌ 工具调用 {index} 修复异常: {e}")
            return None

    @staticmethod
    def handle_simple_google_response(result: AIMessage, llm: Any, analyst_name: str = "分析师") -> str:
        """
        处理简单的Google模型响应（无工具调用）

        Args:
            result: LLM调用结果
            llm: 语言模型实例
            analyst_name: 分析师名称

        Returns:
            str: 分析报告
        """

        if not _handler().is_google_model(llm):
            return _message_content_text(result)

        content = _message_content_text(result)
        logger.info(f"[{analyst_name}] 📝 Google模型直接回复，长度: {len(content)} 字符")

        # 检查内容长度，如果过长进行处理
        if len(content) > 15000:
            logger.warning(f"[{analyst_name}] ⚠️ Google模型输出过长，进行截断处理...")
            return content[:10000] + "\n\n[注：内容已截断以确保可读性]"

        return content
