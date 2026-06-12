from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import importlib, logger
    from .setup import extract_risk_assessment, translate_analyst_labels

def format_analysis(results):
    """格式化分析结果用于显示"""

    if not results["success"]:
        return {"error": results["error"], "success": False}

    state = results["state"]
    decision = results["decision"]

    # 提取关键信息
    # decision 可能是字符串（如 "BUY", "SELL", "HOLD"）或字典
    if isinstance(decision, str):
        # 将英文投资建议转换为中文
        action_translation = {
            "BUY": "买入",
            "SELL": "卖出",
            "HOLD": "持有",
            "buy": "买入",
            "sell": "卖出",
            "hold": "持有",
        }
        action = action_translation.get(decision.strip(), decision.strip())

        formatted_decision = {
            "action": action,
            "confidence": 0.7,  # 默认置信度
            "risk_score": 0.3,  # 默认风险分数
            "target_price": None,  # 字符串格式没有目标价格
            "reasoning": f"基于AI分析，建议{decision.strip().upper()}",
        }
    elif isinstance(decision, dict):
        # 处理目标价格 - 确保正确提取数值
        target_price = decision.get("target_price")
        if target_price is not None and target_price != "N/A":
            try:
                # 尝试转换为浮点数
                if isinstance(target_price, str):
                    # 移除货币符号和空格
                    clean_price = target_price.replace("$", "").replace("¥", "").replace("￥", "").strip()
                    target_price = float(clean_price) if clean_price and clean_price != "None" else None
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
    else:
        # 处理其他类型
        formatted_decision = {
            "action": "持有",
            "confidence": 0.5,
            "risk_score": 0.3,
            "target_price": None,
            "reasoning": f"分析结果: {str(decision)}",
        }

    # 格式化状态信息
    formatted_state = {}

    # 处理各个分析模块的结果 - 包含完整的智能体团队分析
    analysis_keys = [
        "market_report",
        "fundamentals_report",
        "sentiment_report",
        "news_report",
        "risk_assessment",
        "investment_plan",
        # 添加缺失的团队决策数据，确保与CLI端一致
        "investment_debate_state",  # 研究团队辩论（多头/空头研究员）
        "trader_investment_plan",  # 交易团队计划
        "risk_debate_state",  # 风险管理团队决策
        "final_trade_decision",  # 最终交易决策
    ]

    # 添加调试信息
    logger.debug(f"🔍 [格式化调试] 原始state中的键: {list(state.keys())}")
    for key in state.keys():
        if isinstance(state[key], str):
            logger.debug(f"🔍 [格式化调试] {key}: 字符串长度 {len(state[key])}")
        elif isinstance(state[key], dict):
            logger.debug(f"🔍 [格式化调试] {key}: 字典，包含键 {list(state[key].keys())}")
        else:
            logger.debug(f"🔍 [格式化调试] {key}: {type(state[key])}")

    for key in analysis_keys:
        if key in state:
            # 对文本内容进行中文化处理
            content = state[key]
            if isinstance(content, str):
                content = translate_analyst_labels(content)
                logger.debug(f"🔍 [格式化调试] 处理字符串字段 {key}: 长度 {len(content)}")
            elif isinstance(content, dict):
                logger.debug(f"🔍 [格式化调试] 处理字典字段 {key}: 包含键 {list(content.keys())}")
            formatted_state[key] = content
        elif key == "risk_assessment":
            # 特殊处理：从 risk_debate_state 生成 risk_assessment
            risk_assessment = extract_risk_assessment(state)
            if risk_assessment:
                formatted_state[key] = risk_assessment
        else:
            logger.debug(f"🔍 [格式化调试] 缺失字段: {key}")

    return {
        "stock_symbol": results["stock_symbol"],
        "decision": formatted_decision,
        "state": formatted_state,
        "success": True,
        # 将配置信息放在顶层，供前端直接访问
        "analysis_date": results["analysis_date"],
        "analysts": results["analysts"],
        "research_depth": results["research_depth"],
        "llm_provider": results.get("llm_provider", "dashscope"),
        "llm_model": results["llm_model"],
        "metadata": {
            "analysis_date": results["analysis_date"],
            "analysts": results["analysts"],
            "research_depth": results["research_depth"],
            "llm_provider": results.get("llm_provider", "dashscope"),
            "llm_model": results["llm_model"],
        },
    }


