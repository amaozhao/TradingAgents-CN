"use client"

import { useState } from "react"
import { Activity, Bot, Check, CheckCircle2, ChevronDown, CircleDot, CircleSlash, Loader2, OctagonX, Pencil, PlugZap, Plus, Power, ShieldCheck, Square, Target, Trash2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { MarkdownRenderer } from "@/features/learning/markdown-renderer"
import type { LiveStatus, ResearchGoal, ResearchSession } from "@/libs/api/research-agent"
import type { AppLanguage } from "@/stores/app-store"

import { readableToolPreview, statusLabel } from "./event"
import { AGENT_TEXT } from "./text"
import type { AgentMessage, ToolState } from "./types"

export function WelcomeScreen({
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
      <h1 className="text-2xl font-semibold tracking-normal text-foreground">{text.pageTitle}</h1>
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

export function SessionLoadingView({ text }: { text: typeof AGENT_TEXT[AppLanguage] }) {
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

export function MessageBubble({
  message,
  text
}: {
  message: AgentMessage
  text: typeof AGENT_TEXT[AppLanguage]
}) {
  if (message.type === "tool_call" || message.type === "tool_result") {
    const ok = message.status === "ok"
    const failed = message.status === "error"
    const warning = message.status === "warning"
    const skipped = message.status === "skipped"
    const label = text.toolLabels[message.tool || ""]?.title || message.tool || text.toolFallback
    return (
      <div className="flex gap-3">
        <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-full border bg-muted">
          {message.type === "tool_call" && message.status === "running" ? (
            <Loader2 className="size-4 animate-spin text-primary" />
          ) : (
            <CheckCircle2 className={`size-4 ${failed ? "text-destructive" : warning ? "text-amber-600" : skipped ? "text-muted-foreground" : ok ? "text-emerald-600" : "text-muted-foreground"}`} />
          )}
        </div>
        <div className="min-w-0 flex-1 rounded-lg border bg-muted/20 px-3 py-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium">{label}</span>
            <span className="font-mono text-[11px] text-muted-foreground">{message.tool || text.toolFallback}</span>
            <span className="rounded-full bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
              {statusLabel(message.status || "ok", text)}
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
          "min-w-0 max-w-[82%] rounded-xl px-4 py-3 text-sm leading-6",
          isUser ? "bg-primary text-primary-foreground" : "border bg-background",
          isError ? "border-destructive/40 bg-destructive/5 text-destructive" : ""
        ].join(" ")}
      >
        {isUser || isError || message.type === "system" ? (
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <MarkdownRenderer
            content={message.content}
            className="min-w-0 max-w-full text-sm leading-7 [&_h1:first-child]:mt-0 [&_h2:first-child]:mt-0 [&_h3:first-child]:mt-0 [&_table]:text-xs [&_td]:align-top [&_th]:whitespace-nowrap"
          />
        )}
      </div>
    </div>
  )
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

function formatRelative(value: string | number | null | undefined, text: typeof AGENT_TEXT[AppLanguage]) {
  if (value == null || value === "") return text.liveNever
  const timestamp = typeof value === "number"
    ? (value < 1_000_000_000_000 ? value * 1000 : value)
    : new Date(value).getTime()
  if (!Number.isFinite(timestamp)) return text.liveUnknown
  const delta = Math.round((Date.now() - timestamp) / 1000)
  if (delta < 0) return text.liveJustNow
  if (delta < 60) return `${delta}s ${text.liveAgo}`
  if (delta < 3600) return `${Math.floor(delta / 60)}m ${text.liveAgo}`
  if (delta < 86_400) return `${Math.floor(delta / 3600)}h ${text.liveAgo}`
  return `${Math.floor(delta / 86_400)}d ${text.liveAgo}`
}

function formatLimit(value: number | undefined) {
  if (value == null || !Number.isFinite(value)) return ""
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`
}

function summarizeMandate(mandate: LiveStatus["brokers"][number]["mandate"], text: typeof AGENT_TEXT[AppLanguage]) {
  const limits = mandate && "limits" in mandate ? mandate.limits as Record<string, unknown> : null
  if (!limits) return text.liveLimitsUnavailable
  const maxOrder = typeof limits.max_order_notional_usd === "number" ? limits.max_order_notional_usd : undefined
  const trades = typeof limits.max_trades_per_day === "number" ? limits.max_trades_per_day : undefined
  const leverage = typeof limits.max_leverage === "number" ? limits.max_leverage : undefined
  const parts = [
    maxOrder ? `<=${formatLimit(maxOrder)}/${text.liveOrder}` : "",
    trades ? `${trades}/${text.liveDay}` : "",
    leverage ? (leverage <= 1 ? text.liveNoLeverage : `${leverage}x`) : ""
  ].filter(Boolean)
  return parts.join(" · ") || text.liveLimitsUnavailable
}

function LiveStatusPanel({
  status,
  loading,
  unavailable,
  onRefresh,
  onHalt,
  onResume,
  onAuthorize,
  onStartRunner,
  onStopRunner,
  text
}: {
  status: LiveStatus | null
  loading: boolean
  unavailable: boolean
  onRefresh: () => void
  onHalt: () => void
  onResume: () => void
  onAuthorize: (broker: string) => void
  onStartRunner: (broker: string) => void
  onStopRunner: (broker: string) => void
  text: typeof AGENT_TEXT[AppLanguage]
}) {
  const [open, setOpen] = useState(false)
  const [busyAction, setBusyAction] = useState("")
  const [actionError, setActionError] = useState("")
  const brokers = status?.brokers || []
  const halted = Boolean(status?.global_halted)
  const authorizedCount = brokers.filter((broker) => broker.auth.oauth_token_present).length
  const anyRunning = brokers.some((broker) => broker.runner?.alive)
  const hasActiveRuntime = Boolean(halted || brokers.some((item) => item.runner?.alive || item.mandate || item.halted))

  function runAction(key: string, action: () => void | Promise<void>) {
    if (busyAction) return
    setBusyAction(key)
    setActionError("")
    Promise.resolve(action())
      .then(onRefresh)
      .catch((error: unknown) => setActionError(error instanceof Error ? error.message : text.liveActionFailed))
      .finally(() => setBusyAction(""))
  }

  return (
    <section className="rounded-lg border bg-background p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">{text.liveRuntime}</h2>
        <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onRefresh}>
          {loading ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Activity className="mr-1 size-3" />}
          {text.refresh}
        </Button>
      </div>
      {unavailable ? (
        <p className="mt-3 rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
          {text.liveUnavailable}
        </p>
      ) : (
        <div className="mt-3 space-y-2">
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="inline-flex max-w-full items-center gap-1.5 rounded-lg bg-primary/10 px-2.5 py-1 text-left text-xs font-medium text-primary transition-colors hover:bg-primary/15"
            aria-label={text.liveStatus}
            aria-expanded={open}
          >
            <Activity className="size-3 shrink-0" />
            <span className="shrink-0">{text.liveRuntime}</span>
            <span className="truncate text-muted-foreground">
              {authorizedCount > 0 ? `${authorizedCount} ${text.liveConnected}` : text.liveNoConnector}
            </span>
            {anyRunning && !halted && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">
                <CircleDot className="size-2.5" />
                {text.running}
              </span>
            )}
            {halted && (
              <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-1.5 py-0.5 text-[10px] font-medium text-destructive">
                <OctagonX className="size-2.5" />
                {text.liveHalted}
              </span>
            )}
            <ChevronDown className={`size-3 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>

          {actionError && (
            <p className="rounded-md border border-destructive/30 bg-destructive/5 px-2 py-1 text-[11px] text-destructive">
              {actionError}
            </p>
          )}

          {brokers.length === 0 ? (
            <p className="rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
              {text.liveNoConnector}
            </p>
          ) : open && (
            <div className="space-y-2 rounded-lg border border-primary/20 bg-background p-2 shadow-sm">
              {brokers.map((broker) => {
                const brokerKey = broker.auth.broker
                const authorized = broker.auth.oauth_token_present
                const brokerHalted = halted || broker.halted
                const runnerAlive = Boolean(broker.runner?.alive)
                const mandate = broker.mandate && !broker.mandate.expired ? broker.mandate : null
                const actionKey = `${brokerKey}:${runnerAlive ? "stop" : "start"}`
                return (
                  <div key={brokerKey} className="grid gap-2 rounded-lg border bg-muted/20 p-2.5">
                    <div className="flex min-w-0 items-center gap-1.5">
                      <span className="truncate text-xs font-semibold capitalize text-foreground">{brokerKey}</span>
                      {authorized ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">
                          <ShieldCheck className="size-2.5" />
                          {text.liveAuthorized}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                          <CircleSlash className="size-2.5" />
                          {text.liveNotConnected}
                        </span>
                      )}
                    </div>

                    {!authorized ? (
                      <div className="grid gap-1.5 rounded-md border border-dashed border-primary/30 bg-primary/5 p-2">
                        <div className="flex items-center gap-1.5 text-[11px] font-medium text-primary">
                          <PlugZap className="size-3 shrink-0" />
                          {text.liveConnectProfile}
                        </div>
                        <p className="text-[10px] leading-relaxed text-muted-foreground">
                          {text.liveAuthorizeInstruction}
                        </p>
                        <p className="text-[10px] leading-relaxed text-muted-foreground">
                          {text.liveAuthorizationNote}
                        </p>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="h-7 justify-center text-xs"
                          disabled={Boolean(busyAction)}
                          onClick={() => runAction(`${brokerKey}:authorize`, () => onAuthorize(brokerKey))}
                        >
                          {busyAction === `${brokerKey}:authorize` && <Loader2 className="mr-1 size-3 animate-spin" />}
                          {text.liveAuthorize}
                        </Button>
                      </div>
                    ) : (
                      <>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="rounded-md border bg-background/60 p-2">
                            <div className="flex items-center gap-1 text-[10px] font-semibold uppercase text-muted-foreground">
                              <CircleDot className={`size-2.5 ${runnerAlive ? "text-emerald-500" : "text-muted-foreground"}`} />
                              {text.liveRunner}
                            </div>
                            <div className={`mt-0.5 text-xs font-semibold ${runnerAlive ? "text-emerald-600" : "text-muted-foreground"}`}>
                              {runnerAlive ? text.running : text.liveStopped}
                            </div>
                          </div>
                          <div className="rounded-md border bg-background/60 p-2">
                            <div className="flex items-center gap-1 text-[10px] font-semibold uppercase text-muted-foreground">
                              <Activity className="size-2.5" />
                              {text.liveLastTick}
                            </div>
                            <div className="mt-0.5 text-xs font-medium text-foreground">
                              {formatRelative(broker.runner?.last_tick, text)}
                            </div>
                          </div>
                        </div>

                        {mandate ? (
                          <div className="rounded-md border bg-background/60 p-2">
                            <div className="flex items-center gap-1 text-[10px] font-semibold uppercase text-muted-foreground">
                              <ShieldCheck className="size-2.5" />
                              {text.liveActiveMandate}
                            </div>
                            <div className="mt-0.5 font-mono text-[11px] text-foreground">
                              {summarizeMandate(mandate, text)}
                            </div>
                          </div>
                        ) : (
                          <div className="rounded-md border border-dashed bg-background/40 p-2 text-[10px] leading-relaxed text-muted-foreground">
                            {text.liveNoActiveMandate}
                          </div>
                        )}

                        <div className="flex items-center justify-between gap-2">
                          {brokerHalted ? (
                            <span className="inline-flex items-center gap-1 text-[10px] font-medium text-destructive">
                              <OctagonX className="size-3" />
                              {text.liveHaltedControls}
                            </span>
                          ) : (
                            <span className="text-[10px] text-muted-foreground">
                              {runnerAlive ? text.liveRuntimeActive : text.liveIdle}
                            </span>
                          )}
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className={`h-7 px-2 text-[11px] ${runnerAlive ? "border-destructive/40 text-destructive hover:bg-destructive/10" : "border-primary/40 text-primary hover:bg-primary/10"}`}
                            title={runnerAlive ? text.liveStopRunnerTitle : text.liveStartRunnerTitle}
                            disabled={Boolean(busyAction) || brokerHalted || !mandate}
                            onClick={() => runAction(actionKey, () => runnerAlive ? onStopRunner(brokerKey) : onStartRunner(brokerKey))}
                          >
                            {busyAction === actionKey ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Power className="mr-1 size-3" />}
                            {runnerAlive ? text.liveStopRunner : text.liveStartRunner}
                          </Button>
                        </div>
                      </>
                    )}
                  </div>
                )
              })}
            </div>
          )}
          {hasActiveRuntime && (
            <Button
              type="button"
              variant={halted ? "outline" : "destructive"}
              size="sm"
              className="w-full justify-center"
              disabled={Boolean(busyAction)}
              onClick={() => runAction(halted ? "resume" : "halt", halted ? onResume : onHalt)}
            >
              {busyAction === (halted ? "resume" : "halt") ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Square className="mr-2 size-4" />}
              {halted ? text.liveResume : text.globalHalt}
            </Button>
          )}
        </div>
      )}
    </section>
  )
}

