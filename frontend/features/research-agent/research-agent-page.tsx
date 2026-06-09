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
  type ResearchMessage,
  type ResearchSession
} from "@/libs/api/research-agent"

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
        desc: "调用 Vibe backtest 工具生成策略、运行回测并输出指标",
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
        desc: "启动 Vibe swarm 投资委员会/研究团队",
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
  "Vibe Agent Runtime",
  "47 个 Vibe 工具",
  "Research Goal",
  "Swarm",
  "Backtest",
  "Alpha Zoo",
  "文档/Web",
  "交易连接器",
  "Shadow Account"
]

const AGENT_COMPLETION_POLL_TIMEOUT_MS = 60 * 60_000

const QUICK_RESEARCH_PROMPTS = [
  { label: "跨市场回测", prompt: "Create a risk-parity style backtest for 000001.SZ, BTC-USDT, and AAPL from 2025-01-01 to 2026-06-01." },
  { label: "检查交易连接器", prompt: "List my trading connector profiles and check the selected connector. Do not place or modify orders." },
  { label: "智能体团队", prompt: "Run the investment committee swarm on A-share energy storage opportunities in research-only mode." },
  { label: "Shadow Account", prompt: "Use Shadow Account tools to scan a momentum breakout strategy and produce a research-only shadow report if possible." }
]

