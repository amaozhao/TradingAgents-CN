"use client"

import { useState } from "react"
import { Activity, Bot, Check, CheckCircle2, Loader2, Pencil, Plus, Square, Target, Trash2, Users, X } from "lucide-react"

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
    const label = text.toolLabels[message.tool || ""]?.title || message.tool || text.toolFallback
    return (
      <div className="flex gap-3">
        <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-full border bg-muted">
          {message.type === "tool_call" && message.status === "running" ? (
            <Loader2 className="size-4 animate-spin text-primary" />
          ) : (
            <CheckCircle2 className={`size-4 ${failed ? "text-destructive" : warning ? "text-amber-600" : ok ? "text-emerald-600" : "text-muted-foreground"}`} />
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
                    : tool.status === "warning"
                      ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
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
                        <span className="min-w-0 truncate text-xs font-medium">{tool.title || label?.title || tool.name}</span>
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${statusClass}`}>
                          {statusLabel(tool.status, text)}
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
