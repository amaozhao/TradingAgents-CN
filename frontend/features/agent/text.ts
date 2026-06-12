import { Activity, FileText, Landmark, Sparkles, TrendingUp, Users } from "lucide-react"

export const EXAMPLE_CATEGORIES = [
  {
    label: "多市场回测",
    icon: TrendingUp,
    examples: [
      {
        title: "跨市场组合",
        desc: "A 股 + Crypto + 美股，使用风险平价优化器",
        prompt: "请用 backtest 工具回测一个风险平价组合，标的包括 000001.SZ、BTC-USDT 和 AAPL，时间范围为 2024 全年，并和等权组合基准进行对比。"
      },
      {
        title: "BTC 5 分钟 MACD 策略",
        desc: "使用 OKX 实时数据做分钟级 Crypto 回测",
        prompt: "请回测 BTC-USDT 的 5 分钟 MACD 策略，参数 fast=12、slow=26、signal=9，时间范围为最近 30 天，并总结收益、回撤和主要风险。"
      },
      {
        title: "美股科技最大分散组合",
        desc: "通过 yfinance 优化 FAANG+ 组合",
        prompt: "请使用 max_diversification 组合优化器回测 AAPL、MSFT、GOOGL、AMZN、NVDA 在 2024 全年的表现，并说明和等权组合相比的差异。"
      }
    ]
  },
  {
    label: "研究分析",
    icon: Sparkles,
    examples: [
      {
        title: "多因子 Alpha 模型",
        desc: "在 300 只股票上做 IC 加权因子合成",
        prompt: "请基于沪深 300 成分股构建多因子 Alpha 模型，因子包括 momentum、reversal、volatility 和 turnover，使用 IC 加权合成，并回测 2023-2024 年表现。"
      },
      {
        title: "期权 Greeks 分析",
        desc: "Black-Scholes 定价和 Delta/Gamma/Theta/Vega",
        prompt: "请用 Black-Scholes 模型计算期权 Greeks：spot=100、strike=105、risk-free rate=3%、vol=25%、expiry=90 days，并解释 Delta、Gamma、Theta、Vega 的含义和风险。"
      }
    ]
  },
  {
    label: "智能体团队",
    icon: Users,
    examples: [
      {
        title: "投委会评审",
        desc: "多智能体辩论：多空观点、风险审查、PM 决策",
        prompt: "[Swarm Team Mode] 请使用 investment_committee preset，根据当前市场环境评估 NVDA 应该做多、做空还是观望，并汇总多空观点、风险审查和 PM 决策。"
      },
      {
        title: "量化策略桌",
        desc: "筛选、因子研究、回测、风险审计流水线",
        prompt: "[Swarm Team Mode] 请使用 quant_strategy_desk preset，在沪深 300 成分股中寻找并回测最佳动量策略，流程包括筛选、因子研究、回测和风险审计。"
      }
    ]
  },
  {
    label: "文档与网页研究",
    icon: FileText,
    examples: [
      {
        title: "分析财报 PDF",
        desc: "上传 PDF 并询问财务数据",
        prompt: "请读取我上传的财报 PDF，总结关键财务指标、经营风险、管理层展望，以及对股价可能产生影响的要点。"
      },
      {
        title: "网页研究：宏观展望",
        desc: "读取实时网页来源并总结宏观影响",
        prompt: "请读取最新的美联储会议纪要，并总结其中对股票市场和 Crypto 市场最重要的影响。"
      }
    ]
  },
  {
    label: "交易日志",
    icon: Activity,
    examples: [
      {
        title: "分析券商导出记录",
        desc: "解析同花顺/东财/富途/通用 CSV 的交易统计",
        prompt: "请分析我刚上传的交易日志，输出完整画像，包括持仓天数、胜率、盈亏比、主要交易标的和按小时分布的交易行为。如果当前会话没有可读取的交易日志 artifact_id/file_id 或日志文本，请先让我上传或粘贴日志，不要调用交易日志工具。"
      },
      {
        title: "诊断交易行为偏差",
        desc: "处置效应、过度交易、追涨、锚定等诊断",
        prompt: "请对我的交易日志运行 4 类行为诊断：disposition、overtrading、chasing、anchoring，并告诉我哪一种偏差对 PnL 伤害最大。如果当前会话没有可读取的交易日志 artifact_id/file_id 或日志文本，请先让我上传或粘贴日志，不要调用交易日志工具。"
      }
    ]
  },
  {
    label: "交易连接器",
    icon: Landmark,
    examples: [
      {
        title: "检查已选连接器",
        desc: "列出连接器配置并检查当前选中项",
        prompt: "请列出我的 trading connector profiles，说明当前选中的是哪一个，然后检查这个连接器是否可用。如果还没准备好，请明确告诉我缺少哪一步配置。不要下单，也不要修改订单。"
      },
      {
        title: "分析连接器组合",
        desc: "读取账户摘要和持仓，保持只读",
        prompt: "请先检查当前选中的 trading connector profile 是否 connected；如果未 connected 或缺 OAuth/token，请只说明缺少哪一步配置，不要调用账户、持仓、订单或历史读取工具。如果已 connected，再读取账户摘要和持仓，分析现金、仓位集中度和组合风险。保持只读，不要下单，也不要修改订单。"
      },
      {
        title: "报价与趋势",
        desc: "通过当前连接器获取报价和近期日线",
        prompt: "请先检查当前选中的 trading connector 是否 connected；如果未 connected 或缺 OAuth/token，请只说明缺少哪一步配置，不要调用 quote 或 history 工具。如果已 connected，再获取 AAPL 的实时 quote 和最近 30 根日线，并总结当前报价相对近期趋势的位置。保持只读。"
      }
    ]
  },
  {
    label: "Shadow Account",
    icon: Activity,
    examples: [
      {
        title: "从日志训练 Shadow",
        desc: "从券商 CSV 提取你的策略规则",
        prompt: "请根据我刚上传的交易日志训练 Shadow Account，提取我的策略规则，并展示这些规则是否像我的真实交易行为。如果当前会话没有可读取的交易日志 artifact_id/file_id 或日志文本，请先让我上传或粘贴日志，不要调用 Shadow 或交易日志工具。"
      },
      {
        title: "我少赚了多少？",
        desc: "回测 Shadow 策略并归因实际 PnL 差异",
        prompt: "请对最近 90 天的美股市场运行 Shadow backtest，拆解我的实际 PnL 和 Shadow 策略之间的差异，包括规则违背、过早离场和错过信号。如果当前会话没有 returns、trades[].pnl、交易日志 artifact_id/file_id 或日志文本，请先让我上传或粘贴数据，不要调用 Shadow backtest 工具。"
      },
      {
        title: "生成 Shadow 报告",
        desc: "8 段 HTML/PDF 报告，含权益曲线和归因瀑布图",
        prompt: "请渲染 Shadow report 并给出 URL，报告开头先说明 you-vs-shadow delta，再展示权益曲线、分市场 Sharpe 和归因瀑布图。如果当前会话没有 shadow backtest_id 或 shadow report 数据，请先说明缺少什么，不要直接调用 Shadow 报告工具。"
      }
    ]
  },
  {
    label: "当前项目补充",
    icon: Sparkles,
    examples: [
      {
        title: "A 股储能研究",
        desc: "结合 A 股研究、Alpha、矩阵和报告证据",
        prompt: "帮我分析 A 股的储能板块，给出推荐个股、证据和风险点"
      },
      {
        title: "Alpha Zoo 覆盖检查",
        desc: "运行 Alpha bench / compare，并解释覆盖率和 IC/IR",
        prompt: "请对 600519、000001、300750 在 2025-01-01 到 2026-06-03 期间运行 Alpha Zoo coverage，因子包括 academic_carhart_mom、academic_cma、academic_mkt_rf，并用普通语言解释覆盖率、IC 和 IR。"
      },
      {
        title: "相关性矩阵",
        desc: "计算候选资产相关性并给出组合分散度建议",
        prompt: "请为 600519、000001、300750 构建相关性矩阵，并解释哪些标的之间有更好的组合分散效果。"
      }
    ]
  }
]