const TOOL_LABELS: Record<string, { title: string; desc: string }> = {
  load_skill: { title: "加载能力模块", desc: "加载 Vibe 工具或技能说明" },
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
  run_swarm: { title: "智能体团队", desc: "运行 Vibe swarm 多智能体研究团队" },
  trading_connections: { title: "交易连接器列表", desc: "列出可选交易连接器 profiles" },
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

function compactPreviewText(value: unknown) {
  return formatEventValue(value)
    .replace(/<skill\b[^>]*>/g, "")
    .replace(/<\/skill>/g, "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/[#*`>]+/g, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .slice(0, 220)
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

function jsonFragmentPreview(toolName: string, raw: string) {
  const result = {
    status: jsonFragmentStringField(raw, "status"),
    error: jsonFragmentStringField(raw, "error"),
    content: jsonFragmentStringField(raw, "content"),
    stdout: jsonFragmentStringField(raw, "stdout"),
    stderr: jsonFragmentStringField(raw, "stderr"),
    exit_code: jsonFragmentNumberField(raw, "exit_code") ?? jsonFragmentNumberField(raw, "exitcode")
  }

  if (toolName === "load_skill" && result.content) return skillPreview(result.content)
  if (toolName === "bash") return bashPreview(result)
  if (result.error) return `工具失败：${compactPreviewText(result.error)}`
  if (result.content) return compactPreviewText(result.content)
  if (result.stdout || result.stderr) return bashPreview(result)
  return compactPreviewText(raw.replace(/^\{+/, ""))
}

function skillPreview(content: string) {
  const name = content.match(/<skill\s+name=["']([^"']+)["']/)?.[1]
  const heading = content.match(/^#{1,6}\s+(.+)$/m)?.[1]
  const body = compactPreviewText(content)
  const prefix = name ? `已加载技能 ${name}` : "技能已加载"
  if (heading && body) return `${prefix}: ${heading} - ${body}`
  if (heading) return `${prefix}: ${heading}`
  return body ? `${prefix}: ${body}` : prefix
}

function bashPreview(result: Record<string, unknown>) {
  const exitCode = result.exit_code ?? result.code
  const stdout = compactPreviewText(result.stdout)
  const stderr = compactPreviewText(result.stderr || result.error)
  const failed = String(result.status || "") === "error" || (typeof exitCode === "number" && exitCode !== 0)
  const prefix = failed
    ? `命令失败${exitCode != null ? `（exit ${exitCode}）` : ""}`
    : "命令执行成功"
  if (stdout && stderr) return `${prefix}。输出：${stdout}。错误：${stderr}`
  if (stderr) return `${prefix}。错误：${stderr}`
  if (stdout) return `${prefix}。输出：${stdout}`
  return prefix
}

function evidencePreview(result: Record<string, unknown>) {
  const evidence = result.evidence
  if (evidence && typeof evidence === "object") {
    const text = compactPreviewText((evidence as Record<string, unknown>).text)
    if (text) return `证据已写入：${text}`
  }
  return result.status === "ok" ? "证据已写入 goal ledger" : compactPreviewText(result.error || result)
}

function goalStatusPreview(result: Record<string, unknown>) {
  const snapshot = result.snapshot
  if (snapshot && typeof snapshot === "object") {
    const goal = (snapshot as Record<string, unknown>).goal
    if (goal && typeof goal === "object") {
      const status = compactPreviewText((goal as Record<string, unknown>).status)
      const objective = compactPreviewText((goal as Record<string, unknown>).objective)
      if (status && objective) return `目标状态已更新为 ${status}：${objective}`
      if (status) return `目标状态已更新为 ${status}`
    }
  }
  return result.status === "ok" ? "目标状态已更新" : compactPreviewText(result.error || result)
}

function readableToolPreview(tool: ToolState) {
  if (!tool.preview) return ""
  const parsed = parseJsonPreview(tool.preview)
  if (!parsed) {
    const trimmed = tool.preview.trim()
    return trimmed.startsWith("{")
      ? jsonFragmentPreview(tool.name, trimmed)
      : compactPreviewText(tool.preview)
  }

  if (tool.name === "load_skill") {
    return skillPreview(formatEventValue(parsed.content || parsed.text || parsed.preview))
  }
  if (tool.name === "bash") return bashPreview(parsed)
  if (tool.name === "add_goal_evidence") return evidencePreview(parsed)
  if (tool.name === "update_research_goal_status") return goalStatusPreview(parsed)

  const content = parsed.content || parsed.text || parsed.summary || parsed.stdout || parsed.error || parsed.preview
  if (content) return compactPreviewText(content)
  if (parsed.status === "ok") return "工具执行完成"
  return compactPreviewText(parsed)
}

function normalizePersistedEvent(event: ResearchAgentEvent): ParsedResearchStreamEvent {
  return {
    event: event.event_type,
    data: event.payload || {},
    eventId: event.event_id
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
    .map((message) => ({
      id: message.message_id,
      type: message.role === "user" ? "user" : "answer",
      content: message.content,
      timestamp: messageTimestamp(message)
    }))
}

function finalAnswerFromEvents(events: ParsedResearchStreamEvent[]) {
  const completed = events.filter((event) => event.event === "message_completed")
  const last = completed.at(-1)
  return last ? eventContent(last.data) : ""
}

function toolsFromEvents(events: ParsedResearchStreamEvent[]): ToolState[] {
  const tools = new Map<string, ToolState>()
  for (const event of events) {
    const toolName = String(event.data.tool_name || event.data.tool || "")
    if (!toolName) continue
    if (event.event === "tool_started") {
      tools.set(toolName, { id: toolName, name: toolName, status: "running" })
    }
    if (event.event === "tool_completed" || event.event === "tool_failed") {
      tools.set(toolName, {
        id: toolName,
        name: toolName,
        status: event.event === "tool_completed" ? "ok" : "error",
        preview: previewFromEventData(event.data),
        artifactId: event.data.artifact_id ? String(event.data.artifact_id) : undefined,
        elapsedMs: typeof event.data.elapsed_ms === "number" ? event.data.elapsed_ms : undefined
      })
    }
  }
  return Array.from(tools.values())
}

function WelcomeScreen({ onExample }: { onExample: (prompt: string) => void }) {
  return (
    <div className="mx-auto flex max-w-4xl flex-col items-center px-4 py-10 text-center">
      <div className="mb-5 flex size-14 items-center justify-center rounded-2xl border bg-primary text-primary-foreground shadow-sm">
        <Bot className="size-7" />
      </div>
      <h1 className="text-2xl font-semibold tracking-normal text-foreground">Vibe Agent</h1>
      <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
        已迁入 Vibe-Trading 原始 Agent Runtime：会话、工具调用、Research Goal、Swarm、回测、文档/Web、交易连接器和 Shadow Account。
      </p>
      <div className="mt-4 flex max-w-2xl flex-wrap justify-center gap-2">
        {CAPABILITY_CHIPS.map((chip) => (
          <span key={chip} className="rounded-full border bg-background px-2.5 py-1 text-[11px] text-muted-foreground">
            {chip}
          </span>
        ))}
      </div>
      <div className="mt-7 grid w-full gap-3 md:grid-cols-2">
        {EXAMPLE_CATEGORIES.map((category) => {
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

function SessionLoadingView() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-10">
      <div className="flex items-center gap-3 rounded-lg border bg-background px-4 py-3 shadow-sm">
        <div className="flex size-9 items-center justify-center rounded-full bg-primary/10">
          <Loader2 className="size-4 animate-spin text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium">正在载入会话</p>
          <p className="mt-1 text-xs text-muted-foreground">正在恢复历史消息和执行步骤...</p>
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

function MessageBubble({ message }: { message: AgentMessage }) {
  if (message.type === "tool_call" || message.type === "tool_result") {
    const ok = message.status === "ok"
    const failed = message.status === "error"
    const label = TOOL_LABELS[message.tool || ""]?.title || message.tool || "tool"
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
            <span className="font-mono text-[11px] text-muted-foreground">{message.tool || "tool"}</span>
            <span className="rounded-full bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
              {message.status === "running" ? "运行中" : message.status === "error" ? "失败" : "完成"}
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
    <div className={`flex gap-3 ${isUser ? "justify-end" : ""}`}>
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

function brokerStatusText(status: LiveStatus["brokers"][number]) {
  if (status.halted) return "已暂停"
  if (status.runner?.alive) return "运行中"
  if (status.mandate && !status.mandate.expired) return "已授权"
  if (status.auth.oauth_token_present) return "已连接"
  return "未连接"
}

function brokerStatusTone(status: LiveStatus["brokers"][number]) {
  if (status.halted) return "border-destructive/40 bg-destructive/5 text-destructive"
  if (status.runner?.alive) return "border-emerald-500/40 bg-emerald-500/5 text-emerald-700"
  if (status.mandate && !status.mandate.expired) return "border-sky-500/40 bg-sky-500/5 text-sky-700"
  return "border-muted bg-muted/30 text-muted-foreground"
}

function LiveStatusPanel({
  status,
  loading,
  unavailable,
  onRefresh,
  onHalt
}: {
  status: LiveStatus | null
  loading: boolean
  unavailable: boolean
  onRefresh: () => void
  onHalt: () => void
}) {
  const brokers = status?.brokers || []
  const hasActiveRuntime = Boolean(status?.global_halted || brokers.some((item) => item.runner?.alive || item.mandate || item.halted))

  return (
    <section className="rounded-lg border bg-background p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">交易连接器运行</h2>
        <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onRefresh}>
          {loading ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Activity className="mr-1 size-3" />}
          刷新
        </Button>
      </div>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        来自 Vibe Runtime 的 <span className="font-mono">/live/status</span>，展示 broker 授权、runner 和 kill switch 状态。
      </p>
      {unavailable ? (
        <p className="mt-3 rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
          当前后端未返回 live runtime 状态。
        </p>
      ) : (
        <div className="mt-3 space-y-2">
          <div className={`rounded-md border px-3 py-2 text-xs ${status?.global_halted ? "border-destructive/40 bg-destructive/5 text-destructive" : "bg-muted/20 text-muted-foreground"}`}>
            全局 Kill Switch：{status?.global_halted ? "已触发" : "未触发"}
          </div>
          {brokers.length === 0 ? (
            <p className="rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
              暂无 broker 状态。可以先运行“检查交易连接器”。
            </p>
          ) : brokers.map((broker) => (
            <div key={broker.auth.broker} className={`rounded-md border px-3 py-2 text-xs ${brokerStatusTone(broker)}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium uppercase">{broker.auth.broker}</span>
                <span>{brokerStatusText(broker)}</span>
              </div>
              <div className="mt-1 grid grid-cols-2 gap-1 text-[11px] opacity-80">
                <span>OAuth: {broker.auth.oauth_token_present ? "有" : "无"}</span>
                <span>Runner: {broker.runner?.alive ? "alive" : "idle"}</span>
                <span>Mandate: {broker.mandate && !broker.mandate.expired ? "active" : "none"}</span>
                <span>Halt: {broker.halted ? "yes" : "no"}</span>
              </div>
            </div>
          ))}
          {hasActiveRuntime && (
            <Button type="button" variant="destructive" size="sm" className="w-full justify-center" onClick={onHalt}>
              <Square className="mr-2 size-4" />全局暂停 live runtime
            </Button>
          )}
        </div>
      )}
    </section>
  )
}

function ToolRail({
  tools,
  running,
  loading,
  liveStatus,
  liveStatusLoading,
  liveStatusUnavailable,
  onRefreshLiveStatus,
  onHaltLive
}: {
  tools: ToolState[]
  running: boolean
  loading: boolean
  liveStatus: LiveStatus | null
  liveStatusLoading: boolean
  liveStatusUnavailable: boolean
  onRefreshLiveStatus: () => void
  onHaltLive: () => void
}) {
  return (
    <aside className="hidden h-full w-[360px] shrink-0 overflow-y-auto border-l bg-muted/10 xl:block">
      <div className="grid min-w-0 gap-4 p-4">
        <section className="min-w-0 rounded-lg border bg-background p-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">执行步骤</h2>
            {(running || loading) && <Loader2 className="size-4 animate-spin text-primary" />}
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            这里展示的是本次 Vibe Agent 调用了哪些后端工具。
          </p>
          <div className="mt-3 space-y-2">
            {loading ? (
              <div className="space-y-2" aria-label="正在载入执行步骤">
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
                等待回测、Alpha、矩阵、文档/Web、Swarm、连接器或 Shadow 工具步骤。
              </p>
            ) : (
              tools.map((tool) => {
                const label = TOOL_LABELS[tool.name]
                const preview = readableToolPreview(tool)
                const statusClass = tool.status === "error"
                  ? "bg-destructive/10 text-destructive"
                  : tool.status === "running"
                    ? "bg-primary/10 text-primary"
                    : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                return (
                  <div key={tool.id} className="min-w-0 rounded-md border bg-background px-3 py-2 shadow-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate text-xs font-medium">{label?.title || tool.name}</span>
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${statusClass}`}>
                        {tool.status === "running" ? "运行中" : tool.status === "error" ? "失败" : "完成"}
                      </span>
                    </div>
                    <p className="mt-1 break-words text-[11px] leading-4 text-muted-foreground [overflow-wrap:anywhere]">{label?.desc || tool.name}</p>
                    {preview && <p className="mt-1 line-clamp-3 break-words text-[11px] leading-4 text-foreground/75 [overflow-wrap:anywhere]">{preview}</p>}
                    {typeof tool.elapsedMs === "number" && (
                      <p className="mt-1 text-[10px] text-muted-foreground">{(tool.elapsedMs / 1000).toFixed(1)}s</p>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </section>

        <LiveStatusPanel
          status={liveStatus}
          loading={liveStatusLoading}
          unavailable={liveStatusUnavailable}
          onRefresh={onRefreshLiveStatus}
          onHalt={onHaltLive}
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
  onDelete
}: {
  sessions: ResearchSession[]
  activeSessionId: string | null
  running: boolean
  onNew: () => void
  onSelect: (sessionId: string) => void
  onRename: (sessionId: string, title: string) => Promise<void>
  onDelete: (sessionId: string) => Promise<void>
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
          <Plus className="mr-2 size-4" />新会话
        </Button>
        <div className="min-h-0 overflow-auto">
          <h2 className="mb-2 text-xs font-medium uppercase text-muted-foreground">Sessions</h2>
          <div className="space-y-1">
            {sessions.length === 0 ? (
              <p className="rounded-lg border border-dashed px-3 py-4 text-xs text-muted-foreground">还没有 Agent 会话。</p>
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
                        <button type="button" className="rounded p-1 hover:bg-background/20" onClick={() => void saveRename(session.session_id)} aria-label="保存重命名">
                          <Check className="size-3" />
                        </button>
                        <button type="button" className="rounded p-1 hover:bg-background/20" onClick={() => setEditingId(null)} aria-label="取消重命名">
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
                            aria-label="重命名会话"
                          >
                            <Pencil className="size-3" />
                          </button>
                          <button
                            type="button"
                            className="rounded p-1 hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => void onDelete(session.session_id)}
                            aria-label="删除会话"
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
            <Users className="size-4" />当前 Agent 范围
          </div>
          当前页面直接调用后端挂载的 Vibe Runtime，不再使用简化 Agent stub。
        </div>
      </div>
    </aside>
  )
}

export function ResearchAgentPage() {
  const [sessions, setSessions] = useState<ResearchSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [tools, setTools] = useState<ToolState[]>([])
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
  const streamStopRef = useRef<(() => void) | null>(null)
  const completionPollRef = useRef<number | null>(null)
  const lastEventIdRef = useRef(0)
  const streamingAnswerIdRef = useRef<string | null>(null)
  const runFinishedRef = useRef(false)
  const sessionLoadSeqRef = useRef(0)

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
    void Promise.all([
      researchAgentApi.listMessages(activeSessionId),
      researchAgentApi.listEvents(activeSessionId)
    ]).then(([messageResponse, eventResponse]) => {
      if (sessionLoadSeqRef.current !== loadSeq) return
      const rawEvents = eventResponse.data || []
      const persistedEvents = rawEvents.map(normalizePersistedEvent)
      lastEventIdRef.current = Math.max(0, ...rawEvents.map((event) => Number(event.event_id || 0)))
      const restoredMessages = messagesFromApi(messageResponse.data || [])
      const answer = finalAnswerFromEvents(persistedEvents)
      const nextMessages = answer && !restoredMessages.some((message) => message.type === "answer" && message.content === answer)
        ? [...restoredMessages, { id: nowId("answer"), type: "answer" as const, content: answer, timestamp: Date.now() }]
        : restoredMessages
      setMessages(nextMessages)
      setTools(toolsFromEvents(persistedEvents))
      requestAnimationFrame(scrollToBottom)
    }).catch(() => {
      if (sessionLoadSeqRef.current !== loadSeq) return
      setMessages([])
      setTools([])
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
    if (cancelRequested) return "取消中"
    if (running) return "运行中"
    return "就绪"
  }, [cancelRequested, running])

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
      message.role === "assistant" && message.linked_attempt_id === attemptId
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

  function startCompletionPolling(sessionId: string, attemptId?: string) {
    stopCompletionPolling()
    if (!attemptId || runFinishedRef.current) return
    const startedAt = Date.now()
    void refreshCompletedAttemptFromStore(sessionId, attemptId).catch(() => undefined)
    completionPollRef.current = window.setInterval(() => {
      if (Date.now() - startedAt > AGENT_COMPLETION_POLL_TIMEOUT_MS) {
        stopCompletionPolling()
        runFinishedRef.current = true
        setRunning(false)
        appendStreamMessage({
          id: nowId("error"),
          type: "error",
          content: "Agent 运行超过 60 分钟仍未收到完成事件，请刷新会话或检查后端日志。",
          timestamp: Date.now()
        })
        return
      }
      void refreshCompletedAttemptFromStore(sessionId, attemptId).catch(() => undefined)
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
    if (item.eventId && Number.isFinite(item.eventId)) {
      lastEventIdRef.current = Math.max(lastEventIdRef.current, item.eventId)
    }
    if (item.event === "heartbeat") return
    if (item.event === "assistant_delta") {
      upsertStreamingAnswer(eventContent(item.data))
      return
    }
    if (item.event === "tool_started") {
      const toolName = String(item.data.tool_name || item.data.tool || "tool")
      upsertTool({ id: toolName, name: toolName, status: "running" })
      appendStreamMessage({ id: nowId("tool-call"), type: "tool_call", content: "", tool: toolName, status: "running", timestamp: Date.now() })
      return
    }
    if (item.event === "tool_completed" || item.event === "tool_failed") {
      const toolName = String(item.data.tool_name || item.data.tool || "tool")
      const status = item.event === "tool_completed" ? "ok" : "error"
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
    if (item.event === "task_failed") {
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      setRunning(false)
      setCancelRequested(false)
      appendStreamMessage({ id: nowId("error"), type: "error", content: eventContent(item.data) || String(item.data.error || "Agent execution failed"), timestamp: Date.now() })
      return
    }
    if (item.event === "task_completed") {
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
      prompt = [
        "Start working on this research goal now.",
        "Keep it research-only, use available tools when evidence is needed, add concrete evidence to the goal ledger, and keep going until the goal is complete, blocked, waiting for user input, or budget-limited.",
        "",
        `Goal: ${raw}`
      ].join("\n")
    }
    return prompt
  }

  async function runPrompt(raw: string) {
    const trimmed = raw.trim()
    if (!trimmed || running) return
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
      stopStream()
      streamStopRef.current = researchAgentApi.subscribeEvents(sessionId, { onEvent: handleStreamEvent, onError: () => undefined }, lastEventIdRef.current)
      const appendResponse = await researchAgentApi.appendMessage(sessionId, { role: "user", content: finalPrompt, metadata: { source: "vibe-agent-page" } })
      startCompletionPolling(sessionId, appendResponse.data.attempt_id)
    } catch (error) {
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      setMessages((current) => [...current, { id: nowId("error"), type: "error", content: error instanceof Error ? error.message : "发送消息失败，请重试。", timestamp: Date.now() }])
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
    lastEventIdRef.current = 0
    setMessages([])
    setTools([])
    setInput("")
    setComposerMode("chat")
  }

  function handleSelectSession(sessionId: string) {
    if (running) return
    stopStream()
    stopCompletionPolling()
    runFinishedRef.current = true
    lastEventIdRef.current = 0
    setSessionLoading(true)
    setMessages([])
    setTools([])
    setActiveSessionId(sessionId)
  }

  async function handleRenameSession(sessionId: string, title: string) {
    const response = await researchAgentApi.updateSession(sessionId, { title })
    setSessions((current) => current.map((session) => (
      session.session_id === sessionId ? response.data : session
    )))
  }

  async function handleDeleteSession(sessionId: string) {
    if (!window.confirm("删除后会清理这个会话的消息、事件和产物。确定删除吗？")) return
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
        content: "已请求后端取消当前 Vibe Agent attempt。",
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
    if (!messages.length) return
    const lines = [`# Agent Chat Export`, ``, `Export time: ${new Date().toLocaleString()}`, ``]
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
              已接入 Vibe-Trading 原始 Agent Runtime，并运行在当前后端进程内。
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleNewSession}>
              <Plus className="mr-2 size-4" />新会话
            </Button>
            {messages.length > 0 && (
              <Button variant="outline" size="sm" onClick={handleExport}>
                <Download className="mr-2 size-4" />导出聊天
              </Button>
            )}
          </div>
        </header>

        <div ref={listRef} onScroll={onScroll} className="relative min-h-0 overflow-auto p-5">
          <div className="w-full space-y-4">
            {sessionLoading ? (
              <SessionLoadingView />
            ) : messages.length === 0 ? (
              <WelcomeScreen onExample={runPrompt} />
            ) : (
              messages.map((message) => <MessageBubble key={message.id} message={message} />)
            )}
            {running && (
              <div className="flex gap-3">
                <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-full border bg-background">
                  <Bot className="size-4 text-primary" />
                </div>
                <div className="flex min-w-0 flex-1 items-center gap-2 pt-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin text-primary" />
                  <span>智能体正在工作...</span>
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
              <ArrowDown className="size-3" />新消息
            </button>
          )}
        </div>

        <form onSubmit={handleSubmit} className="min-w-0 border-t bg-background/90 p-4">
          <div className="w-full min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              {composerMode === "goal" && (
                <span className="inline-flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                  <Target className="size-3" />新研究目标
                  <button type="button" onClick={() => setComposerMode("chat")}><X className="size-3" /></button>
                </span>
              )}
            </div>
            <div className="flex min-w-0 items-center gap-2">
              <div ref={menuRef} className="relative">
                <Button type="button" variant="outline" size="icon" disabled={running} onClick={() => setShowMenu((open) => !open)} aria-label="更多选项" className="size-11 rounded-xl">
                  <Plus className="size-4" />
                </Button>
                {showMenu && (
                  <div className="absolute bottom-full left-0 z-20 mb-2 w-56 rounded-lg border bg-background py-1 shadow-lg">
                    <button type="button" onClick={() => { setComposerMode("goal"); setShowMenu(false) }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                      <Target className="size-4" />研究目标
                    </button>
                    <div className="my-1 border-t" />
                    {QUICK_RESEARCH_PROMPTS.map((item) => (
                      <button key={item.label} type="button" onClick={() => { setShowMenu(false); void runPrompt(item.prompt) }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                        <Sparkles className="size-4" />{item.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <textarea
                value={input}
                rows={1}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder={composerMode === "goal" ? "描述要绑定到当前会话的研究目标" : "例如：Run a backtest, check connector status, or analyze A 股储能板块"}
                className="h-11 max-h-32 min-h-11 min-w-0 flex-1 resize-none rounded-xl border bg-background px-4 py-2.5 text-sm leading-6 outline-none transition-shadow focus:ring-2 focus:ring-primary/30"
                disabled={running}
              />
              {running ? (
                <Button type="button" variant="destructive" onClick={handleCancel} aria-label="停止生成" className="h-11 w-14 rounded-xl">
                  <Square className="size-4" />
                </Button>
              ) : (
                <Button type="submit" disabled={!input.trim()} aria-label="发送" className="h-11 w-14 rounded-xl">
                  <Send className="size-4" />
                </Button>
              )}
            </div>
          </div>
        </form>
      </main>

      <ToolRail
        tools={tools}
        running={running}
        loading={sessionLoading}
        liveStatus={liveStatus}
        liveStatusLoading={liveStatusLoading}
        liveStatusUnavailable={liveStatusUnavailable}
        onRefreshLiveStatus={() => void refreshLiveStatus()}
        onHaltLive={() => void handleHaltLive()}
      />
    </div>
  )
}
