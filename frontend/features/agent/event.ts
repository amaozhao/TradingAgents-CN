import type { BatchPayload, StockPayload } from "@/features/research/payload"
import type { ParsedResearchStreamEvent, ResearchAgentEvent, ResearchAttempt, ResearchGoal, ResearchMessage } from "@/libs/api/research-agent"
import type { AppLanguage } from "@/stores/app-store"

import { AGENT_TEXT } from "./text"
import type { AgentMessage, ToolState } from "./types"

export function stockStageId(data: Record<string, unknown>) {
  const toolName = String(data.tool_name || data.tool || "stock_analysis")
  const stage = String(data.stage || "stage")
  return `${toolName}:${stage}`
}

export function stockStageTitle(data: Record<string, unknown>) {
  return stringField(data.title) || stringField(data.stage)
}

export function stockPayloadFromMetadata(metadata?: Record<string, unknown>) {
  if (metadata?.tool_name !== "stock_analysis") return null
  const value = metadata.tool_arguments
  if (!value || typeof value !== "object") return null
  const payload = value as Partial<StockPayload>
  if (payload.mode !== "single" || !payload.symbol || !payload.market_type) return null
  return payload as StockPayload
}

export function batchPayloadFromMetadata(metadata?: Record<string, unknown>) {
  if (metadata?.tool_name !== "batch_stock_analysis") return null
  const value = metadata.tool_arguments
  if (!value || typeof value !== "object") return null
  const payload = value as Partial<BatchPayload>
  if (!payload.title || !Array.isArray(payload.symbols) || payload.symbols.length === 0) return null
  return payload as BatchPayload
}

export function initialStockWorkflowTools(value: unknown): ToolState[] {
  if (!value || typeof value !== "object") return []
  const payload = value as Partial<StockPayload>
  if (payload.mode !== "single") return []
  return [{
    id: "stock_analysis:validate_input",
    name: "stock_analysis",
    title: "参数校验",
    status: "running",
    preview: "正在提交并校验个股分析参数。"
  }]
}

export function initialBatchWorkflowTools(value: unknown): ToolState[] {
  if (!value || typeof value !== "object") return []
  const payload = value as Partial<BatchPayload>
  if (!Array.isArray(payload.symbols) || payload.symbols.length === 0) return []
  return [{
    id: "batch_stock_analysis:submit",
    name: "batch_stock_analysis",
    title: "提交批量分析",
    status: "running",
    preview: "正在提交并校验批量分析参数。"
  }]
}

export function nowId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function toolMessageId(toolName: string) {
  return `tool-${toolName || "tool"}`
}

export function eventContent(data: Record<string, unknown>) {
  const direct = data.content || data.text || data.delta || data.summary
  if (direct) return String(direct)
  const result = data.result
  if (result && typeof result === "object") {
    const nested = result as Record<string, unknown>
    return String(nested.content || nested.text || nested.delta || nested.summary || "")
  }
  return ""
}

export function humanizeAgentError(raw: string) {
  const message = raw.trim()
  if (!message) return ""
  if (/ConnectTimeout|ReadTimeout|TimeoutException|TimeoutError/i.test(message)) {
    return `外部模型或网络服务请求超时：${message}。任务没有拿到完整结果，请检查代理/API 服务或稍后重试。`
  }
  return message
}

export function eventFailureContent(data: Record<string, unknown>) {
  return humanizeAgentError(eventContent(data) || String(data.error || ""))
}

export function eventToolStatus(event: ParsedResearchStreamEvent): ToolState["status"] {
  if (event.event === "tool_failed") return "error"
  if (event.event === "stock_analysis.stage") {
    const stageStatus = String(event.data.status || "")
    if (stageStatus === "failed") return "error"
    if (stageStatus === "skipped") return "skipped"
    if (stageStatus === "running" || stageStatus === "pending") return "running"
    return "ok"
  }
  const result = event.data.result
  const resultStatus = result && typeof result === "object" ? (result as Record<string, unknown>).status : ""
  const status = String(event.data.status || resultStatus || "")
  if (status === "error" || status === "failed") return "error"
  if (status === "queued" || status === "pending" || status === "processing" || status === "running") return "running"
  if (
    status === "degraded"
    || status === "warning"
    || status === "limited"
    || status === "stale_goal"
    || status === "config_required"
  ) return "warning"
  return "ok"
}