export const CAPABILITY_CHIPS = [
  "智能体运行时",
  "51 个源工具迁移矩阵",
  "金融技能库",
  "Research Goal",
  "Swarm",
  "Backtest",
  "Alpha Zoo",
  "文档/Web",
  "交易连接器",
  "交易日志分析",
  "Shadow Account",
  "持久记忆",
  "会话搜索"
]

export const AGENT_COMPLETION_POLL_TIMEOUT_MS = 60 * 60_000
export const COMPOSER_MIN_HEIGHT = 44
export const COMPOSER_MAX_HEIGHT = 128

export const QUICK_RESEARCH_PROMPTS = [
  { label: "跨市场回测", prompt: "请用 backtest 工具回测一个风险平价组合，标的包括 000001.SZ、BTC-USDT 和 AAPL，时间范围为 2024 全年，并和等权组合基准进行对比。" },
  { label: "检查交易连接器", prompt: "请列出我的 trading connector profiles，说明当前选中的是哪一个，然后检查这个连接器是否可用。如果还没准备好，请明确告诉我缺少哪一步配置。不要下单，也不要修改订单。" },
  { label: "分析连接器组合", prompt: "请先检查当前选中的 trading connector profile 是否 connected；如果未 connected 或缺 OAuth/token，请只说明缺少哪一步配置，不要调用账户、持仓、订单或历史读取工具。如果已 connected，再读取账户摘要和持仓，分析现金、仓位集中度和组合风险。保持只读，不要下单，也不要修改订单。" },
  { label: "智能体团队", prompt: "[Swarm Team Mode] 请使用 investment_committee preset，根据当前市场环境评估 NVDA 应该做多、做空还是观望，并汇总多空观点、风险审查和 PM 决策。" },
  { label: "Shadow Account", prompt: "请对最近 90 天的美股市场运行 Shadow backtest，拆解我的实际 PnL 和 Shadow 策略之间的差异，包括规则违背、过早离场和错过信号。如果当前会话没有 returns、trades[].pnl、交易日志 artifact_id/file_id 或日志文本，请先让我上传或粘贴数据，不要调用 Shadow backtest 工具。" }
]