def validate_analysis_params(stock_symbol, analysis_date, analysts, research_depth, market_type="美股"):
    """验证分析参数"""

    errors = []

    # 验证股票代码
    if not stock_symbol or len(stock_symbol.strip()) == 0:
        errors.append("股票代码不能为空")
    elif len(stock_symbol.strip()) > 10:
        errors.append("股票代码长度不能超过10个字符")
    else:
        # 根据市场类型验证代码格式
        symbol = stock_symbol.strip()
        if market_type == "A股":
            # A股：6位数字
            re = importlib.import_module("re")
            if not re.match(r"^\d{6}$", symbol):
                errors.append("A股代码格式错误，应为6位数字（如：000001）")
        elif market_type == "港股":
            # 港股：4-5位数字.HK 或 纯4-5位数字
            re = importlib.import_module("re")
            symbol_upper = symbol.upper()
            # 检查是否为 XXXX.HK 或 XXXXX.HK 格式
            hk_format = re.match(r"^\d{4,5}\.HK$", symbol_upper)
            # 检查是否为纯4-5位数字格式
            digit_format = re.match(r"^\d{4,5}$", symbol)

            if not (hk_format or digit_format):
                errors.append("港股代码格式错误，应为4位数字.HK（如：0700.HK）或4位数字（如：0700）")
        elif market_type == "美股":
            # 美股：1-5位字母
            re = importlib.import_module("re")
            if not re.match(r"^[A-Z]{1,5}$", symbol.upper()):
                errors.append("美股代码格式错误，应为1-5位字母（如：AAPL）")

    # 验证分析师列表
    if not analysts or len(analysts) == 0:
        errors.append("必须至少选择一个分析师")

    valid_analysts = ["market", "social", "news", "fundamentals"]
    invalid_analysts = [a for a in analysts if a not in valid_analysts]
    if invalid_analysts:
        errors.append(f"无效的分析师类型: {', '.join(invalid_analysts)}")

    # 验证研究深度
    if not isinstance(research_depth, int) or research_depth < 1 or research_depth > 5:
        errors.append("研究深度必须是1-5之间的整数")

    # 验证分析日期
    try:
        datetime = getattr(importlib.import_module("datetime"), "datetime")
        datetime.strptime(analysis_date, "%Y-%m-%d")
    except ValueError:
        errors.append("分析日期格式无效，应为YYYY-MM-DD格式")

    return len(errors) == 0, errors


def get_supported_stocks():
    """获取支持的股票列表"""

    # 常见的美股股票代码
    popular_stocks = [
        {"symbol": "AAPL", "name": "苹果公司", "sector": "科技"},
        {"symbol": "MSFT", "name": "微软", "sector": "科技"},
        {"symbol": "GOOGL", "name": "谷歌", "sector": "科技"},
        {"symbol": "AMZN", "name": "亚马逊", "sector": "消费"},
        {"symbol": "TSLA", "name": "特斯拉", "sector": "汽车"},
        {"symbol": "NVDA", "name": "英伟达", "sector": "科技"},
        {"symbol": "META", "name": "Meta", "sector": "科技"},
        {"symbol": "NFLX", "name": "奈飞", "sector": "媒体"},
        {"symbol": "AMD", "name": "AMD", "sector": "科技"},
        {"symbol": "INTC", "name": "英特尔", "sector": "科技"},
        {"symbol": "SPY", "name": "S&P 500 ETF", "sector": "ETF"},
        {"symbol": "QQQ", "name": "纳斯达克100 ETF", "sector": "ETF"},
    ]

    return popular_stocks