export function ToolRail({
  tools,
  goal,
  running,
  loading,
  liveStatus,
  liveStatusLoading,
  liveStatusUnavailable,
  onRefreshLiveStatus,
  onHaltLive,
  onResumeLive,
  onAuthorizeLive,
  onStartLiveRunner,
  onStopLiveRunner,
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
  onResumeLive: () => void
  onAuthorizeLive: (broker: string) => void
  onStartLiveRunner: (broker: string) => void
  onStopLiveRunner: (broker: string) => void
  text: typeof AGENT_TEXT[AppLanguage]
}) {
  const [expandedTools, setExpandedTools] = useState<Set<string>>(() => new Set())

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
                const compact = !expanded && (tool.status === "ok" || tool.status === "skipped")
                const statusClass = tool.status === "error"
                  ? "bg-destructive/10 text-destructive"
                  : tool.status === "running"
                    ? "bg-primary/10 text-primary"
                    : tool.status === "warning"
                      ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
                      : tool.status === "skipped"
                        ? "bg-muted text-muted-foreground"
                      : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                return (
                  <div key={tool.id} className={`min-w-0 rounded-md border bg-background px-3 shadow-sm ${compact ? "py-1.5" : "py-2"}`}>
                    <button
                      type="button"
                      className="block w-full text-left"
                      aria-expanded={expanded}
                      onClick={() => toggleTool(tool.id)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate text-xs font-medium">{tool.title || label?.title || tool.name}</span>
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${statusClass}`}>
                          {statusLabel(tool.status, text)}
                        </span>
                      </div>
                      {!compact && (
                        <>
                          <p className="mt-1 break-words text-[11px] leading-4 text-muted-foreground [overflow-wrap:anywhere]">{label?.desc || tool.name}</p>
                          <p className="mt-1 text-[10px] font-medium text-primary">
                            {expanded ? text.collapseDetails : text.expandDetails}
                          </p>
                        </>
                      )}
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
          onResume={onResumeLive}
          onAuthorize={onAuthorizeLive}
          onStartRunner={onStartLiveRunner}
          onStopRunner={onStopLiveRunner}
          text={text}
        />
      </div>
    </aside>
  )
}

export function SessionRail({
  sessions,
  activeSessionId,
  onNew,
  onSelect,
  onRename,
  onDelete,
  text
}: {
  sessions: ResearchSession[]
  activeSessionId: string | null
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
                          className="min-w-0 flex-1 text-left"
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
      </div>
    </aside>
  )
}