export const EXAMPLE_CATEGORIES_EN: typeof EXAMPLE_CATEGORIES = [
  {
    label: "Multi-market backtest",
    icon: TrendingUp,
    examples: [
      {
        title: "Cross-market portfolio",
        desc: "A-shares + crypto + US equities with risk-parity optimizer",
        prompt: "Backtest a risk-parity portfolio of 000001.SZ, BTC-USDT, and AAPL for full-year 2024, compare against equal-weight baseline"
      },
      {
        title: "BTC 5-minute MACD strategy",
        desc: "Minute-level crypto backtest with real-time OKX data",
        prompt: "Backtest BTC-USDT 5-minute MACD strategy, fast=12 slow=26 signal=9, last 30 days"
      },
      {
        title: "US tech max diversification",
        desc: "Portfolio optimizer across FAANG+ via yfinance",
        prompt: "Backtest AAPL, MSFT, GOOGL, AMZN, NVDA with max_diversification portfolio optimizer, full-year 2024"
      }
    ]
  },
  {
    label: "Research and analysis",
    icon: Sparkles,
    examples: [
      {
        title: "Multi-factor alpha model",
        desc: "IC-weighted factor synthesis across 300 stocks",
        prompt: "Build a multi-factor alpha model using momentum, reversal, volatility, and turnover on CSI 300 constituents with IC-weighted factor synthesis, backtest 2023-2024"
      },
      {
        title: "Options Greeks analysis",
        desc: "Black-Scholes pricing with Delta/Gamma/Theta/Vega",
        prompt: "Calculate option Greeks using Black-Scholes: spot=100, strike=105, risk-free rate=3%, vol=25%, expiry=90 days, analyze Delta/Gamma/Theta/Vega"
      }
    ]
  },
  {
    label: "Swarm teams",
    icon: Users,
    examples: [
      {
        title: "Investment committee review",
        desc: "Multi-agent debate: long vs short, risk review, PM decision",
        prompt: "[Swarm Team Mode] Use the investment_committee preset to evaluate whether to go long or short on NVDA given current market conditions"
      },
      {
        title: "Quant strategy desk",
        desc: "Screening, factor research, backtest, and risk-audit pipeline",
        prompt: "[Swarm Team Mode] Use the quant_strategy_desk preset to find and backtest the best momentum strategy on CSI 300 constituents"
      }
    ]
  },
  {
    label: "Document and web research",
    icon: FileText,
    examples: [
      {
        title: "Analyze an earnings report PDF",
        desc: "Upload a PDF and ask questions about the financials",
        prompt: "Summarize the key financial metrics, risks, and outlook from the uploaded earnings report"
      },
      {
        title: "Web research: macro outlook",
        desc: "Read live web sources for macro analysis",
        prompt: "Read the latest Fed meeting minutes and summarize the key takeaways for equity and crypto markets"
      }
    ]
  },
  {
    label: "Trade journal",
    icon: Activity,
    examples: [
      {
        title: "Analyze my broker export",
        desc: "Parse broker CSVs for holding stats, win rate, PnL ratio, and hourly distribution",
        prompt: "Analyze the trade journal I just uploaded — full profile with holding stats, win rate, top symbols, and hourly distribution. If this session has no readable journal artifact_id/file_id or pasted journal text, ask me to upload or paste it before calling the trade journal tool."
      },
      {
        title: "Diagnose my behavior biases",
        desc: "Disposition effect, overtrading, chasing, and anchoring diagnostics",
        prompt: "Run the 4 behavior diagnostics on my trade journal (disposition, overtrading, chasing, anchoring) and tell me which bias hurts my PnL most. If this session has no readable journal artifact_id/file_id or pasted journal text, ask me to upload or paste it before calling the trade journal tool."
      }
    ]
  },
  {
    label: "Trading connectors",
    icon: Landmark,
    examples: [
      {
        title: "Check selected connector",
        desc: "List connector profiles and verify the selected one",
        prompt: "List my trading connector profiles, show which one is selected, then check that selected connector. If it is not ready, tell me exactly what setup step is missing. Do not place or modify orders."
      },
      {
        title: "Analyze connector portfolio",
        desc: "Read account summary and positions from the selected connector",
        prompt: "First check whether the selected trading connector profile is connected. If it is not connected or OAuth/token is missing, only explain the missing setup step and do not call account, position, order, or history read tools. If it is connected, summarize my account, positions, concentration, cash, and portfolio risk. Do not place or modify orders."
      },
      {
        title: "Quote and trend",
        desc: "Fetch a quote plus recent daily bars through the selected connector",
        prompt: "First check whether the selected trading connector is connected. If it is not connected or OAuth/token is missing, only explain the missing setup step and do not call quote or history tools. If it is connected, fetch an AAPL quote and 30 daily bars, then summarize the current quote versus the recent trend. Keep it read-only."
      }
    ]
  },
  {
    label: "Shadow Account",
    icon: Activity,
    examples: [
      {
        title: "Train my shadow from journal",
        desc: "Extract your strategy rules from a broker CSV and persist a Shadow profile",
        prompt: "Train my shadow account from the trading journal I just uploaded — show the extracted rules and confirm they look like my behavior. If this session has no readable journal artifact_id/file_id or pasted journal text, ask me to upload or paste it before calling Shadow or trade journal tools."
      },
      {
        title: "How much am I leaving on the table?",
        desc: "Backtest your shadow strategy and attribute delta versus actual PnL",
        prompt: "Run a shadow backtest for the last 90 days on the US market and break down where my PnL diverged from the shadow (rule violations, early exits, missed signals). If this session has no returns, trades[].pnl, journal artifact_id/file_id, or pasted journal text, ask me to upload or paste data before calling the shadow backtest tool."
      },
      {
        title: "Generate shadow report",
        desc: "8-section HTML/PDF with equity curve and attribution waterfall",
        prompt: "Render the shadow report and give me the URL — lead with the you-vs-shadow delta. If this session has no shadow backtest_id or shadow report data, explain what is missing before calling the shadow report tool."
      }
    ]
  },
  {
    label: "Current-project additions",
    icon: Sparkles,
    examples: [
      {
        title: "A-share energy storage research",
        desc: "Combine A-share research, Alpha evidence, matrices, and reports",
        prompt: "Analyze the A-share energy storage sector, then provide recommended names, supporting evidence, and risk points."
      },
      {
        title: "Alpha Zoo coverage check",
        desc: "Run Alpha bench/compare and explain coverage plus IC/IR",
        prompt: "Run Alpha Zoo coverage for academic_carhart_mom, academic_cma, academic_mkt_rf on 600519,000001,300750 from 2025-01-01 to 2026-06-03, then explain the result in plain language."
      },
      {
        title: "Correlation matrix",
        desc: "Calculate candidate-asset correlations and diversification implications",
        prompt: "Build a correlation matrix for 600519, 000001, and 300750, then explain which names diversify each other."
      }
    ]
  }
]