def generate_demo_results_deprecated(
    stock_symbol,
    analysis_date,
    analysts,
    research_depth,
    llm_provider,
    llm_model,
    error_msg,
    market_type="美股",
):
    """
    已弃用：生成演示分析结果

    注意：此函数已弃用，因为演示数据会误导用户。
    现在我们使用占位符来代替演示数据。
    """

    random = importlib.import_module("random")

    # 根据市场类型设置货币符号和价格范围
    if market_type == "港股":
        currency_symbol = "HK$"
        price_range = (50, 500)  # 港股价格范围
        market_name = "港股"
    elif market_type == "A股":
        currency_symbol = "¥"
        price_range = (5, 100)  # A股价格范围
        market_name = "A股"
    else:  # 美股
        currency_symbol = "$"
        price_range = (50, 300)  # 美股价格范围
        market_name = "美股"

    # 生成模拟决策
    actions = ["买入", "持有", "卖出"]
    action = random.choice(actions)

    demo_decision = {
        "action": action,
        "confidence": round(random.uniform(0.6, 0.9), 2),
        "risk_score": round(random.uniform(0.2, 0.7), 2),
        "target_price": round(random.uniform(*price_range), 2),
        "reasoning": f"""
基于对{market_name}{stock_symbol}的综合分析，我们的AI分析团队得出以下结论：

**投资建议**: {action}
**目标价格**: {currency_symbol}{round(random.uniform(*price_range), 2)}

**主要分析要点**:
1. **技术面分析**: 当前价格趋势显示{"上涨" if action == "买入" else "下跌" if action == "卖出" else "横盘"}信号
2. **基本面评估**: 公司财务状况{"良好" if action == "买入" else "一般" if action == "持有" else "需关注"}
3. **市场情绪**: 投资者情绪{"乐观" if action == "买入" else "中性" if action == "持有" else "谨慎"}
4. **风险评估**: 当前风险水平为{"中等" if action == "持有" else "较低" if action == "买入" else "较高"}

**注意**: 这是演示数据，实际分析需要配置正确的API密钥。
        """,
    }

    # 生成模拟状态数据
    demo_state = {}

    if "market" in analysts:
        current_price = round(random.uniform(*price_range), 2)
        high_price = round(current_price * random.uniform(1.2, 1.8), 2)
        low_price = round(current_price * random.uniform(0.5, 0.8), 2)

        demo_state["market_report"] = f"""
## 📈 {market_name}{stock_symbol} 技术面分析报告

### 价格趋势分析
- **当前价格**: {currency_symbol}{current_price}
- **日内变化**: {random.choice(["+", "-"])}{round(random.uniform(0.5, 5), 2)}%
- **52周高点**: {currency_symbol}{high_price}
- **52周低点**: {currency_symbol}{low_price}

### 技术指标
- **RSI (14日)**: {round(random.uniform(30, 70), 1)}
- **MACD**: {"看涨" if action == "BUY" else "看跌" if action == "SELL" else "中性"}
- **移动平均线**: 价格{"高于" if action == "BUY" else "低于" if action == "SELL" else "接近"}20日均线

### 支撑阻力位
- **支撑位**: ${round(random.uniform(80, 120), 2)}
- **阻力位**: ${round(random.uniform(250, 350), 2)}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    if "fundamentals" in analysts:
        demo_state["fundamentals_report"] = f"""
## 💰 {stock_symbol} 基本面分析报告

### 财务指标
- **市盈率 (P/E)**: {round(random.uniform(15, 35), 1)}
- **市净率 (P/B)**: {round(random.uniform(1, 5), 1)}
- **净资产收益率 (ROE)**: {round(random.uniform(10, 25), 1)}%
- **毛利率**: {round(random.uniform(20, 60), 1)}%