export function statusLabel(status: ToolState["status"], text: typeof AGENT_TEXT[AppLanguage]) {
  if (status === "running") return text.running
  if (status === "error") return text.failed
  if (status === "skipped") return text.skipped
  if (status === "warning") return text.warning
  return text.completed
}

export function formatEventValue(value: unknown) {
  if (value == null) return ""
  if (typeof value === "string") return value === "[object Object]" ? "" : value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function previewFromEventData(data: Record<string, unknown>) {
  const stage = formatEventValue(data.stage)
  const message = formatEventValue(data.message)
  const progress = typeof data.progress === "number" ? `${data.progress}%` : ""
  if (stage || message || progress) {
    return [stage, progress, message].filter(Boolean).join(" · ")
  }
  for (const key of ["preview", "result", "error", "content", "text", "summary"] as const) {
    const formatted = formatEventValue(data[key])
    if (formatted) return formatted
  }
  return ""
}

export function stringField(value: unknown) {
  return value == null || value === "" ? undefined : String(value)
}

export function resultData(data: Record<string, unknown>) {
  const result = data.result
  return result && typeof result === "object" ? result as Record<string, unknown> : {}
}

export function stockLinksFromEventData(data: Record<string, unknown>) {
  const result = resultData(data)
  return {
    taskId: stringField(data.task_id) || stringField(result.task_id) || stringField(result.job_id),
    reportUrl: stringField(data.report_url) || stringField(result.report_url)
  }
}

export function textValue(value: unknown) {
  return typeof value === "string" ? value.trim() : ""
}

export function createGoalDraft(raw: string, text: typeof AGENT_TEXT[AppLanguage]) {
  const lines = raw.split("\n").map((line) => line.trim()).filter(Boolean)
  const title = (lines[0] || raw).slice(0, 120) || text.researchGoal
  return {
    title,
    description: raw,
    criteria: text.goalCriteria
  }
}

export function mergeGoalEvent(current: ResearchGoal | null, eventName: string, data: Record<string, unknown>): ResearchGoal | null {
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

export function parseJsonPreview(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : null
  } catch {
    return null
  }
}

export function compactPreviewText(value: unknown, maxLength: number | null = 220) {
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

export function decodeJsonFragment(value: string) {
  try {
    return JSON.parse(`"${value}"`) as string
  } catch {
    return value
      .replace(/\\"/g, "\"")
      .replace(/\\n/g, "\n")
      .replace(/\\t/g, " ")
  }
}

export function jsonFragmentStringField(raw: string, key: string) {
  const match = raw.match(new RegExp(`"${key}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)`))
  return match ? decodeJsonFragment(match[1]) : ""
}

export function jsonFragmentNumberField(raw: string, key: string) {
  const match = raw.match(new RegExp(`"${key}"\\s*:\\s*(-?\\d+(?:\\.\\d+)?)`))
  return match ? Number(match[1]) : undefined
}

export function jsonFragmentPreview(toolName: string, raw: string, maxLength: number | null = 220) {
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

export function skillPreview(content: string, maxLength: number | null = 220) {
  const name = content.match(/<skill\s+name=["']([^"']+)["']/)?.[1]
  const heading = content.match(/^#{1,6}\s+(.+)$/m)?.[1]
  const body = compactPreviewText(content, maxLength)
  const prefix = name ? `已加载技能 ${name}` : "技能已加载"
  if (heading && body) return `${prefix}: ${heading} - ${body}`
  if (heading) return `${prefix}: ${heading}`
  return body ? `${prefix}: ${body}` : prefix
}

export function bashPreview(result: Record<string, unknown>, maxLength: number | null = 220) {
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

export function evidencePreview(result: Record<string, unknown>, maxLength: number | null = 220) {
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

export function goalStatusPreview(result: Record<string, unknown>, maxLength: number | null = 220) {
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

export function configRequiredPreview(toolName: string, result: Record<string, unknown>, maxLength: number | null = 220) {
  const instruction = compactPreviewText(result.instruction, maxLength)
  if (instruction) return `需要补充数据：${instruction}`

  const knownToolMessage = (() => {
    if (toolName === "analyze_trade_journal") {
      return "请先上传交易日志文件、粘贴交易日志文本，或提供当前用户可访问的 artifact_id/file_id。缺少这些用户侧输入时不会生成模拟交易日志。"
    }
    if (toolName === "run_shadow_backtest") {
      return "请先上传或粘贴交易日志，或明确提供 returns / trades[].pnl；缺少真实收益序列时不会生成模拟回测数据。"
    }
    if (toolName.startsWith("trading_")) {
      return "请先连接交易器并完成 OAuth 授权；连接器未就绪时不会读取账户、订单或持仓数据。"
    }
    return ""
  })()
  if (knownToolMessage) return `需要补充数据：${knownToolMessage}`

  const reason = compactPreviewText(result.reason || result.message || result.error, maxLength)
  return `需要补充数据：${reason || "缺少该工具必需的用户数据或配置，请先补充后再运行。"}`
}

export function stockAnalysisPreview(toolName: string, result: Record<string, unknown>, maxLength: number | null = 220) {
  const taskId = compactPreviewText(result.task_id, maxLength)
  if (toolName === "single_stock_analysis") {
    const symbol = compactPreviewText(result.symbol || result.stock_code, maxLength)
    const depth = compactPreviewText(result.research_depth, maxLength)
    const task = taskId ? `任务 ${taskId}` : "任务"
    const target = symbol ? `${symbol}${depth ? `（${depth}）` : ""}` : "个股分析"
    return `${target} ${task}已提交到分析队列。`
  }
  if (toolName === "stock_analysis_status") {
    const progress = typeof result.progress === "number" ? `${result.progress}%` : ""
    const step = compactPreviewText(result.current_step || result.message || result.status, maxLength)
    const task = taskId ? `任务 ${taskId}` : "个股分析任务"
    if (progress && step) return `${task}进度 ${progress}：${step}`
    if (step) return `${task}状态：${step}`
    return `${task}状态已读取。`
  }
  if (toolName === "stock_analysis_report") {
    const summary = compactPreviewText(result.summary || result.recommendation, maxLength)
    if (summary) return `个股分析报告已生成：${summary}`
    return "个股分析报告已生成。"
  }
  return ""
}

export function readableToolPreview(tool: ToolState, maxLength: number | null = 220) {
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
  if (
    tool.name === "stock_analysis"
    || tool.name === "single_stock_analysis"
    || tool.name === "stock_analysis_status"
    || tool.name === "stock_analysis_report"
  ) {
    const preview = stockAnalysisPreview(tool.name, parsed, maxLength)
    if (preview) return preview
  }
  if (parsed.status === "config_required") return configRequiredPreview(tool.name, parsed, maxLength)
  if (parsed.status === "degraded") {
    const history = parsed.history && typeof parsed.history === "object"
      ? parsed.history as Record<string, unknown>
      : null
    const reason = compactPreviewText(
      parsed.error || parsed.message || parsed.reason || history?.reason || parsed.error_type,
      maxLength
    )
    return reason ? `数据受限：${reason}` : "数据或外部服务受限，Agent 已使用可用证据继续。"
  }

  const content = parsed.content || parsed.text || parsed.summary || parsed.stdout || parsed.error || parsed.preview
  if (content) return compactPreviewText(content, maxLength)
  if (parsed.status === "ok") return "工具执行完成"
  return compactPreviewText(parsed, maxLength)
}

export function normalizePersistedEvent(event: ResearchAgentEvent): ParsedResearchStreamEvent {
  return {
    event: event.event_type,
    data: event.payload || {},
    eventId: event.event_id == null ? undefined : String(event.event_id)
  }
}

export function messageTimestamp(message: ResearchMessage) {
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

export function messagesFromApi(messages: ResearchMessage[]): AgentMessage[] {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .filter((message) => message.role !== "assistant" || message.content.trim().length > 0)
    .map((message) => ({
      id: message.message_id,
      type: message.role === "user" ? "user" : "answer",
      content: message.content,
      timestamp: messageTimestamp(message),
      metadata: message.metadata
    }))
}

export function finalAnswerFromEvents(events: ParsedResearchStreamEvent[]) {
  const completed = events.filter((event) => event.event === "message_completed" || event.event === "attempt.completed")
  for (const event of completed.reverse()) {
    const content = eventContent(event.data)
    if (content) return content
  }
  return ""
}

export function attemptResultContent(attempt: ResearchAttempt) {
  const result = attempt.result
  if (!result || typeof result !== "object") return ""
  const content = result.content
  return typeof content === "string" ? content.trim() : ""
}

export function attemptTimestamp(attempt: ResearchAttempt) {
  const timestamp = attempt.started_at || attempt.created_at
  if (!timestamp) return 0
  const parsed = new Date(timestamp).getTime()
  return Number.isFinite(parsed) ? parsed : 0
}

export function latestActiveAttempt(attempts: ResearchAttempt[]) {
  return attempts
    .filter((attempt) => attempt.status === "queued" || attempt.status === "running")
    .sort((left, right) => attemptTimestamp(left) - attemptTimestamp(right))
    .at(-1)
}

export function latestAttempt(attempts: ResearchAttempt[]) {
  return [...attempts]
    .sort((left, right) => attemptTimestamp(left) - attemptTimestamp(right))
    .at(-1)
}

export function failureMessageFromEvents(events: ParsedResearchStreamEvent[]) {
  const failed = events.filter((event) => event.event === "task_failed" || event.event === "attempt.failed" || event.event === "job_failed")
  for (const event of failed.reverse()) {
    const content = eventFailureContent(event.data)
    if (content) return content
  }
  return ""
}

export function attemptScopedEvents(
  events: ParsedResearchStreamEvent[],
  attemptId?: string
) {
  if (!attemptId) return events
  const startIndex = events.findIndex((event) => (
    String(event.data.attempt_id || "") === attemptId &&
    (event.event === "attempt.created" || event.event === "attempt.started")
  ))
  if (startIndex >= 0) {
    const endIndex = events.findIndex((event, index) => (
      index > startIndex &&
      String(event.data.attempt_id || "") !== attemptId &&
      (event.event === "attempt.created" || event.event === "attempt.started")
    ))
    return events.slice(startIndex, endIndex >= 0 ? endIndex : undefined)
  }
  return events.filter((event) => String(event.data.attempt_id || "") === attemptId)
}

export function toolsFromEvents(events: ParsedResearchStreamEvent[], attemptId?: string): ToolState[] {
  const tools = new Map<string, ToolState>()
  for (const event of attemptScopedEvents(events, attemptId)) {
    const toolName = String(event.data.tool_name || event.data.tool || "")
    if (!toolName) continue
    if (event.event === "tool_started" || event.event === "tool_call") {
      const links = stockLinksFromEventData(event.data)
      tools.set(toolName, {
        id: toolName,
        name: toolName,
        status: "running",
        preview: previewFromEventData(event.data),
        taskId: links.taskId,
        reportUrl: links.reportUrl
      })
    }
    if (event.event === "tool_progress" || event.event === "tool_heartbeat") {
      const existing = tools.get(toolName)
      const links = stockLinksFromEventData(event.data)
      tools.set(toolName, {
        id: toolName,
        name: toolName,
        status: "running",
        preview: previewFromEventData(event.data) || existing?.preview,
        artifactId: existing?.artifactId,
        taskId: links.taskId || existing?.taskId,
        reportUrl: links.reportUrl || existing?.reportUrl,
        elapsedMs: existing?.elapsedMs
      })
    }
    if (event.event === "stock_analysis.stage") {
      const id = stockStageId(event.data)
      const existing = tools.get(id)
      const links = stockLinksFromEventData(event.data)
      tools.set(id, {
        id,
        name: toolName,
        title: stockStageTitle(event.data),
        status: eventToolStatus(event),
        preview: previewFromEventData(event.data) || existing?.preview,
        artifactId: event.data.artifact_id ? String(event.data.artifact_id) : existing?.artifactId,
        taskId: links.taskId || existing?.taskId,
        reportUrl: links.reportUrl || existing?.reportUrl,
        elapsedMs: existing?.elapsedMs
      })
    }
    if (event.event === "tool_completed" || event.event === "tool_failed" || event.event === "tool_result") {
      const status = eventToolStatus(event)
      const existing = tools.get(toolName)
      const links = stockLinksFromEventData(event.data)
      tools.set(toolName, {
        id: toolName,
        name: toolName,
        status,
        preview: previewFromEventData(event.data),
        artifactId: event.data.artifact_id ? String(event.data.artifact_id) : undefined,
        taskId: links.taskId || existing?.taskId,
        reportUrl: links.reportUrl || existing?.reportUrl,
        elapsedMs: typeof event.data.elapsed_ms === "number" ? event.data.elapsed_ms : undefined
      })
    }
  }
  return Array.from(tools.values())
}