export const TOOL_LABELS: Record<string, { title: string; desc: string }> = {
  load_skill: { title: "加载能力模块", desc: "加载工具或技能说明" },
  bash: { title: "命令执行", desc: "执行辅助命令并收集输出" },
  screening_run: { title: "股票筛选", desc: "构建候选池并筛掉不满足条件的标的" },
  alpha_bench: { title: "Alpha 覆盖检查", desc: "检查候选股票可用因子、覆盖率和有效性" },
  correlation_matrix: { title: "相关性矩阵", desc: "分析候选股票之间的相关性和组合分散度" },
  stock_analysis: { title: "个股分析", desc: "通过 Agent workflow 提交并跟踪个股分析" },
  single_stock_analysis: { title: "个股分析", desc: "生成个股证据、风险点和研究摘要" },
  stock_analysis_status: { title: "个股分析进度", desc: "读取个股 LangGraph DAG 任务状态" },
  stock_analysis_report: { title: "个股分析报告", desc: "读取已完成的个股分析报告" },
  report_write: { title: "报告写入", desc: "把本次研究证据保存为报告产物" },
  backtest: { title: "回测", desc: "生成/运行策略并输出绩效指标与产物" },
  alpha_zoo: { title: "Alpha Zoo", desc: "查询因子定义、公式和元数据" },
  alpha_compare: { title: "Alpha 对比", desc: "比较多个因子的 IC/IR、覆盖率和样本" },
  read_document: { title: "文档读取", desc: "读取上传的 PDF/Office/文本文件" },
  read_url: { title: "网页读取", desc: "抓取并解析允许访问的网页" },
  web_search: { title: "网页搜索", desc: "搜索公开网页资料" },
  run_swarm: { title: "智能体团队", desc: "运行 swarm 多智能体研究团队" },
  trading_connections: { title: "交易连接器列表", desc: "列出可选交易连接器 profiles" },
  trading_select_connection: { title: "选择交易连接器", desc: "选择当前会话使用的交易连接器 profile" },
  trading_check: { title: "交易连接器检查", desc: "检查选中连接器可用性" },
  trading_account: { title: "账户摘要", desc: "读取连接器账户信息" },
  trading_positions: { title: "持仓摘要", desc: "读取连接器持仓信息" },
  trading_orders: { title: "订单摘要", desc: "读取连接器订单信息" },
  trading_quote: { title: "连接器行情", desc: "读取连接器行情" },
  analyze_trade_journal: { title: "交易日志分析", desc: "分析交易行为和风险纪律" },
  extract_shadow_strategy: { title: "Shadow 策略提取", desc: "从描述中提取影子账户策略" },
  run_shadow_backtest: { title: "Shadow 回测", desc: "运行影子账户回测" },
  render_shadow_report: { title: "Shadow 报告", desc: "渲染影子账户报告" },
  start_research_goal: { title: "创建研究目标", desc: "创建或绑定 research goal" },
  add_goal_evidence: { title: "追加目标证据", desc: "向 goal ledger 写入证据" },
  update_research_goal_status: { title: "更新目标状态", desc: "把本次研究目标标记为最新状态" },
  get_research_goal: { title: "读取研究目标", desc: "读取当前 research goal 状态" }
}

