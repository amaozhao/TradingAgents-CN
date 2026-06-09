"use client"

import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react"
import {
  Activity,
  ArrowDown,
  Bot,
  Check,
  CheckCircle2,
  Download,
  FileText,
  Landmark,
  Loader2,
  Pencil,
  Plus,
  Send,
  Sparkles,
  Square,
  Target,
  Trash2,
  TrendingUp,
  Users,
  X
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { MarkdownRenderer } from "@/features/learning/markdown-renderer"
import {
  researchAgentApi,
  type LiveStatus,
  type ParsedResearchStreamEvent,
  type ResearchAgentEvent,
  type ResearchGoal,
  type ResearchMessage,
  type ResearchSession
} from "@/libs/api/research-agent"
import { useAppStore, type AppLanguage } from "@/stores/app-store"

type AgentMessageType = "user" | "answer" | "error" | "tool_call" | "tool_result" | "system"

type AgentMessage = {
  id: string
  type: AgentMessageType
  content: string
  timestamp: number
  tool?: string
  status?: "running" | "ok" | "error"
  elapsedMs?: number
}

type ToolState = {
  id: string
  name: string
  status: "running" | "ok" | "error"
  preview?: string
  artifactId?: string
  elapsedMs?: number
}

const EXAMPLE_CATEGORIES = [
  {
    label: "研究与回测",
    icon: TrendingUp,
    examples: [
      {
        title: "跨市场组合回测",
        desc: "调用 Agent backtest 工具生成策略、运行回测并输出指标",
        prompt: "Create a risk-parity style backtest for 000001.SZ, BTC-USDT, and AAPL from 2025-01-01 to 2026-06-01. Show metrics, risks, and next improvements."
      },
      {
        title: "A 股储能研究",
        desc: "结合 A 股研究、Alpha、矩阵和报告证据",
        prompt: "帮我分析 A 股的储能板块，给出推荐个股、证据和风险点"
      }
    ]
  },
  {
    label: "Alpha 与矩阵",
    icon: Sparkles,
    examples: [
      {
        title: "Alpha Zoo 覆盖检查",
        desc: "运行 Alpha bench / compare，并解释覆盖率和 IC/IR",
        prompt: "Run Alpha Zoo coverage for academic_carhart_mom, academic_cma, academic_mkt_rf on 600519,000001,300750 from 2025-01-01 to 2026-06-03, then explain the result in plain language."
      },
      {
        title: "相关性矩阵",
        desc: "计算候选资产相关性并给出组合分散度建议",
        prompt: "Build a correlation matrix for 600519, 000001, and 300750, then explain which names diversify each other."
      }
    ]
  },
  {
    label: "文档与网页",
    icon: FileText,
    examples: [
      {
        title: "网页研究",
        desc: "读取公开网页并提取研究证据",
        prompt: "Read https://example.com and summarize any market-relevant information. If the page has no finance content, say so clearly."
      },
      {
        title: "PDF/文档分析",
        desc: "上传文件后让 Agent 调用 read_document 读取",
        prompt: "Read the uploaded document and extract the trading thesis, catalysts, risks, and evidence gaps."
      }
    ]
  },
  {
    label: "运行时与连接器",
    icon: Landmark,
    examples: [
      {
        title: "检查交易连接器",
        desc: "列出 profiles、检查选中连接器状态，不下单",
        prompt: "List my trading connector profiles, show which one is selected, then check that selected connector. If it is not ready, tell me exactly what setup step is missing. Do not place or modify orders."
      },
      {
        title: "智能体团队",
        desc: "启动 Agent swarm 投资委员会/研究团队",
        prompt: "Run the investment committee swarm on A-share energy storage opportunities. Use research-only mode and summarize each worker's conclusion."
      }
    ]
  },
  {
    label: "Shadow 与交易日志",
    icon: Activity,
    examples: [
      {
        title: "Shadow Account",
        desc: "扫描策略信号、回测并渲染 shadow 报告",
        prompt: "Use Shadow Account tools to scan this strategy idea: buy momentum breakouts after volume expansion and exit on failed retest. Run a safe research-only shadow backtest if enough data is available."
      },
      {
        title: "交易日志诊断",
        desc: "分析交易日志中的纪律、风险和行为问题",
        prompt: "Analyze my trade journal and identify recurring mistakes, risk rule breaches, and one concrete improvement plan."
      }
    ]
  }
]

const CAPABILITY_CHIPS = [
  "Agent Runtime",
  "51 个源工具迁移矩阵",
  "Research Goal",
  "Swarm",
  "Backtest",
  "Alpha Zoo",
  "文档/Web",
  "交易连接器",
  "Shadow Account"
]

const AGENT_COMPLETION_POLL_TIMEOUT_MS = 60 * 60_000
const COMPOSER_MIN_HEIGHT = 44
const COMPOSER_MAX_HEIGHT = 128

const QUICK_RESEARCH_PROMPTS = [
  { label: "跨市场回测", prompt: "Create a risk-parity style backtest for 000001.SZ, BTC-USDT, and AAPL from 2025-01-01 to 2026-06-01." },
  { label: "检查交易连接器", prompt: "List my trading connector profiles and check the selected connector. Do not place or modify orders." },
  { label: "智能体团队", prompt: "Run the investment committee swarm on A-share energy storage opportunities in research-only mode." },
  { label: "Shadow Account", prompt: "Use Shadow Account tools to scan a momentum breakout strategy and produce a research-only shadow report if possible." }
]

const EXAMPLE_CATEGORIES_EN: typeof EXAMPLE_CATEGORIES = [
  {
    label: "Research and backtests",
    icon: TrendingUp,
    examples: [
      {
        title: "Cross-market portfolio backtest",
        desc: "Use the Agent backtest tool to build a strategy, run it, and summarize metrics",
        prompt: "Create a risk-parity style backtest for 000001.SZ, BTC-USDT, and AAPL from 2025-01-01 to 2026-06-01. Show metrics, risks, and next improvements."
      },
      {
        title: "A-share energy storage research",
        desc: "Combine A-share research, Alpha evidence, matrices, and reports",
        prompt: "Analyze the A-share energy storage sector, then provide recommended names, supporting evidence, and risk points."
      }
    ]
  },
  {
    label: "Alpha and matrices",
    icon: Sparkles,
    examples: [
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
  },
  {
    label: "Documents and web",
    icon: FileText,
    examples: [
      {
        title: "Web research",
        desc: "Read public pages and extract research evidence",
        prompt: "Read https://example.com and summarize any market-relevant information. If the page has no finance content, say so clearly."
      },
      {
        title: "PDF/document analysis",
        desc: "Upload a file, then let the Agent call read_document",
        prompt: "Read the uploaded document and extract the trading thesis, catalysts, risks, and evidence gaps."
      }
    ]
  },
  {
    label: "Runtime and connectors",
    icon: Landmark,
    examples: [
      {
        title: "Check trading connectors",
        desc: "List profiles and check the selected connector without placing orders",
        prompt: "List my trading connector profiles, show which one is selected, then check that selected connector. If it is not ready, tell me exactly what setup step is missing. Do not place or modify orders."
      },
      {
        title: "Agent team",
        desc: "Run an Agent swarm investment committee or research team",
        prompt: "Run the investment committee swarm on A-share energy storage opportunities. Use research-only mode and summarize each worker's conclusion."
      }
    ]
  },
  {
    label: "Shadow and trade journals",
    icon: Activity,
    examples: [
      {
        title: "Shadow Account",
        desc: "Scan strategy signals, backtest, and render a shadow report",
        prompt: "Use Shadow Account tools to scan this strategy idea: buy momentum breakouts after volume expansion and exit on failed retest. Run a safe research-only shadow backtest if enough data is available."
      },
      {
        title: "Trade journal diagnosis",
        desc: "Analyze discipline, risk, and behavior issues in a trade journal",
        prompt: "Analyze my trade journal and identify recurring mistakes, risk rule breaches, and one concrete improvement plan."
      }
    ]
  }
]

const TOOL_LABELS: Record<string, { title: string; desc: string }> = {
  load_skill: { title: "加载能力模块", desc: "加载工具或技能说明" },
  bash: { title: "命令执行", desc: "执行辅助命令并收集输出" },
  screening_run: { title: "股票筛选", desc: "构建候选池并筛掉不满足条件的标的" },
  alpha_bench: { title: "Alpha 覆盖检查", desc: "检查候选股票可用因子、覆盖率和有效性" },
  correlation_matrix: { title: "相关性矩阵", desc: "分析候选股票之间的相关性和组合分散度" },
  single_stock_analysis: { title: "单股分析", desc: "生成单股证据、风险点和研究摘要" },
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

const TOOL_LABELS_EN: Record<string, { title: string; desc: string }> = {
  load_skill: { title: "Load skill", desc: "Load a tool or skill description" },
  bash: { title: "Command execution", desc: "Run an auxiliary command and collect output" },
  screening_run: { title: "Stock screening", desc: "Build a candidate pool and filter names" },
  alpha_bench: { title: "Alpha coverage check", desc: "Check factor availability, coverage, and validity" },
  correlation_matrix: { title: "Correlation matrix", desc: "Analyze correlations and portfolio diversification" },
  single_stock_analysis: { title: "Single-stock analysis", desc: "Generate evidence, risks, and a research summary" },
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

const AGENT_TEXT = {
  "zh-CN": {
    pageSubtitle: "已接入当前项目 Agent Runtime，并运行在当前后端进程内。",
    currentProjectDescription: "当前项目 Agent Runtime：会话、工具调用、Research Goal、Swarm、回测、文档/Web、交易连接器和 Shadow Account。",
    capabilities: CAPABILITY_CHIPS,
    quickPrompts: QUICK_RESEARCH_PROMPTS,
    examples: EXAMPLE_CATEGORIES,
    toolLabels: TOOL_LABELS,
    ready: "就绪",
    running: "运行中",
    cancelling: "取消中",
    failed: "失败",
    completed: "完成",
    newSession: "新会话",
    exportChat: "导出聊天",
    working: "智能体正在工作...",
    newMessages: "新消息",
    goalModeChip: "新研究目标",
    moreOptions: "更多选项",
    researchGoal: "研究目标",
    goalPlaceholder: "描述要绑定到当前会话的研究目标",
    chatPlaceholder: "例如：运行回测、检查连接器状态，或分析 A 股储能板块",
    stop: "停止生成",
    send: "发送",
    loadingSessionTitle: "正在载入会话",
    loadingSessionDesc: "正在恢复历史消息和执行步骤...",
    toolFallback: "tool",
    sessions: "Sessions",
    noSessions: "还没有 Agent 会话。",
    scopeTitle: "当前 Agent 范围",
    scopeDesc: "当前页面直接调用当前项目 research-agent 后端，不依赖外部运行时。",
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
    pageSubtitle: "Connected to the current-project Agent Runtime running inside this backend process.",
    currentProjectDescription: "Current-project Agent Runtime: sessions, tool calls, Research Goal, Swarm, backtests, documents/web, trading connectors, and Shadow Account.",
    capabilities: ["Agent Runtime", "51 source-tool migration matrix", "Research Goal", "Swarm", "Backtest", "Alpha Zoo", "Documents/Web", "Trading connectors", "Shadow Account"],
    quickPrompts: [
      { label: "Cross-market backtest", prompt: "Create a risk-parity style backtest for 000001.SZ, BTC-USDT, and AAPL from 2025-01-01 to 2026-06-01." },
      { label: "Check connectors", prompt: "List my trading connector profiles and check the selected connector. Do not place or modify orders." },
      { label: "Agent team", prompt: "Run the investment committee swarm on A-share energy storage opportunities in research-only mode." },
      { label: "Shadow Account", prompt: "Use Shadow Account tools to scan a momentum breakout strategy and produce a research-only shadow report if possible." }
    ],
    examples: EXAMPLE_CATEGORIES_EN,
    toolLabels: TOOL_LABELS_EN,
    ready: "Ready",
    running: "Running",
    cancelling: "Cancelling",
    failed: "Failed",
    completed: "Complete",
    newSession: "New session",
    exportChat: "Export chat",
    working: "Agent is working...",
    newMessages: "New messages",
    goalModeChip: "New research goal",
    moreOptions: "More options",
    researchGoal: "Research goal",
    goalPlaceholder: "Describe the research goal to bind to this session",
    chatPlaceholder: "Example: run a backtest, check connector status, or analyze the A-share energy storage sector",
    stop: "Stop generation",
    send: "Send",
    loadingSessionTitle: "Loading session",
    loadingSessionDesc: "Restoring historical messages and execution steps...",
    toolFallback: "tool",
    sessions: "Sessions",
    noSessions: "No Agent sessions yet.",
    scopeTitle: "Current Agent scope",
    scopeDesc: "This page calls the current-project research-agent backend directly and does not depend on an external runtime.",
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


function nowId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function eventContent(data: Record<string, unknown>) {
  return String(data.content || data.text || data.delta || data.summary || "")
}

function formatEventValue(value: unknown) {
  if (value == null) return ""
  if (typeof value === "string") return value === "[object Object]" ? "" : value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function previewFromEventData(data: Record<string, unknown>) {
  for (const key of ["preview", "result", "error", "content", "text", "summary"] as const) {
    const formatted = formatEventValue(data[key])
    if (formatted) return formatted
  }
  return ""
}

function textValue(value: unknown) {
  return typeof value === "string" ? value.trim() : ""
}

function createGoalDraft(raw: string, text: typeof AGENT_TEXT[AppLanguage]) {
  const lines = raw.split("\n").map((line) => line.trim()).filter(Boolean)
  const title = (lines[0] || raw).slice(0, 120) || text.researchGoal
  return {
    title,
    description: raw,
    criteria: text.goalCriteria
  }
}

function mergeGoalEvent(current: ResearchGoal | null, eventName: string, data: Record<string, unknown>): ResearchGoal | null {
  if (eventName === "goal.created") {
    return {
      ...(current || {}),
      goal_id: textValue(data.goal_id) || current?.goal_id || "current-goal",
      title: textValue(data.title) || current?.title,
      status: textValue(data.status) || current?.status || "active",
      updated_at: textValue(data.updated_at) || current?.updated_at
    }
  }
  if (eventName === "goal.updated") {
    const updates = data.updates && typeof data.updates === "object" ? data.updates as Record<string, unknown> : data
    return {
      ...(current || {}),
      goal_id: textValue(data.goal_id) || current?.goal_id || "current-goal",
      title: textValue(updates.title) || current?.title,
      description: textValue(updates.description) || current?.description,
      status: textValue(updates.status) || current?.status,
      status_reason: textValue(updates.reason) || textValue(updates.status_reason) || current?.status_reason,
      updated_at: textValue(data.updated_at) || current?.updated_at
    }
  }
  if (eventName === "goal.evidence") {
    const evidence = data.evidence && typeof data.evidence === "object" ? data.evidence as Record<string, unknown> : data
    return {
      ...(current || {}),
      goal_id: textValue(data.goal_id) || current?.goal_id || "current-goal",
      status: current?.status || "active",
      evidence: [
        ...(current?.evidence || []),
        {
          evidence_id: textValue(evidence.evidence_id) || textValue(data.evidence_id),
          kind: textValue(evidence.kind) || textValue(data.kind) || "note",
          summary: textValue(evidence.summary) || textValue(data.summary) || previewFromEventData(data),
          artifact_id: textValue(evidence.artifact_id) || textValue(data.artifact_id) || null,
          message_id: textValue(evidence.message_id) || textValue(data.message_id) || null,
          created_at: textValue(evidence.created_at) || textValue(data.created_at)
        }
      ],
      updated_at: textValue(data.updated_at) || current?.updated_at
    }
  }
  return current
}

function parseJsonPreview(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : null
  } catch {
    return null
  }
}

function compactPreviewText(value: unknown, maxLength: number | null = 220) {
  const lines = formatEventValue(value)
    .replace(/<skill\b[^>]*>/g, "")
    .replace(/<\/skill>/g, "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/[#*`>]+/g, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  const text = maxLength == null
    ? lines.join("\n").replace(/[ \t]+/g, " ")
    : lines.join(" ").replace(/\s+/g, " ")
  return maxLength == null ? text : text.slice(0, maxLength)
}

function decodeJsonFragment(value: string) {
  try {
    return JSON.parse(`"${value}"`) as string
  } catch {
    return value
      .replace(/\\"/g, "\"")
      .replace(/\\n/g, "\n")
      .replace(/\\t/g, " ")
  }
}

function jsonFragmentStringField(raw: string, key: string) {
  const match = raw.match(new RegExp(`"${key}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)`))
  return match ? decodeJsonFragment(match[1]) : ""
}

function jsonFragmentNumberField(raw: string, key: string) {
  const match = raw.match(new RegExp(`"${key}"\\s*:\\s*(-?\\d+(?:\\.\\d+)?)`))
  return match ? Number(match[1]) : undefined
}

function jsonFragmentPreview(toolName: string, raw: string, maxLength: number | null = 220) {
  const result = {
    status: jsonFragmentStringField(raw, "status"),
    error: jsonFragmentStringField(raw, "error"),
    content: jsonFragmentStringField(raw, "content"),
    stdout: jsonFragmentStringField(raw, "stdout"),
    stderr: jsonFragmentStringField(raw, "stderr"),
    exit_code: jsonFragmentNumberField(raw, "exit_code") ?? jsonFragmentNumberField(raw, "exitcode")
  }

  if (toolName === "load_skill" && result.content) return skillPreview(result.content, maxLength)
  if (toolName === "bash") return bashPreview(result, maxLength)
  if (result.error) return `工具失败：${compactPreviewText(result.error, maxLength)}`
  if (result.content) return compactPreviewText(result.content, maxLength)
  if (result.stdout || result.stderr) return bashPreview(result, maxLength)
  return compactPreviewText(raw.replace(/^\{+/, ""), maxLength)
}

function skillPreview(content: string, maxLength: number | null = 220) {
  const name = content.match(/<skill\s+name=["']([^"']+)["']/)?.[1]
  const heading = content.match(/^#{1,6}\s+(.+)$/m)?.[1]
  const body = compactPreviewText(content, maxLength)
  const prefix = name ? `已加载技能 ${name}` : "技能已加载"
  if (heading && body) return `${prefix}: ${heading} - ${body}`
  if (heading) return `${prefix}: ${heading}`
  return body ? `${prefix}: ${body}` : prefix
}

function bashPreview(result: Record<string, unknown>, maxLength: number | null = 220) {
  const exitCode = result.exit_code ?? result.code
  const stdout = compactPreviewText(result.stdout, maxLength)
  const stderr = compactPreviewText(result.stderr || result.error, maxLength)
  const failed = String(result.status || "") === "error" || (typeof exitCode === "number" && exitCode !== 0)
  const prefix = failed
    ? `命令失败${exitCode != null ? `（exit ${exitCode}）` : ""}`
    : "命令执行成功"
  if (stdout && stderr) return `${prefix}。输出：${stdout}。错误：${stderr}`
  if (stderr) return `${prefix}。错误：${stderr}`
  if (stdout) return `${prefix}。输出：${stdout}`
  return prefix
}

function evidencePreview(result: Record<string, unknown>, maxLength: number | null = 220) {
  const evidence = result.evidence
  if (evidence && typeof evidence === "object") {
    const record = evidence as Record<string, unknown>
    const text = compactPreviewText(record.summary || record.text || record.content, maxLength)
    if (text) return `证据已写入：${text}`
  }
  const summary = compactPreviewText(result.summary || result.content || result.text, maxLength)
  if (summary) return `证据已写入：${summary}`
  return result.status === "ok" ? "证据已写入 goal ledger" : compactPreviewText(result.error || result, maxLength)
}

function goalStatusPreview(result: Record<string, unknown>, maxLength: number | null = 220) {
  const directStatus = compactPreviewText(result.status, maxLength)
  const directTitle = compactPreviewText(result.title || result.objective, maxLength)
  if (directStatus && directTitle) return `目标状态已更新为 ${directStatus}：${directTitle}`
  if (directStatus) return `目标状态已更新为 ${directStatus}`

  const snapshot = result.snapshot
  if (snapshot && typeof snapshot === "object") {
    const goal = (snapshot as Record<string, unknown>).goal
    if (goal && typeof goal === "object") {
      const status = compactPreviewText((goal as Record<string, unknown>).status, maxLength)
      const objective = compactPreviewText((goal as Record<string, unknown>).objective, maxLength)
      if (status && objective) return `目标状态已更新为 ${status}：${objective}`
      if (status) return `目标状态已更新为 ${status}`
    }
  }
  return result.status === "ok" ? "目标状态已更新" : compactPreviewText(result.error || result, maxLength)
}

function readableToolPreview(tool: ToolState, maxLength: number | null = 220) {
  if (!tool.preview) return ""
  const parsed = parseJsonPreview(tool.preview)
  if (!parsed) {
    const trimmed = tool.preview.trim()
    return trimmed.startsWith("{")
      ? jsonFragmentPreview(tool.name, trimmed, maxLength)
      : compactPreviewText(tool.preview, maxLength)
  }

  if (tool.name === "load_skill") {
    return skillPreview(formatEventValue(parsed.content || parsed.text || parsed.preview), maxLength)
  }
  if (tool.name === "bash") return bashPreview(parsed, maxLength)
  if (tool.name === "add_goal_evidence") return evidencePreview(parsed, maxLength)
  if (tool.name === "update_research_goal_status") return goalStatusPreview(parsed, maxLength)

  const content = parsed.content || parsed.text || parsed.summary || parsed.stdout || parsed.error || parsed.preview
  if (content) return compactPreviewText(content, maxLength)
  if (parsed.status === "ok") return "工具执行完成"
  return compactPreviewText(parsed, maxLength)
}

function normalizePersistedEvent(event: ResearchAgentEvent): ParsedResearchStreamEvent {
  return {
    event: event.event_type,
    data: event.payload || {},
    eventId: event.event_id == null ? undefined : String(event.event_id)
  }
}

function messageTimestamp(message: ResearchMessage) {
  if (message.created_at) {
    const parsed = new Date(message.created_at).getTime()
    if (Number.isFinite(parsed)) return parsed
  }
  const value = message.metadata?.created_at
  if (typeof value === "string") {
    const parsed = new Date(value).getTime()
    if (Number.isFinite(parsed)) return parsed
  }
  return Date.now()
}

function messagesFromApi(messages: ResearchMessage[]): AgentMessage[] {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .filter((message) => message.role !== "assistant" || message.content.trim().length > 0)
    .map((message) => ({
      id: message.message_id,
      type: message.role === "user" ? "user" : "answer",
      content: message.content,
      timestamp: messageTimestamp(message)
    }))
}

function finalAnswerFromEvents(events: ParsedResearchStreamEvent[]) {
  const completed = events.filter((event) => event.event === "message_completed" || event.event === "attempt.completed")
  const last = completed.at(-1)
  return last ? eventContent(last.data) || String(last.data.summary || "") : ""
}

function attemptResultContent(attempt: ResearchAttempt) {
  const result = attempt.result
  if (!result || typeof result !== "object") return ""
  const content = result.content
  return typeof content === "string" ? content.trim() : ""
}

function failureMessageFromEvents(events: ParsedResearchStreamEvent[]) {
  const failed = events.filter((event) => event.event === "task_failed" || event.event === "attempt.failed" || event.event === "job_failed")
  for (const event of failed.reverse()) {
    const content = eventContent(event.data) || String(event.data.error || "")
    if (content) return content
  }
  return ""
}

function toolsFromEvents(events: ParsedResearchStreamEvent[]): ToolState[] {
  const tools = new Map<string, ToolState>()
  for (const event of events) {
    const toolName = String(event.data.tool_name || event.data.tool || "")
    if (!toolName) continue
    if (event.event === "tool_started" || event.event === "tool_call") {
      tools.set(toolName, {
        id: toolName,
        name: toolName,
        status: "running",
        preview: previewFromEventData(event.data)
      })
    }
    if (event.event === "tool_progress" || event.event === "tool_heartbeat") {
      const existing = tools.get(toolName)
      tools.set(toolName, {
        id: toolName,
        name: toolName,
        status: "running",
        preview: previewFromEventData(event.data) || existing?.preview,
        artifactId: existing?.artifactId,
        elapsedMs: existing?.elapsedMs
      })
    }
    if (event.event === "tool_completed" || event.event === "tool_failed" || event.event === "tool_result") {
      const failed = event.event === "tool_failed" || String(event.data.status || "ok") === "error"
      tools.set(toolName, {
        id: toolName,
        name: toolName,
        status: failed ? "error" : "ok",
        preview: previewFromEventData(event.data),
        artifactId: event.data.artifact_id ? String(event.data.artifact_id) : undefined,
        elapsedMs: typeof event.data.elapsed_ms === "number" ? event.data.elapsed_ms : undefined
      })
    }
  }
  return Array.from(tools.values())
}

function WelcomeScreen({
  onExample,
  text
}: {
  onExample: (prompt: string) => void
  text: typeof AGENT_TEXT[AppLanguage]
}) {
  return (
    <div className="mx-auto flex max-w-4xl flex-col items-center px-4 py-10 text-center">
      <div className="mb-5 flex size-14 items-center justify-center rounded-2xl border bg-primary text-primary-foreground shadow-sm">
        <Bot className="size-7" />
      </div>
      <h1 className="text-2xl font-semibold tracking-normal text-foreground">TradingAgents-CN Agent</h1>
      <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
        {text.currentProjectDescription}
      </p>
      <div className="mt-4 flex max-w-2xl flex-wrap justify-center gap-2">
        {text.capabilities.map((chip) => (
          <span key={chip} className="rounded-full border bg-background px-2.5 py-1 text-[11px] text-muted-foreground">
            {chip}
          </span>
        ))}
      </div>
      <div className="mt-7 grid w-full gap-3 md:grid-cols-2">
        {text.examples.map((category) => {
          const Icon = category.icon
          return (
            <section key={category.label} className="rounded-lg border bg-background p-3 text-left">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                <Icon className="size-4 text-primary" />
                {category.label}
              </div>
              <div className="grid gap-2">
                {category.examples.map((example) => (
                  <button
                    key={example.title}
                    type="button"
                    onClick={() => onExample(example.prompt)}
                    className="rounded-md border bg-muted/20 px-3 py-2 text-left transition-colors hover:border-primary/50 hover:bg-muted/40"
                  >
                    <span className="block text-sm font-medium">{example.title}</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">{example.desc}</span>
                  </button>
                ))}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}

function SessionLoadingView({ text }: { text: typeof AGENT_TEXT[AppLanguage] }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-10">
      <div className="flex items-center gap-3 rounded-lg border bg-background px-4 py-3 shadow-sm">
        <div className="flex size-9 items-center justify-center rounded-full bg-primary/10">
          <Loader2 className="size-4 animate-spin text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium">{text.loadingSessionTitle}</p>
          <p className="mt-1 text-xs text-muted-foreground">{text.loadingSessionDesc}</p>
        </div>
      </div>
      <div className="space-y-3">
        {[0, 1, 2].map((item) => (
          <div key={item} className="animate-pulse rounded-xl border bg-background p-4">
            <div className="h-3 w-1/3 rounded bg-muted" />
            <div className="mt-3 h-3 w-full rounded bg-muted" />
            <div className="mt-2 h-3 w-5/6 rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  )
}

function MessageBubble({
  message,
  text
}: {
  message: AgentMessage
  text: typeof AGENT_TEXT[AppLanguage]
}) {
  if (message.type === "tool_call" || message.type === "tool_result") {
    const ok = message.status === "ok"
    const failed = message.status === "error"
    const label = text.toolLabels[message.tool || ""]?.title || message.tool || text.toolFallback
    return (
      <div className="flex gap-3">
        <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-full border bg-muted">
          {message.type === "tool_call" && message.status === "running" ? (
            <Loader2 className="size-4 animate-spin text-primary" />
          ) : (
            <CheckCircle2 className={`size-4 ${failed ? "text-destructive" : ok ? "text-emerald-600" : "text-muted-foreground"}`} />
          )}
        </div>
        <div className="min-w-0 flex-1 rounded-lg border bg-muted/20 px-3 py-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium">{label}</span>
            <span className="font-mono text-[11px] text-muted-foreground">{message.tool || text.toolFallback}</span>
            <span className="rounded-full bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
              {message.status === "running" ? text.running : message.status === "error" ? text.failed : text.completed}
            </span>
            {message.elapsedMs != null && (
              <span className="text-[11px] text-muted-foreground">{(message.elapsedMs / 1000).toFixed(1)}s</span>
            )}
          </div>
          {message.content && <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-xs text-muted-foreground">{message.content}</p>}
        </div>
      </div>
    )
  }

  const isUser = message.type === "user"
  const isError = message.type === "error"
  return (
    <div data-testid={`agent-message-${message.type}`} className={`flex gap-3 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-full border bg-background">
          <Bot className="size-4 text-primary" />
        </div>
      )}
      <div
        className={[
          "max-w-[82%] rounded-xl px-4 py-3 text-sm leading-6",
          isUser ? "bg-primary text-primary-foreground" : "border bg-background",
          isError ? "border-destructive/40 bg-destructive/5 text-destructive" : ""
        ].join(" ")}
      >
        {isUser || isError || message.type === "system" ? (
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <MarkdownRenderer
            content={message.content}
            className="overflow-x-auto text-sm leading-7 [&_h1:first-child]:mt-0 [&_h2:first-child]:mt-0 [&_h3:first-child]:mt-0 [&_table]:min-w-max [&_table]:text-xs [&_td]:align-top [&_th]:whitespace-nowrap"
          />
        )}
      </div>
    </div>
  )
}

function brokerStatusText(status: LiveStatus["brokers"][number], text: typeof AGENT_TEXT[AppLanguage]) {
  if (status.halted) return text.brokerHalted
  if (status.runner?.alive) return text.brokerRunning
  if (status.mandate && !status.mandate.expired) return text.brokerAuthorized
  if (status.auth.oauth_token_present) return text.brokerConnected
  return text.brokerDisconnected
}

function brokerStatusTone(status: LiveStatus["brokers"][number]) {
  if (status.halted) return "border-destructive/40 bg-destructive/5 text-destructive"
  if (status.runner?.alive) return "border-emerald-500/40 bg-emerald-500/5 text-emerald-700"
  if (status.mandate && !status.mandate.expired) return "border-sky-500/40 bg-sky-500/5 text-sky-700"
  return "border-muted bg-muted/30 text-muted-foreground"
}

function GoalPanel({
  goal,
  loading,
  text
}: {
  goal: ResearchGoal | null
  loading: boolean
  text: typeof AGENT_TEXT[AppLanguage]
}) {
  const evidence = goal?.evidence || []
  const latestEvidence = evidence.at(-1)
  return (
    <section className="rounded-lg border bg-background p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-medium">
          <Target className="size-4 text-primary" />
          {text.goalPanelTitle}
        </h2>
        {loading ? (
          <Loader2 className="size-4 animate-spin text-primary" />
        ) : goal?.status ? (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
            {goal.status}
          </span>
        ) : null}
      </div>

      {!goal ? (
        <p className="mt-3 rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
          {text.noGoal}
        </p>
      ) : (
        <div className="mt-3 space-y-3 text-xs">
          <div>
            <p className="font-medium leading-5">{goal.title || text.unnamedGoal}</p>
            {goal.description && (
              <p className="mt-1 line-clamp-3 whitespace-pre-wrap leading-5 text-muted-foreground">{goal.description}</p>
            )}
            {goal.status_reason && (
              <p className="mt-1 rounded-md bg-muted/40 px-2 py-1 leading-5 text-muted-foreground">
                {goal.status_reason}
              </p>
            )}
          </div>

          {goal.criteria && goal.criteria.length > 0 && (
            <div>
              <p className="mb-1 font-medium text-muted-foreground">{text.criteriaTitle}</p>
              <ul className="space-y-1">
                {goal.criteria.slice(0, 4).map((item, index) => (
                  <li key={`${item}-${index}`} className="rounded-md bg-muted/30 px-2 py-1 leading-5 text-muted-foreground">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="rounded-md border bg-muted/20 px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="font-medium">{text.evidenceLedger}</span>
              <span className="text-muted-foreground">{text.evidenceCount(evidence.length)}</span>
            </div>
            {latestEvidence?.summary ? (
              <p className="mt-1 line-clamp-3 leading-5 text-muted-foreground">{latestEvidence.summary}</p>
            ) : (
              <p className="mt-1 leading-5 text-muted-foreground">{text.noEvidence}</p>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

function LiveStatusPanel({
  status,
  loading,
  unavailable,
  onRefresh,
  onHalt,
  text
}: {
  status: LiveStatus | null
  loading: boolean
  unavailable: boolean
  onRefresh: () => void
  onHalt: () => void
  text: typeof AGENT_TEXT[AppLanguage]
}) {
  const brokers = status?.brokers || []
  const hasActiveRuntime = Boolean(status?.global_halted || brokers.some((item) => item.runner?.alive || item.mandate || item.halted))

  return (
    <section className="rounded-lg border bg-background p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">{text.liveTitle}</h2>
        <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onRefresh}>
          {loading ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Activity className="mr-1 size-3" />}
          {text.refresh}
        </Button>
      </div>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        {text.liveDesc}
      </p>
      {unavailable ? (
        <p className="mt-3 rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
          {text.liveUnavailable}
        </p>
      ) : (
        <div className="mt-3 space-y-2">
          <div className={`rounded-md border px-3 py-2 text-xs ${status?.global_halted ? "border-destructive/40 bg-destructive/5 text-destructive" : "bg-muted/20 text-muted-foreground"}`}>
            {text.globalKillSwitch}: {status?.global_halted ? text.triggered : text.notTriggered}
          </div>
          {brokers.length === 0 ? (
            <p className="rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
              {text.noBrokerStatus}
            </p>
          ) : brokers.map((broker) => (
            <div key={broker.auth.broker} className={`rounded-md border px-3 py-2 text-xs ${brokerStatusTone(broker)}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium uppercase">{broker.auth.broker}</span>
                <span>{brokerStatusText(broker, text)}</span>
              </div>
              <div className="mt-1 grid grid-cols-2 gap-1 text-[11px] opacity-80">
                <span>OAuth: {broker.auth.oauth_token_present ? text.yes : text.no}</span>
                <span>Runner: {broker.runner?.alive ? "alive" : "idle"}</span>
                <span>Mandate: {broker.mandate && !broker.mandate.expired ? "active" : "none"}</span>
                <span>Halt: {broker.halted ? "yes" : "no"}</span>
              </div>
            </div>
          ))}
          {hasActiveRuntime && (
            <Button type="button" variant="destructive" size="sm" className="w-full justify-center" onClick={onHalt}>
              <Square className="mr-2 size-4" />{text.globalHalt}
            </Button>
          )}
        </div>
      )}
    </section>
  )
}

function ToolRail({
  tools,
  goal,
  running,
  loading,
  liveStatus,
  liveStatusLoading,
  liveStatusUnavailable,
  onRefreshLiveStatus,
  onHaltLive,
  text
}: {
  tools: ToolState[]
  goal: ResearchGoal | null
  running: boolean
  loading: boolean
  liveStatus: LiveStatus | null
  liveStatusLoading: boolean
  liveStatusUnavailable: boolean
  onRefreshLiveStatus: () => void
  onHaltLive: () => void
  text: typeof AGENT_TEXT[AppLanguage]
}) {
  const [expandedTools, setExpandedTools] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    setExpandedTools((current) => {
      const visibleIds = new Set(tools.map((tool) => tool.id))
      const next = new Set(Array.from(current).filter((id) => visibleIds.has(id)))
      return next.size === current.size ? current : next
    })
  }, [tools])

  function toggleTool(toolId: string) {
    setExpandedTools((current) => {
      const next = new Set(current)
      if (next.has(toolId)) {
        next.delete(toolId)
      } else {
        next.add(toolId)
      }
      return next
    })
  }

  return (
    <aside className="hidden h-full w-[360px] shrink-0 overflow-y-auto border-l bg-muted/10 xl:block">
      <div className="grid min-w-0 gap-4 p-4">
        <section className="min-w-0 rounded-lg border bg-background p-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">{text.toolSteps}</h2>
            {(running || loading) && <Loader2 className="size-4 animate-spin text-primary" />}
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            {text.toolStepsDesc}
          </p>
          <div className="mt-3 space-y-2">
            {loading ? (
              <div className="space-y-2" aria-label={text.loadingSteps}>
                {[0, 1, 2].map((item) => (
                  <div key={item} className="animate-pulse rounded-md border bg-background px-3 py-2">
                    <div className="flex items-center justify-between">
                      <div className="h-3 w-24 rounded bg-muted" />
                      <div className="h-4 w-10 rounded-full bg-muted" />
                    </div>
                    <div className="mt-2 h-3 w-full rounded bg-muted" />
                    <div className="mt-2 h-3 w-2/3 rounded bg-muted" />
                  </div>
                ))}
              </div>
            ) : tools.length === 0 ? (
              <p className="rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
                {text.noToolSteps}
              </p>
            ) : (
              tools.map((tool) => {
                const label = text.toolLabels[tool.name]
                const preview = readableToolPreview(tool, null)
                const expanded = expandedTools.has(tool.id)
                const statusClass = tool.status === "error"
                  ? "bg-destructive/10 text-destructive"
                  : tool.status === "running"
                    ? "bg-primary/10 text-primary"
                    : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                return (
                  <div key={tool.id} className="min-w-0 rounded-md border bg-background px-3 py-2 shadow-sm">
                    <button
                      type="button"
                      className="block w-full text-left"
                      aria-expanded={expanded}
                      onClick={() => toggleTool(tool.id)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate text-xs font-medium">{label?.title || tool.name}</span>
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${statusClass}`}>
                          {tool.status === "running" ? text.running : tool.status === "error" ? text.failed : text.completed}
                        </span>
                      </div>
                      <p className="mt-1 break-words text-[11px] leading-4 text-muted-foreground [overflow-wrap:anywhere]">{label?.desc || tool.name}</p>
                      <p className="mt-1 text-[10px] font-medium text-primary">
                        {expanded ? text.collapseDetails : text.expandDetails}
                      </p>
                    </button>
                    {expanded && preview && (
                      <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted/40 p-2 font-mono text-[11px] leading-5 text-foreground/80 [overflow-wrap:anywhere]">
                        {preview}
                      </pre>
                    )}
                    {typeof tool.elapsedMs === "number" && (
                      <p className="mt-1 text-[10px] text-muted-foreground">{(tool.elapsedMs / 1000).toFixed(1)}s</p>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </section>

        <GoalPanel goal={goal} loading={loading} text={text} />

        <LiveStatusPanel
          status={liveStatus}
          loading={liveStatusLoading}
          unavailable={liveStatusUnavailable}
          onRefresh={onRefreshLiveStatus}
          onHalt={onHaltLive}
          text={text}
        />
      </div>
    </aside>
  )
}

function SessionRail({
  sessions,
  activeSessionId,
  running,
  onNew,
  onSelect,
  onRename,
  onDelete,
  text
}: {
  sessions: ResearchSession[]
  activeSessionId: string | null
  running: boolean
  onNew: () => void
  onSelect: (sessionId: string) => void
  onRename: (sessionId: string, title: string) => Promise<void>
  onDelete: (sessionId: string) => Promise<void>
  text: typeof AGENT_TEXT[AppLanguage]
}) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState("")

  async function saveRename(sessionId: string) {
    const title = editingTitle.trim()
    if (!title) return
    await onRename(sessionId, title)
    setEditingId(null)
    setEditingTitle("")
  }

  return (
    <aside className="hidden w-72 shrink-0 border-r bg-muted/10 lg:block">
      <div className="grid h-full grid-rows-[auto_minmax(0,1fr)_auto] gap-4 p-4">
        <Button className="w-full justify-start" onClick={onNew}>
          <Plus className="mr-2 size-4" />{text.newSession}
        </Button>
        <div className="min-h-0 overflow-auto">
          <h2 className="mb-2 text-xs font-medium uppercase text-muted-foreground">{text.sessions}</h2>
          <div className="space-y-1">
            {sessions.length === 0 ? (
              <p className="rounded-lg border border-dashed px-3 py-4 text-xs text-muted-foreground">{text.noSessions}</p>
            ) : (
              sessions.map((session) => {
                const active = session.session_id === activeSessionId
                const editing = editingId === session.session_id
                return (
                  <div
                    key={session.session_id}
                    className={[
                      "group rounded-lg px-2 py-2 text-sm transition-colors",
                      active ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                    ].join(" ")}
                  >
                    {editing ? (
                      <div className="flex items-center gap-1">
                        <input
                          autoFocus
                          value={editingTitle}
                          onChange={(event) => setEditingTitle(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") void saveRename(session.session_id)
                            if (event.key === "Escape") setEditingId(null)
                          }}
                          className="min-w-0 flex-1 rounded border bg-background px-2 py-1 text-foreground outline-none"
                        />
                        <button type="button" className="rounded p-1 hover:bg-background/20" onClick={() => void saveRename(session.session_id)} aria-label={text.saveRename}>
                          <Check className="size-3" />
                        </button>
                        <button type="button" className="rounded p-1 hover:bg-background/20" onClick={() => setEditingId(null)} aria-label={text.cancelRename}>
                          <X className="size-3" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex min-w-0 items-start gap-1">
                        <button
                          type="button"
                          onClick={() => onSelect(session.session_id)}
                          disabled={running}
                          className="min-w-0 flex-1 text-left disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <span className="block truncate">{session.title || "Agent session"}</span>
                          {session.updated_at && (
                            <span className="mt-0.5 block truncate text-[11px] opacity-70">{new Date(session.updated_at).toLocaleString()}</span>
                          )}
                        </button>
                        <div className="flex shrink-0 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                          <button
                            type="button"
                            className="rounded p-1 hover:bg-background/20"
                            onClick={() => {
                              setEditingId(session.session_id)
                              setEditingTitle(session.title || "")
                            }}
                            aria-label={text.renameSession}
                          >
                            <Pencil className="size-3" />
                          </button>
                          <button
                            type="button"
                            className="rounded p-1 hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => void onDelete(session.session_id)}
                            aria-label={text.deleteSession}
                          >
                            <Trash2 className="size-3" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>
        <div className="rounded-lg border bg-background p-3 text-xs text-muted-foreground">
          <div className="mb-2 flex items-center gap-2 font-medium text-foreground">
            <Users className="size-4" />{text.scopeTitle}
          </div>
          {text.scopeDesc}
        </div>
      </div>
    </aside>
  )
}

export function ResearchAgentPage() {
  const language = useAppStore((state) => state.language)
  const text = AGENT_TEXT[language]
  const [sessions, setSessions] = useState<ResearchSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [tools, setTools] = useState<ToolState[]>([])
  const [goal, setGoal] = useState<ResearchGoal | null>(null)
  const [input, setInput] = useState("")
  const [running, setRunning] = useState(false)
  const [sessionLoading, setSessionLoading] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [composerMode, setComposerMode] = useState<"chat" | "goal">("chat")
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [cancelRequested, setCancelRequested] = useState(false)
  const [liveStatus, setLiveStatus] = useState<LiveStatus | null>(null)
  const [liveStatusLoading, setLiveStatusLoading] = useState(false)
  const [liveStatusUnavailable, setLiveStatusUnavailable] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const streamStopRef = useRef<(() => void) | null>(null)
  const completionPollRef = useRef<number | null>(null)
  const lastEventIdRef = useRef("")
  const streamingAnswerIdRef = useRef<string | null>(null)
  const runFinishedRef = useRef(false)
  const sessionLoadSeqRef = useRef(0)

  function resizeComposer() {
    const textarea = composerRef.current
    if (!textarea) return
    textarea.style.height = `${COMPOSER_MIN_HEIGHT}px`
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, COMPOSER_MIN_HEIGHT), COMPOSER_MAX_HEIGHT)
    textarea.style.height = `${nextHeight}px`
    textarea.style.overflowY = textarea.scrollHeight > COMPOSER_MAX_HEIGHT ? "auto" : "hidden"
  }

  useEffect(() => {
    resizeComposer()
  }, [input, composerMode])

  useEffect(() => {
    void researchAgentApi.listSessions().then((response) => {
      const loaded = response.data || []
      setSessions(loaded)
      if (loaded[0]?.session_id) setActiveSessionId(loaded[0].session_id)
    }).catch(() => setSessions([]))
  }, [])

  useEffect(() => {
    if (!activeSessionId || running) {
      setSessionLoading(false)
      return
    }
    const loadSeq = sessionLoadSeqRef.current + 1
    sessionLoadSeqRef.current = loadSeq
    setSessionLoading(true)
    setMessages([])
    setTools([])
    setGoal(null)
    void Promise.all([
      researchAgentApi.listMessages(activeSessionId),
      researchAgentApi.listEvents(activeSessionId),
      researchAgentApi.getGoal(activeSessionId)
    ]).then(([messageResponse, eventResponse, goalResponse]) => {
      if (sessionLoadSeqRef.current !== loadSeq) return
      const rawEvents = eventResponse.data || []
      const persistedEvents = rawEvents.map(normalizePersistedEvent)
      lastEventIdRef.current = rawEvents.length ? String(rawEvents[rawEvents.length - 1]?.event_id || "") : ""
      const restoredMessages = messagesFromApi(messageResponse.data || [])
      const answer = finalAnswerFromEvents(persistedEvents)
      const failure = failureMessageFromEvents(persistedEvents)
      let nextMessages = answer && !restoredMessages.some((message) => message.type === "answer" && message.content === answer)
        ? [...restoredMessages, { id: nowId("answer"), type: "answer" as const, content: answer, timestamp: Date.now() }]
        : restoredMessages
      if (failure && !nextMessages.some((message) => message.type === "error" && message.content === failure)) {
        nextMessages = [...nextMessages, { id: nowId("error"), type: "error" as const, content: failure, timestamp: Date.now() }]
      }
      setMessages(nextMessages)
      setTools(toolsFromEvents(persistedEvents))
      setGoal(goalResponse.data || persistedEvents.reduce((current, event) => mergeGoalEvent(current, event.event, event.data), null as ResearchGoal | null))
      requestAnimationFrame(scrollToBottom)
    }).catch(() => {
      if (sessionLoadSeqRef.current !== loadSeq) return
      setMessages([])
      setTools([])
      setGoal(null)
    }).finally(() => {
      if (sessionLoadSeqRef.current === loadSeq) setSessionLoading(false)
    })
  }, [activeSessionId, running])

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setShowMenu(false)
    }
    if (showMenu) document.addEventListener("mousedown", onClick)
    return () => document.removeEventListener("mousedown", onClick)
  }, [showMenu])

  useEffect(() => () => {
    stopStream()
    stopCompletionPolling()
  }, [])

  useEffect(() => {
    void refreshLiveStatus()
    const timer = window.setInterval(() => {
      void refreshLiveStatus()
    }, 15_000)
    return () => window.clearInterval(timer)
  }, [])

  const statusLabel = useMemo(() => {
    if (cancelRequested) return text.cancelling
    if (running) return text.running
    return text.ready
  }, [cancelRequested, running, text])

  function scrollToBottom() {
    const list = listRef.current
    if (!list) return
    list.scrollTop = list.scrollHeight
    setShowScrollButton(false)
  }

  function onScroll() {
    const list = listRef.current
    if (!list) return
    setShowScrollButton(list.scrollHeight - list.scrollTop - list.clientHeight > 140)
  }

  function stopStream() {
    streamStopRef.current?.()
    streamStopRef.current = null
    streamingAnswerIdRef.current = null
  }

  function stopCompletionPolling() {
    if (completionPollRef.current != null) {
      window.clearInterval(completionPollRef.current)
      completionPollRef.current = null
    }
  }

  async function refreshCompletedAttemptFromStore(sessionId: string, attemptId: string) {
    const response = await researchAgentApi.listMessages(sessionId)
    const storedMessages = response.data || []
    const completedReply = storedMessages.find((message) => (
      message.role === "assistant" &&
      message.linked_attempt_id === attemptId &&
      message.content.trim().length > 0
    ))
    if (!completedReply) return false

    stopStream()
    stopCompletionPolling()
    runFinishedRef.current = true
    setMessages(messagesFromApi(storedMessages))
    setRunning(false)
    setCancelRequested(false)
    void researchAgentApi.listSessions().then((sessionResponse) => setSessions(sessionResponse.data || [])).catch(() => undefined)
    requestAnimationFrame(scrollToBottom)
    return true
  }

  async function refreshAttemptStatusFromStore(sessionId: string, attemptId: string) {
    if (await refreshCompletedAttemptFromStore(sessionId, attemptId)) return true
    const response = await researchAgentApi.listAttempts(sessionId)
    const attempt = (response.data || []).find((item) => item.attempt_id === attemptId)
    if (!attempt) return false

    if (attempt.status === "failed") {
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      setRunning(false)
      setCancelRequested(false)
      appendStreamMessage({
        id: nowId("error"),
        type: "error",
        content: attempt.error || "Agent execution failed",
        timestamp: Date.now()
      })
      return true
    }

    if (attempt.status === "cancelled") {
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      setRunning(false)
      setCancelRequested(false)
      appendStreamMessage({
        id: nowId("system"),
        type: "system",
        content: text.cancelRequested,
        timestamp: Date.now()
      })
      return true
    }

    if (attempt.status === "completed") {
      const content = attemptResultContent(attempt)
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      setRunning(false)
      setCancelRequested(false)
      if (content) {
        setMessages((current) => {
          if (current.some((message) => message.type === "answer" && message.content.trim() === content)) return current
          const withoutStreamingPlaceholder = streamingAnswerIdRef.current
            ? current.filter((message) => message.id !== streamingAnswerIdRef.current)
            : current
          return [...withoutStreamingPlaceholder, {
            id: nowId("answer"),
            type: "answer",
            content,
            timestamp: Date.now()
          }]
        })
        streamingAnswerIdRef.current = null
        requestAnimationFrame(scrollToBottom)
      }
      void researchAgentApi.listSessions().then((sessionResponse) => setSessions(sessionResponse.data || [])).catch(() => undefined)
      return true
    }

    return false
  }

  function startCompletionPolling(sessionId: string, attemptId?: string) {
    stopCompletionPolling()
    if (!attemptId || runFinishedRef.current) return
    const startedAt = Date.now()
    void refreshAttemptStatusFromStore(sessionId, attemptId).catch(() => undefined)
    completionPollRef.current = window.setInterval(() => {
      if (Date.now() - startedAt > AGENT_COMPLETION_POLL_TIMEOUT_MS) {
        stopCompletionPolling()
        runFinishedRef.current = true
        setRunning(false)
        appendStreamMessage({
          id: nowId("error"),
          type: "error",
          content: text.timeout,
          timestamp: Date.now()
        })
        return
      }
      void refreshAttemptStatusFromStore(sessionId, attemptId).catch(() => undefined)
    }, 3_000)
  }

  function upsertStreamingAnswer(content: string, replace = false) {
    if (!content) return
    setMessages((current) => {
      const existingId = streamingAnswerIdRef.current
      if (!existingId) {
        const id = nowId("answer")
        streamingAnswerIdRef.current = id
        return [...current, { id, type: "answer", content, timestamp: Date.now() }]
      }
      return current.map((message) => (
        message.id === existingId
          ? { ...message, content: replace ? content : `${message.content}${content}`, timestamp: Date.now() }
          : message
      ))
    })
    requestAnimationFrame(scrollToBottom)
  }

  function upsertTool(tool: ToolState) {
    setTools((current) => {
      const index = current.findIndex((item) => item.id === tool.id)
      if (index < 0) return [...current, tool]
      const next = [...current]
      next[index] = { ...next[index], ...tool }
      return next
    })
  }

  function appendStreamMessage(message: AgentMessage) {
    setMessages((current) => [...current, message])
    requestAnimationFrame(scrollToBottom)
  }

  async function refreshLiveStatus() {
    setLiveStatusLoading(true)
    try {
      const response = await researchAgentApi.getLiveStatus()
      setLiveStatus(response.data)
      setLiveStatusUnavailable(false)
    } catch {
      setLiveStatusUnavailable(true)
    } finally {
      setLiveStatusLoading(false)
    }
  }

  function handleStreamEvent(item: ParsedResearchStreamEvent) {
    if (item.eventId) lastEventIdRef.current = item.eventId
    if (item.event === "heartbeat") return
    if (item.event === "goal.created" || item.event === "goal.updated" || item.event === "goal.evidence") {
      setGoal((current) => mergeGoalEvent(current, item.event, item.data))
      return
    }
    if (item.event === "assistant_delta") {
      upsertStreamingAnswer(eventContent(item.data))
      return
    }
    if (item.event === "attempt.started") {
      appendStreamMessage({ id: nowId("attempt-started"), type: "system", content: text.running, timestamp: Date.now() })
      return
    }
    if (item.event === "tool_started" || item.event === "tool_call") {
      const toolName = String(item.data.tool_name || item.data.tool || "tool")
      upsertTool({ id: toolName, name: toolName, status: "running", preview: previewFromEventData(item.data) })
      appendStreamMessage({ id: nowId("tool-call"), type: "tool_call", content: previewFromEventData(item.data), tool: toolName, status: "running", timestamp: Date.now() })
      return
    }
    if (item.event === "tool_progress" || item.event === "tool_heartbeat") {
      const toolName = String(item.data.tool_name || item.data.tool || "tool")
      upsertTool({ id: toolName, name: toolName, status: "running", preview: previewFromEventData(item.data) })
      return
    }
    if (item.event === "tool_completed" || item.event === "tool_failed" || item.event === "tool_result") {
      const toolName = String(item.data.tool_name || item.data.tool || "tool")
      const status = item.event === "tool_failed" || String(item.data.status || "ok") === "error" ? "error" : "ok"
      const preview = previewFromEventData(item.data)
      const elapsedMs = typeof item.data.elapsed_ms === "number" ? item.data.elapsed_ms : undefined
      upsertTool({
        id: toolName,
        name: toolName,
        status,
        preview,
        artifactId: item.data.artifact_id ? String(item.data.artifact_id) : undefined,
        elapsedMs
      })
      appendStreamMessage({ id: nowId("tool-result"), type: "tool_result", content: preview, tool: toolName, status, elapsedMs, timestamp: Date.now() })
      return
    }
    if (item.event === "message_completed") {
      upsertStreamingAnswer(eventContent(item.data), true)
      return
    }
    if (item.event === "task_failed" || item.event === "attempt.failed" || item.event === "job_failed") {
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      setRunning(false)
      setCancelRequested(false)
      appendStreamMessage({ id: nowId("error"), type: "error", content: eventContent(item.data) || String(item.data.error || "Agent execution failed"), timestamp: Date.now() })
      return
    }
    if (item.event === "task_completed" || item.event === "attempt.completed") {
      const attemptId = String(item.data.attempt_id || "")
      if (activeSessionId && attemptId) {
        void refreshCompletedAttemptFromStore(activeSessionId, attemptId)
      }
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      setRunning(false)
      setCancelRequested(false)
      void researchAgentApi.listSessions().then((response) => setSessions(response.data || [])).catch(() => undefined)
      void refreshLiveStatus()
      return
    }
    if (item.event === "live.action" || item.event === "live.halted" || item.event === "live.resumed") {
      void refreshLiveStatus()
    }
  }

  async function ensureSession(title: string) {
    if (activeSessionId) return activeSessionId
    const response = await researchAgentApi.createSession({ title: title.slice(0, 50) || "Agent session" })
    const session = response.data
    setActiveSessionId(session.session_id)
    setSessions((current) => [session, ...current])
    return session.session_id
  }

  function buildPrompt(raw: string) {
    let prompt = raw
    if (composerMode === "goal") {
      prompt = text.goalPrompt(raw)
    }
    return prompt
  }

  async function runPrompt(raw: string) {
    const trimmed = raw.trim()
    if (!trimmed || running) return
    const requestedMode = composerMode
    const finalPrompt = buildPrompt(trimmed)
    setInput("")
    setComposerMode("chat")
    setShowMenu(false)
    setCancelRequested(false)
    runFinishedRef.current = false
    setRunning(true)
    setMessages((current) => [...current, { id: nowId("user"), type: "user", content: finalPrompt, timestamp: Date.now() }])
    requestAnimationFrame(scrollToBottom)

    try {
      const sessionId = await ensureSession(trimmed)
      let linkedGoalId = goal?.goal_id
      if (requestedMode === "goal") {
        const goalResponse = await researchAgentApi.createGoal(sessionId, createGoalDraft(trimmed, text))
        linkedGoalId = goalResponse.data.goal_id
        setGoal(goalResponse.data)
      }
      stopStream()
      streamStopRef.current = researchAgentApi.subscribeEvents(sessionId, { onEvent: handleStreamEvent, onError: () => undefined }, lastEventIdRef.current)
      const appendResponse = await researchAgentApi.appendMessage(sessionId, {
        role: "user",
        content: finalPrompt,
        metadata: {
          source: "research-agent-page",
          mode: requestedMode,
          goal_id: linkedGoalId
        }
      })
      startCompletionPolling(sessionId, appendResponse.data.attempt_id)
    } catch (error) {
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      setMessages((current) => [...current, { id: nowId("error"), type: "error", content: error instanceof Error ? error.message : text.sendFailed, timestamp: Date.now() }])
      setRunning(false)
      setCancelRequested(false)
      requestAnimationFrame(scrollToBottom)
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    void runPrompt(input)
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    void runPrompt(input)
  }

  function handleNewSession() {
    stopStream()
    stopCompletionPolling()
    runFinishedRef.current = true
    setActiveSessionId(null)
    sessionLoadSeqRef.current += 1
    setSessionLoading(false)
    lastEventIdRef.current = ""
    setMessages([])
    setTools([])
    setGoal(null)
    setInput("")
    setComposerMode("chat")
  }

  function handleSelectSession(sessionId: string) {
    if (running) return
    stopStream()
    stopCompletionPolling()
    runFinishedRef.current = true
    lastEventIdRef.current = ""
    setSessionLoading(true)
    setMessages([])
    setTools([])
    setGoal(null)
    setActiveSessionId(sessionId)
  }

  async function handleRenameSession(sessionId: string, title: string) {
    const response = await researchAgentApi.updateSession(sessionId, { title })
    setSessions((current) => current.map((session) => (
      session.session_id === sessionId ? response.data : session
    )))
  }

  async function handleDeleteSession(sessionId: string) {
    if (!window.confirm(text.deleteConfirm)) return
    await researchAgentApi.deleteSession(sessionId)
    setSessions((current) => current.filter((session) => session.session_id !== sessionId))
    if (activeSessionId === sessionId) {
      handleNewSession()
    }
  }

  function handleCancel() {
    const sessionId = activeSessionId
    if (sessionId) void researchAgentApi.cancelSession(sessionId).catch(() => undefined)
    stopStream()
    stopCompletionPolling()
    runFinishedRef.current = true
    setCancelRequested(true)
    setRunning(false)
    setMessages((current) => [
      ...current,
      {
        id: nowId("system"),
        type: "system",
        content: text.cancelRequested,
        timestamp: Date.now()
      }
    ])
  }

  async function handleHaltLive() {
    await researchAgentApi.haltLive({
      reason: "user requested halt from Agent page",
      session_id: activeSessionId
    })
    await refreshLiveStatus()
  }

  function handleExport() {
    if (!messages.length && !goal) return
    const lines = [`# Agent Chat Export`, ``, `Export time: ${new Date().toLocaleString()}`, ``]
    if (goal) {
      lines.push("## Research Goal", "")
      lines.push(`Goal ID: ${goal.goal_id}`, `Status: ${goal.status || "unknown"}`, `Title: ${goal.title || "Untitled"}`, "")
      if (goal.description) lines.push(goal.description, "")
      if (goal.criteria?.length) lines.push("### Criteria", "", ...goal.criteria.map((item) => `- ${item}`), "")
      if (goal.evidence?.length) {
        lines.push("### Evidence", "")
        for (const item of goal.evidence) {
          lines.push(`- ${item.summary || item.kind || item.evidence_id || "Evidence"}`)
        }
        lines.push("")
      }
    }
    for (const message of messages) {
      const label = message.type === "user" ? "User" : message.type === "answer" ? "Assistant" : message.type
      lines.push(`## ${label}`, "", message.content || message.tool || "", "")
    }
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `agent-chat-${new Date().toISOString().slice(0, 10)}.md`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] min-h-[680px] overflow-hidden rounded-lg border bg-background">
      <SessionRail
        sessions={sessions}
        activeSessionId={activeSessionId}
        running={running}
        onNew={handleNewSession}
        onSelect={handleSelectSession}
        onRename={handleRenameSession}
        onDelete={handleDeleteSession}
        text={text}
      />

      <main className="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden">
        <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Bot className="size-5 text-primary" />
              <h1 className="truncate text-base font-semibold">Agent</h1>
              <span className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">{statusLabel}</span>
            </div>
            <p className="mt-1 truncate text-xs text-muted-foreground">
              {text.pageSubtitle}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleNewSession}>
              <Plus className="mr-2 size-4" />{text.newSession}
            </Button>
            {(messages.length > 0 || goal) && (
              <Button variant="outline" size="sm" onClick={handleExport}>
                <Download className="mr-2 size-4" />{text.exportChat}
              </Button>
            )}
          </div>
        </header>

        <div ref={listRef} onScroll={onScroll} className="relative min-h-0 overflow-auto p-5">
          <div className="w-full space-y-4">
            {sessionLoading ? (
              <SessionLoadingView text={text} />
            ) : messages.length === 0 ? (
              <WelcomeScreen onExample={runPrompt} text={text} />
            ) : (
              messages.map((message) => <MessageBubble key={message.id} message={message} text={text} />)
            )}
            {running && (
              <div className="flex gap-3">
                <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-full border bg-background">
                  <Bot className="size-4 text-primary" />
                </div>
                <div className="flex min-w-0 flex-1 items-center gap-2 pt-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin text-primary" />
                  <span>{text.working}</span>
                </div>
              </div>
            )}
          </div>
          {showScrollButton && (
            <button
              type="button"
              onClick={scrollToBottom}
              className="sticky bottom-4 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1 rounded-full bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground shadow-lg"
            >
              <ArrowDown className="size-3" />{text.newMessages}
            </button>
          )}
        </div>

        <form onSubmit={handleSubmit} className="min-w-0 border-t bg-background/90 p-4">
          <div className="w-full min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              {composerMode === "goal" && (
                <span className="inline-flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                  <Target className="size-3" />{text.goalModeChip}
                  <button type="button" onClick={() => setComposerMode("chat")}><X className="size-3" /></button>
                </span>
              )}
            </div>
            <div className="flex min-w-0 items-center gap-2">
              <div ref={menuRef} className="relative">
                <Button type="button" variant="outline" size="icon" disabled={running} onClick={() => setShowMenu((open) => !open)} aria-label={text.moreOptions} className="size-11 rounded-xl">
                  <Plus className="size-4" />
                </Button>
                {showMenu && (
                  <div className="absolute bottom-full left-0 z-20 mb-2 w-56 rounded-lg border bg-background py-1 shadow-lg">
                    <button type="button" onClick={() => { setComposerMode("goal"); setShowMenu(false) }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                      <Target className="size-4" />{text.researchGoal}
                    </button>
                    <div className="my-1 border-t" />
                    {text.quickPrompts.map((item) => (
                      <button key={item.label} type="button" onClick={() => { setShowMenu(false); void runPrompt(item.prompt) }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                        <Sparkles className="size-4" />{item.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <textarea
                ref={composerRef}
                value={input}
                rows={1}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder={composerMode === "goal" ? text.goalPlaceholder : text.chatPlaceholder}
                className="max-h-32 min-h-11 min-w-0 flex-1 resize-none overflow-hidden rounded-xl border bg-background px-4 py-2.5 text-sm leading-6 outline-none transition-shadow focus:ring-2 focus:ring-primary/30"
                disabled={running}
              />
              {running ? (
                <Button type="button" variant="destructive" onClick={handleCancel} aria-label={text.stop} className="h-11 w-14 rounded-xl">
                  <Square className="size-4" />
                </Button>
              ) : (
                <Button type="submit" disabled={!input.trim()} aria-label={text.send} className="h-11 w-14 rounded-xl">
                  <Send className="size-4" />
                </Button>
              )}
            </div>
          </div>
        </form>
      </main>

      <ToolRail
        tools={tools}
        goal={goal}
        running={running}
        loading={sessionLoading}
        liveStatus={liveStatus}
        liveStatusLoading={liveStatusLoading}
        liveStatusUnavailable={liveStatusUnavailable}
        onRefreshLiveStatus={() => void refreshLiveStatus()}
        onHaltLive={() => void handleHaltLive()}
        text={text}
      />
    </div>
  )
}