### 盈利能力
- **营收增长**: {random.choice(["+", "-"])}{round(random.uniform(5, 20), 1)}%
- **净利润增长**: {random.choice(["+", "-"])}{round(random.uniform(10, 30), 1)}%
- **每股收益**: ${round(random.uniform(2, 15), 2)}

### 财务健康度
- **负债率**: {round(random.uniform(20, 60), 1)}%
- **流动比率**: {round(random.uniform(1, 3), 1)}
- **现金流**: {"正向" if action != "SELL" else "需关注"}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    if "social" in analysts:
        demo_state["sentiment_report"] = f"""
## 💭 {stock_symbol} 市场情绪分析报告

### 社交媒体情绪
- **整体情绪**: {"积极" if action == "BUY" else "消极" if action == "SELL" else "中性"}
- **情绪强度**: {round(random.uniform(0.5, 0.9), 2)}
- **讨论热度**: {"高" if random.random() > 0.5 else "中等"}

### 投资者情绪指标
- **恐慌贪婪指数**: {round(random.uniform(20, 80), 0)}
- **看涨看跌比**: {round(random.uniform(0.8, 1.5), 2)}
- **期权Put/Call比**: {round(random.uniform(0.5, 1.2), 2)}

### 机构投资者动向
- **机构持仓变化**: {random.choice(["增持", "减持", "维持"])}
- **分析师评级**: {"买入" if action == "BUY" else "卖出" if action == "SELL" else "持有"}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    if "news" in analysts:
        demo_state["news_report"] = f"""
## 📰 {stock_symbol} 新闻事件分析报告

### 近期重要新闻
1. **财报发布**: 公司发布{"超预期" if action == "BUY" else "低于预期" if action == "SELL" else "符合预期"}的季度财报
2. **行业动态**: 所在行业面临{"利好" if action == "BUY" else "挑战" if action == "SELL" else "稳定"}政策环境
3. **公司公告**: 管理层{"乐观" if action == "BUY" else "谨慎" if action == "SELL" else "稳健"}展望未来

### 新闻情绪分析
- **正面新闻占比**: {round(random.uniform(40, 80), 0)}%
- **负面新闻占比**: {round(random.uniform(10, 40), 0)}%
- **中性新闻占比**: {round(random.uniform(20, 50), 0)}%