export const TOOL_LABELS_EN: Record<string, { title: string; desc: string }> = {
  load_skill: { title: "Load skill", desc: "Load a tool or skill description" },
  bash: { title: "Command execution", desc: "Run an auxiliary command and collect output" },
  screening_run: { title: "Stock screening", desc: "Build a candidate pool and filter names" },
  alpha_bench: { title: "Alpha coverage check", desc: "Check factor availability, coverage, and validity" },
  correlation_matrix: { title: "Correlation matrix", desc: "Analyze correlations and portfolio diversification" },
  stock_analysis: { title: "Single-stock analysis", desc: "Submit and track single-stock analysis through the Agent workflow" },
  single_stock_analysis: { title: "Single-stock analysis", desc: "Generate evidence, risks, and a research summary" },
  stock_analysis_status: { title: "Single-stock progress", desc: "Read single-stock LangGraph DAG task status" },
  stock_analysis_report: { title: "Single-stock report", desc: "Read a completed single-stock analysis report" },
  report_write: { title: "Report write", desc: "Save research evidence as a report artifact" },
  backtest: { title: "Backtest", desc: "Build/run a strategy and output metrics plus artifacts" },
  alpha_zoo: { title: "Alpha Zoo", desc: "Query factor definitions, formulas, and metadata" },
  alpha_compare: { title: "Alpha compare", desc: "Compare IC/IR, coverage, and samples across factors" },
  read_document: { title: "Read document", desc: "Read uploaded PDF/Office/text files" },
  read_url: { title: "Read web page", desc: "Fetch and parse allowed web pages" },
  web_search: { title: "Web search", desc: "Search public web sources" },
  run_swarm: { title: "Agent team", desc: "Run a swarm multi-agent research team" },
  trading_connections: { title: "Trading connectors", desc: "List available trading connector profiles" },
  trading_select_connection: { title: "Select trading connector", desc: "Select the connector profile for this session" },
  trading_check: { title: "Connector check", desc: "Check selected connector availability" },
  trading_account: { title: "Account summary", desc: "Read connector account information" },
  trading_positions: { title: "Positions", desc: "Read connector positions" },
  trading_orders: { title: "Orders", desc: "Read connector orders" },
  trading_quote: { title: "Connector quote", desc: "Read connector market quotes" },
  analyze_trade_journal: { title: "Trade journal analysis", desc: "Analyze trading behavior and risk discipline" },
  extract_shadow_strategy: { title: "Extract shadow strategy", desc: "Extract a shadow-account strategy from a description" },
  run_shadow_backtest: { title: "Shadow backtest", desc: "Run a shadow-account backtest" },
  render_shadow_report: { title: "Shadow report", desc: "Render a shadow-account report" },
  start_research_goal: { title: "Create research goal", desc: "Create or bind a research goal" },
  add_goal_evidence: { title: "Add goal evidence", desc: "Write evidence into the goal ledger" },
  update_research_goal_status: { title: "Update goal status", desc: "Mark the current research goal status" },
  get_research_goal: { title: "Read research goal", desc: "Read the current research goal state" }
}

export const AGENT_TEXT = {
  "zh-CN": {
    pageTitle: "智能体",
    pageSubtitle: "已接入当前项目智能体运行时，并运行在当前后端进程内。",
    capabilities: CAPABILITY_CHIPS,
    quickPrompts: QUICK_RESEARCH_PROMPTS,
    examples: EXAMPLE_CATEGORIES,
    toolLabels: TOOL_LABELS,
    ready: "就绪",
    running: "运行中",
    cancelling: "取消中",
    skipped: "已跳过",
    warning: "数据受限",
    failed: "失败",
    completed: "完成",
    newSession: "新会话",
    exportChat: "导出聊天",
    working: "智能体正在工作...",
    newMessages: "新消息",
    goalModeChip: "新研究目标",
    moreOptions: "更多选项",
    researchGoal: "研究目标",
    singleStock: "个股分析",
    goalPlaceholder: "描述要绑定到当前会话的研究目标",
    chatPlaceholder: "例如：运行回测、检查连接器状态，或分析 A 股储能板块",
    stop: "停止生成",
    send: "发送",
    loadingSessionTitle: "正在载入会话",
    loadingSessionDesc: "正在恢复历史消息和执行步骤...",
    toolFallback: "tool",
    sessions: "会话",
    noSessions: "还没有智能体会话。",
    saveRename: "保存重命名",
    cancelRename: "取消重命名",
    renameSession: "重命名会话",
    deleteSession: "删除会话",
    deleteConfirm: "删除后会清理这个会话的消息、事件和产物。确定删除吗？",
    cancelRequested: "已请求后端取消当前 Agent attempt。",
    timeout: "Agent 运行超过 60 分钟仍未收到完成事件，请刷新会话或检查后端日志。",
    sendFailed: "发送消息失败，请重试。",
    goalCriteria: [
      "保持研究用途，不执行交易下单",
      "使用当前项目已授权工具收集证据",
      "在目标完成、阻塞或等待用户输入时更新状态"
    ],
    goalPrompt: (raw: string) => [
      "Start working on this research goal now.",
      "Keep it research-only, use available tools when evidence is needed, add concrete evidence to the goal ledger, and keep going until the goal is complete, blocked, waiting for user input, or budget-limited.",
      "",
      `Goal: ${raw}`
    ].join("\n"),
    unnamedGoal: "未命名研究目标",
    goalPanelTitle: "当前研究目标",
    noGoal: "暂无绑定的 Research Goal。点击输入框左侧加号选择“研究目标”后发送，会先在当前项目后端创建目标。",
    criteriaTitle: "验收条件",
    evidenceLedger: "证据 Ledger",
    evidenceCount: (count: number) => `${count} 条`,
    noEvidence: "等待 Agent 工具写入可追溯证据。",
    liveTitle: "交易连接器运行",
    refresh: "刷新",
    liveDesc: "来自当前 Agent Runtime 的 /live/status，展示 broker 授权、runner 和 kill switch 状态。",
    liveUnavailable: "当前后端未返回 live runtime 状态。",
    liveRuntime: "交易连接器运行",
    liveStatus: "交易连接器运行状态",
    liveConnected: "已连接",
    liveNoConnector: "没有交易连接器连接",
    liveHalted: "已停止",
    liveNever: "从未",
    liveUnknown: "未知",
    liveJustNow: "刚刚",
    liveAgo: "前",
    liveOrder: "每单",
    liveDay: "每日",
    liveNoLeverage: "不使用杠杆",
    liveAuthorized: "已授权",
    liveNotConnected: "未连接",
    liveConnectProfile: "连接此 profile 以启用交易连接器运行",
    liveAuthorizeInstruction: "选择 broker profile 后，在持有 broker 连接的桌面会话中完成授权。",
    liveAuthorizationNote: "OAuth 成功且 mandate 提交前，交易连接器通道保持只读。",
    liveAuthorize: "授权连接器",
    liveRunner: "Runner",
    liveStopped: "已停止",
    liveLastTick: "最近心跳",
    liveActiveMandate: "当前 mandate",
    liveLimitsUnavailable: "限制不可用",
    liveNoActiveMandate: "没有当前 mandate。请让智能体生成一个 mandate，并在启动交易连接器运行前提交它。",
    liveHaltedControls: "已停止 - runner 控制已禁用",
    liveRuntimeActive: "Mandate 范围内运行中",
    liveIdle: "空闲",
    liveStopRunner: "停止 runner",
    liveStartRunner: "启动 runner",
    liveStopRunnerTitle: "停止常驻 runner",
    liveStartRunnerTitle: "启动常驻 runner",
    liveResume: "恢复交易连接器运行",
    liveActionFailed: "交易连接器操作失败。",
    globalKillSwitch: "全局 Kill Switch",
    triggered: "已触发",
    notTriggered: "未触发",
    noBrokerStatus: "暂无 broker 状态。可以先运行“检查交易连接器”。",
    globalHalt: "全局暂停 live runtime",
    brokerHalted: "已暂停",
    brokerRunning: "运行中",
    brokerAuthorized: "已授权",
    brokerConnected: "已连接",
    brokerDisconnected: "未连接",
    yes: "有",
    no: "无",
    toolSteps: "执行步骤",
    toolStepsDesc: "这里展示的是本次 Agent 调用了哪些后端工具。",
    loadingSteps: "正在载入执行步骤",
    noToolSteps: "等待回测、Alpha、矩阵、文档/Web、Swarm、连接器或 Shadow 工具步骤。",
    collapseDetails: "收起详情",
    expandDetails: "展开详情"
  },
  "en-US": {
    pageTitle: "Agent",
    pageSubtitle: "Connected to the current-project Agent Runtime running inside this backend process.",
    capabilities: ["Agent Runtime", "51 source-tool migration matrix", "Finance Skills Library", "Research Goal", "Swarm", "Backtest", "Alpha Zoo", "Documents/Web", "Trading connectors", "Trade journal analyzer", "Shadow Account", "Persistent memory", "Session search"],
    quickPrompts: [
      { label: "Cross-market backtest", prompt: "Backtest a risk-parity portfolio of 000001.SZ, BTC-USDT, and AAPL for full-year 2024, compare against equal-weight baseline" },
      { label: "Check connector", prompt: "List my trading connector profiles, show which one is selected, then check that selected connector. If it is not ready, tell me exactly what setup step is missing. Do not place or modify orders." },
      { label: "Analyze connector portfolio", prompt: "First check whether the selected trading connector profile is connected. If it is not connected or OAuth/token is missing, only explain the missing setup step and do not call account, position, order, or history read tools. If it is connected, summarize my account, positions, concentration, cash, and portfolio risk. Do not place or modify orders." },
      { label: "Agent team", prompt: "[Swarm Team Mode] Use the investment_committee preset to evaluate whether to go long or short on NVDA given current market conditions" },
      { label: "Shadow Account", prompt: "Run a shadow backtest for the last 90 days on the US market and break down where my PnL diverged from the shadow (rule violations, early exits, missed signals). If this session has no returns, trades[].pnl, journal artifact_id/file_id, or pasted journal text, ask me to upload or paste data before calling the shadow backtest tool." }
    ],
    examples: EXAMPLE_CATEGORIES_EN,
    toolLabels: TOOL_LABELS_EN,
    ready: "Ready",
    running: "Running",
    cancelling: "Cancelling",
    skipped: "Skipped",
    warning: "Data limited",
    failed: "Failed",
    completed: "Complete",
    newSession: "New session",
    exportChat: "Export chat",
    working: "Agent is working...",
    newMessages: "New messages",
    goalModeChip: "New research goal",
    moreOptions: "More options",
    researchGoal: "Research goal",
    singleStock: "Single-stock analysis",
    goalPlaceholder: "Describe the research goal to bind to this session",
    chatPlaceholder: "Example: run a backtest, check connector status, or analyze the A-share energy storage sector",
    stop: "Stop generation",
    send: "Send",
    loadingSessionTitle: "Loading session",
    loadingSessionDesc: "Restoring historical messages and execution steps...",
    toolFallback: "tool",
    sessions: "Sessions",
    noSessions: "No Agent sessions yet.",
    saveRename: "Save rename",
    cancelRename: "Cancel rename",
    renameSession: "Rename session",
    deleteSession: "Delete session",
    deleteConfirm: "Deleting will remove this session's messages, events, and artifacts. Continue?",
    cancelRequested: "Requested backend cancellation for the current Agent attempt.",
    timeout: "Agent has run for more than 60 minutes without a completion event. Refresh the session or check backend logs.",
    sendFailed: "Failed to send message. Please retry.",
    goalCriteria: [
      "Keep the work research-only; do not place trades",
      "Use current-project authorized tools to collect evidence",
      "Update status when the goal is complete, blocked, waiting for input, or budget-limited"
    ],
    goalPrompt: (raw: string) => [
      "Start working on this research goal now.",
      "Keep it research-only, use available tools when evidence is needed, add concrete evidence to the goal ledger, and keep going until the goal is complete, blocked, waiting for user input, or budget-limited.",
      "",
      `Goal: ${raw}`
    ].join("\n"),
    unnamedGoal: "Untitled research goal",
    goalPanelTitle: "Current research goal",
    noGoal: "No Research Goal is bound yet. Choose \"Research goal\" from the plus menu before sending to create one in the current backend.",
    criteriaTitle: "Acceptance criteria",
    evidenceLedger: "Evidence ledger",
    evidenceCount: (count: number) => `${count} item${count === 1 ? "" : "s"}`,
    noEvidence: "Waiting for Agent tools to write traceable evidence.",
    liveTitle: "Trading connector runtime",
    refresh: "Refresh",
    liveDesc: "Current Agent Runtime /live/status for broker authorization, runner, and kill switch state.",
    liveUnavailable: "The backend did not return live runtime status.",
    liveRuntime: "Trading connector runtime",
    liveStatus: "Trading connector runtime status",
    liveConnected: "connected",
    liveNoConnector: "no connector connected",
    liveHalted: "Halted",
    liveNever: "Never",
    liveUnknown: "Unknown",
    liveJustNow: "Just now",
    liveAgo: "ago",
    liveOrder: "order",
    liveDay: "day",
    liveNoLeverage: "no leverage",
    liveAuthorized: "Authorized",
    liveNotConnected: "Not connected",
    liveConnectProfile: "Connect this profile to enable connector runtime",
    liveAuthorizeInstruction: "Select a broker profile, then authorize it from the desktop session that holds the broker connection.",
    liveAuthorizationNote: "The connector channel stays read-only until OAuth succeeds and a mandate is committed.",
    liveAuthorize: "Authorize connector",
    liveRunner: "Runner",
    liveStopped: "Stopped",
    liveLastTick: "Last tick",
    liveActiveMandate: "Active mandate",
    liveLimitsUnavailable: "limits unavailable",
    liveNoActiveMandate: "No active mandate. Ask the agent to propose one, then commit it before starting the connector runtime.",
    liveHaltedControls: "Halted - runner controls disabled",
    liveRuntimeActive: "Runtime active inside mandate",
    liveIdle: "Idle",
    liveStopRunner: "Stop runner",
    liveStartRunner: "Start runner",
    liveStopRunnerTitle: "Stop the persistent runner",
    liveStartRunnerTitle: "Start the persistent runner",
    liveResume: "Resume connector runtime",
    liveActionFailed: "Connector runtime action failed.",
    globalKillSwitch: "Global Kill Switch",
    triggered: "Triggered",
    notTriggered: "Not triggered",
    noBrokerStatus: "No broker status yet. Run \"Check connectors\" first.",
    globalHalt: "Halt live runtime globally",
    brokerHalted: "Halted",
    brokerRunning: "Running",
    brokerAuthorized: "Authorized",
    brokerConnected: "Connected",
    brokerDisconnected: "Disconnected",
    yes: "Yes",
    no: "No",
    toolSteps: "Execution steps",
    toolStepsDesc: "Shows which backend tools this Agent run called.",
    loadingSteps: "Loading execution steps",
    noToolSteps: "Waiting for backtest, Alpha, matrix, document/web, Swarm, connector, or Shadow tool steps.",
    collapseDetails: "Collapse details",
    expandDetails: "Expand details"
  }
}