### 市场影响评估
- **短期影响**: {"正面" if action == "BUY" else "负面" if action == "SELL" else "中性"}
- **长期影响**: {"积极" if action != "SELL" else "需观察"}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    # 添加风险评估和投资建议
    demo_state["risk_assessment"] = f"""
## ⚠️ {stock_symbol} 风险评估报告

### 主要风险因素
1. **市场风险**: {"低" if action == "BUY" else "高" if action == "SELL" else "中等"}
2. **行业风险**: {"可控" if action != "SELL" else "需关注"}
3. **公司特定风险**: {"较低" if action == "BUY" else "中等"}

### 风险等级评估
- **总体风险等级**: {"低风险" if action == "BUY" else "高风险" if action == "SELL" else "中等风险"}
- **建议仓位**: {random.choice(["轻仓", "标准仓位", "重仓"]) if action != "SELL" else "建议减仓"}

*注意: 这是演示数据，实际分析需要配置API密钥*
    """

    demo_state["investment_plan"] = f"""
## 📋 {stock_symbol} 投资建议

### 具体操作建议
- **操作方向**: {action}
- **建议价位**: ${round(random.uniform(90, 310), 2)}
- **止损位**: ${round(random.uniform(80, 200), 2)}
- **目标价位**: ${round(random.uniform(150, 400), 2)}

### 投资策略
- **投资期限**: {"短期" if research_depth <= 2 else "中长期"}
- **仓位管理**: {"分批建仓" if action == "BUY" else "分批减仓" if action == "SELL" else "维持现状"}

*注意: 这是演示数据，实际分析需要配置API密钥*
    """

    # 添加团队决策演示数据，确保与CLI端一致
    demo_state["investment_debate_state"] = {
        "bull_history": f"""
## 📈 多头研究员分析

作为多头研究员，我对{stock_symbol}持乐观态度：

### 🚀 投资亮点
1. **技术面突破**: 股价突破关键阻力位，技术形态良好
2. **基本面支撑**: 公司业绩稳健增长，财务状况健康
3. **市场机会**: 当前估值合理，具备上涨空间

### 📊 数据支持
- 近期成交量放大，资金流入明显
- 行业景气度提升，政策环境有利
- 机构投资者增持，市场信心增强

**建议**: 积极买入，目标价位上调15-20%

*注意: 这是演示数据*
        """.strip(),
        "bear_history": f"""
## 📉 空头研究员分析

作为空头研究员，我对{stock_symbol}持谨慎态度：

### ⚠️ 风险因素
1. **估值偏高**: 当前市盈率超过行业平均水平
2. **技术风险**: 短期涨幅过大，存在回调压力
3. **宏观环境**: 市场整体波动加大，不确定性增加

### 📉 担忧点
- 成交量虽然放大，但可能是获利盘出货
- 行业竞争加剧，公司市场份额面临挑战
- 政策变化可能对行业产生负面影响

**建议**: 谨慎观望，等待更好的入场时机

*注意: 这是演示数据*
        """.strip(),
        "judge_decision": f"""
## 🎯 研究经理综合决策

经过多头和空头研究员的充分辩论，我的综合判断如下：

### 📊 综合评估
- **多头观点**: 技术面和基本面都显示积极信号
- **空头观点**: 估值和短期风险需要关注
- **平衡考虑**: 机会与风险并存，需要策略性操作

### 🎯 最终建议
基于当前市场环境和{stock_symbol}的具体情况，建议采取**{action}**策略：

1. **操作建议**: {action}
2. **仓位控制**: {"分批建仓" if action == "买入" else "分批减仓" if action == "卖出" else "维持现状"}
3. **风险管理**: 设置止损位，控制单只股票仓位不超过10%

**决策依据**: 综合技术面、基本面和市场情绪分析

*注意: 这是演示数据*
        """.strip(),
    }

    demo_state["trader_investment_plan"] = f"""
## 💼 交易团队执行计划

基于研究团队的分析结果，制定如下交易执行计划：

### 🎯 交易策略
- **交易方向**: {action}
- **目标价位**: {currency_symbol}{round(random.uniform(*price_range) * 1.1, 2)}
- **止损价位**: {currency_symbol}{round(random.uniform(*price_range) * 0.9, 2)}

### 📊 仓位管理
- **建议仓位**: {"30-50%" if action == "买入" else "减仓至20%" if action == "卖出" else "维持现有仓位"}
- **分批操作**: {"分3次建仓" if action == "买入" else "分2次减仓" if action == "卖出" else "暂不操作"}
- **时间安排**: {"1-2周内完成" if action != "持有" else "持续观察"}

### ⚠️ 风险控制
- **止损设置**: 跌破支撑位立即止损
- **止盈策略**: 达到目标价位分批止盈
- **监控要点**: 密切关注成交量和技术指标变化

*注意: 这是演示数据，实际交易需要配置API密钥*
    """

    demo_state["risk_debate_state"] = {
        "risky_history": f"""
## 🚀 激进分析师风险评估

从激进投资角度分析{stock_symbol}：

### 💪 风险承受能力
- **高收益机会**: 当前市场提供了难得的投资机会
- **风险可控**: 虽然存在波动，但长期趋势向好
- **时机把握**: 现在是积极布局的最佳时机

### 🎯 激进策略
- **加大仓位**: 建议将仓位提升至60-80%
- **杠杆使用**: 可适度使用杠杆放大收益
- **快速行动**: 机会稍纵即逝，需要果断决策

**风险评级**: 中等风险，高收益潜力

*注意: 这是演示数据*
        """.strip(),
        "safe_history": f"""
## 🛡️ 保守分析师风险评估

从风险控制角度分析{stock_symbol}：

### ⚠️ 风险识别
- **市场波动**: 当前市场不确定性较高
- **估值风险**: 部分股票估值已经偏高
- **流动性风险**: 需要关注市场流动性变化

### 🔒 保守策略
- **控制仓位**: 建议仓位不超过30%
- **分散投资**: 避免过度集中于单一标的
- **安全边际**: 确保有足够的安全边际

**风险评级**: 中高风险，需要谨慎操作

*注意: 这是演示数据*
        """.strip(),
        "neutral_history": f"""
## ⚖️ 中性分析师风险评估

从平衡角度分析{stock_symbol}：

### 📊 客观评估
- **机会与风险并存**: 当前市场既有机会也有风险
- **适度参与**: 建议采取适度参与的策略
- **灵活调整**: 根据市场变化及时调整策略

### ⚖️ 平衡策略
- **中等仓位**: 建议仓位控制在40-50%
- **动态调整**: 根据市场情况动态调整仓位
- **风险监控**: 持续监控风险指标变化

**风险评级**: 中等风险，平衡收益

*注意: 这是演示数据*
        """.strip(),
        "judge_decision": f"""
## 🎯 投资组合经理最终风险决策

综合三位风险分析师的意见，最终风险管理决策如下：

### 📊 风险综合评估
- **激进观点**: 高收益机会，建议积极参与
- **保守观点**: 风险较高，建议谨慎操作
- **中性观点**: 机会与风险并存，适度参与

### 🎯 最终风险决策
基于当前市场环境和{stock_symbol}的风险特征：

1. **风险等级**: 中等风险
2. **建议仓位**: 40%（平衡收益与风险）
3. **风险控制**: 严格执行止损策略
4. **监控频率**: 每日监控，及时调整

**决策理由**: 在控制风险的前提下，适度参与市场机会

*注意: 这是演示数据*
        """.strip(),
    }

    confidence = demo_state.get("decision", {}).get("confidence", 0.7)

    demo_state["final_trade_decision"] = f"""
## 🎯 最终投资决策

经过分析师团队、研究团队、交易团队和风险管理团队的全面分析，最终投资决策如下：

### 📊 决策摘要
- **投资建议**: **{action}**
- **置信度**: {confidence:.1%}
- **风险评级**: 中等风险
- **预期收益**: {"10-20%" if action == "买入" else "规避损失" if action == "卖出" else "稳健持有"}

### 🎯 执行计划
1. **操作方向**: {action}
2. **目标仓位**: {"40%" if action == "买入" else "20%" if action == "卖出" else "维持现状"}
3. **执行时间**: {"1-2周内分批执行" if action != "持有" else "持续观察"}
4. **风险控制**: 严格执行止损止盈策略

### 📈 预期目标
- **目标价位**: {currency_symbol}{round(random.uniform(*price_range) * 1.15, 2)}
- **止损价位**: {currency_symbol}{round(random.uniform(*price_range) * 0.85, 2)}
- **投资期限**: {"3-6个月" if research_depth >= 3 else "1-3个月"}

### ⚠️ 重要提醒
这是基于当前市场环境和{stock_symbol}基本面的综合判断。投资有风险，请根据个人风险承受能力谨慎决策。

**免责声明**: 本分析仅供参考，不构成投资建议。

*注意: 这是演示数据，实际分析需要配置正确的API密钥*
    """

    return {
        "stock_symbol": stock_symbol,
        "analysis_date": analysis_date,
        "analysts": analysts,
        "research_depth": research_depth,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "state": demo_state,
        "decision": demo_decision,
        "success": True,
        "error": None,
        "is_demo": True,
        "demo_reason": f"API调用失败，显示演示数据。错误信息: {error_msg}",
    }
