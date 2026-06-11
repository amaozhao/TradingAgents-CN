"use client"

import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react"
import { ArrowDown, Bot, Download, Loader2, Plus, Send, Sparkles, Square, Target, TrendingUp, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { MessageBubble, SessionLoadingView, SessionRail, ToolRail, WelcomeScreen } from "@/features/agent/view"
import { StockConfigCard, StockReplayCard, type StockPayload, type StockRunStatus } from "@/features/research/stock"
import { researchAgentApi, type LiveStatus, type ParsedResearchStreamEvent, type ResearchGoal, type ResearchSession } from "@/libs/api/research-agent"
import { useAppStore } from "@/stores/app-store"

import { attemptResultContent, createGoalDraft, eventContent, eventFailureContent, eventToolStatus, finalAnswerFromEvents, failureMessageFromEvents, latestActiveAttempt, latestAttempt, mergeGoalEvent, messagesFromApi, normalizePersistedEvent, nowId, previewFromEventData, stockLinksFromEventData, stockPayloadFromMetadata, stockStageId, stockStageTitle, toolMessageId, toolsFromEvents } from "@/features/agent/event"
import { AGENT_COMPLETION_POLL_TIMEOUT_MS, AGENT_TEXT, COMPOSER_MAX_HEIGHT, COMPOSER_MIN_HEIGHT } from "@/features/agent/text"
import type { AgentMessage, ToolState } from "@/features/agent/types"

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
  const [showStockConfig, setShowStockConfig] = useState(false)
  const [stockConfigSubmitted, setStockConfigSubmitted] = useState(false)
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
  const localRunningSessionRef = useRef<string | null>(null)

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
    if (!activeSessionId) {
      setSessionLoading(false)
      return
    }
    if (running && localRunningSessionRef.current === activeSessionId) {
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
      researchAgentApi.getGoal(activeSessionId),
      researchAgentApi.listAttempts(activeSessionId)
    ]).then(([messageResponse, eventResponse, goalResponse, attemptResponse]) => {
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
      const attempts = attemptResponse.data || []
      const activeAttempt = latestActiveAttempt(attempts)
      const visibleAttempt = activeAttempt || latestAttempt(attempts)
      setTools(toolsFromEvents(persistedEvents, visibleAttempt?.attempt_id))
      setGoal(goalResponse.data || persistedEvents.reduce((current, event) => mergeGoalEvent(current, event.event, event.data), null as ResearchGoal | null))
      if (activeAttempt) {
        runFinishedRef.current = false
        localRunningSessionRef.current = null
        setRunning(true)
        setCancelRequested(false)
        stopStream()
        streamStopRef.current = researchAgentApi.subscribeEvents(
          activeSessionId,
          { onEvent: handleStreamEvent, onError: () => undefined },
          lastEventIdRef.current
        )
        startCompletionPolling(activeSessionId, activeAttempt.attempt_id)
      } else {
        runFinishedRef.current = true
        setRunning(false)
        setCancelRequested(false)
      }
      requestAnimationFrame(scrollToBottom)
    }).catch(() => {
      if (sessionLoadSeqRef.current !== loadSeq) return
      setMessages([])
      setTools([])
      setGoal(null)
      setRunning(false)
    }).finally(() => {
      if (sessionLoadSeqRef.current === loadSeq) setSessionLoading(false)
    })
    // Session reload is keyed by session identity; running changes are handled in refs to avoid resubscribing loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId])

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
  const stockRunStatus = tools.filter((tool) => tool.name === "stock_analysis").at(-1)

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
    localRunningSessionRef.current = null
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
      localRunningSessionRef.current = null
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
      localRunningSessionRef.current = null
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
      localRunningSessionRef.current = null
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

  function upsertStreamMessage(message: AgentMessage) {
    setMessages((current) => {
      const index = current.findIndex((item) => item.id === message.id)
      if (index < 0) return [...current, message]
      const next = [...current]
      next[index] = { ...next[index], ...message }
      return next
    })
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
      return
    }
    if (item.event === "tool_started" || item.event === "tool_call") {
      const toolName = String(item.data.tool_name || item.data.tool || "tool")
      upsertTool({
        id: toolName,
        name: toolName,
        status: "running",
        preview: previewFromEventData(item.data),
        ...stockLinksFromEventData(item.data)
      })
      upsertStreamMessage({ id: toolMessageId(toolName), type: "tool_call", content: previewFromEventData(item.data), tool: toolName, status: "running", timestamp: Date.now() })
      return
    }
    if (item.event === "tool_progress" || item.event === "tool_heartbeat") {
      const toolName = String(item.data.tool_name || item.data.tool || "tool")
      upsertTool({
        id: toolName,
        name: toolName,
        status: "running",
        preview: previewFromEventData(item.data),
        ...stockLinksFromEventData(item.data)
      })
      return
    }
    if (item.event === "stock_analysis.stage") {
      const toolName = String(item.data.tool_name || item.data.tool || "stock_analysis")
      upsertTool({
        id: stockStageId(item.data),
        name: toolName,
        title: stockStageTitle(item.data),
        status: eventToolStatus(item),
        preview: previewFromEventData(item.data),
        artifactId: item.data.artifact_id ? String(item.data.artifact_id) : undefined,
        ...stockLinksFromEventData(item.data)
      })
      return
    }
    if (item.event === "tool_completed" || item.event === "tool_failed" || item.event === "tool_result") {
      const toolName = String(item.data.tool_name || item.data.tool || "tool")
      const status = eventToolStatus(item)
      const preview = previewFromEventData(item.data)
      const elapsedMs = typeof item.data.elapsed_ms === "number" ? item.data.elapsed_ms : undefined
      upsertTool({
        id: toolName,
        name: toolName,
        status,
        preview,
        artifactId: item.data.artifact_id ? String(item.data.artifact_id) : undefined,
        ...stockLinksFromEventData(item.data),
        elapsedMs
      })
      upsertStreamMessage({ id: toolMessageId(toolName), type: "tool_result", content: preview, tool: toolName, status, elapsedMs, timestamp: Date.now() })
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
      localRunningSessionRef.current = null
      setRunning(false)
      setCancelRequested(false)
      appendStreamMessage({ id: nowId("error"), type: "error", content: eventFailureContent(item.data) || "Agent execution failed", timestamp: Date.now() })
      return
    }
    if (item.event === "task_completed" || item.event === "attempt.completed") {
      const attemptId = String(item.data.attempt_id || "")
      const terminalSessionId = activeSessionId || localRunningSessionRef.current || String(item.data.session_id || "")
      const terminalContent = eventContent(item.data)
      if (terminalContent) upsertStreamingAnswer(terminalContent, true)
      if (terminalSessionId && attemptId) {
        void refreshCompletedAttemptFromStore(terminalSessionId, attemptId).then((found) => {
          if (found) return
          window.setTimeout(() => {
            void refreshAttemptStatusFromStore(terminalSessionId, attemptId).catch(() => undefined)
          }, 500)
        }).catch(() => undefined)
      }
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      localRunningSessionRef.current = null
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
    lastEventIdRef.current = ""
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

  async function runPrompt(raw: string, metadata: Record<string, unknown> = {}) {
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
    setTools([])
    setMessages((current) => [...current, { id: nowId("user"), type: "user", content: finalPrompt, timestamp: Date.now() }])
    requestAnimationFrame(scrollToBottom)

    try {
      const sessionId = await ensureSession(trimmed)
      localRunningSessionRef.current = sessionId
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
          goal_id: linkedGoalId,
          ...metadata
        }
      })
      startCompletionPolling(sessionId, appendResponse.data.attempt_id)
    } catch (error) {
      stopStream()
      stopCompletionPolling()
      runFinishedRef.current = true
      localRunningSessionRef.current = null
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

  function fillComposerFromQuickPrompt(prompt: string) {
    setInput(prompt)
    setComposerMode("chat")
    setShowMenu(false)
    requestAnimationFrame(() => composerRef.current?.focus())
  }

  function fillComposerFromStockSummary(summary: string) {
    setInput(`请进行单股分析：${summary}`)
    setComposerMode("chat")
    requestAnimationFrame(() => composerRef.current?.focus())
  }

  async function runStockAnalysis(summary: string, payload: StockPayload) {
    setStockConfigSubmitted(true)
    await runPrompt(`单股分析：${summary}`, {
      mode: "stock_analysis_workflow",
      tool_name: "stock_analysis",
      tool_arguments: payload
    })
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
    localRunningSessionRef.current = null
    setActiveSessionId(null)
    sessionLoadSeqRef.current += 1
    setSessionLoading(false)
    lastEventIdRef.current = ""
    setMessages([])
    setTools([])
    setGoal(null)
    setInput("")
    setShowStockConfig(false)
    setStockConfigSubmitted(false)
    setComposerMode("chat")
  }

  function handleSelectSession(sessionId: string) {
    stopStream()
    stopCompletionPolling()
    runFinishedRef.current = true
    localRunningSessionRef.current = null
    setRunning(false)
    setCancelRequested(false)
    lastEventIdRef.current = ""
    setSessionLoading(true)
    setMessages([])
    setTools([])
    setGoal(null)
    setShowStockConfig(false)
    setStockConfigSubmitted(false)
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
    localRunningSessionRef.current = null
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

  function renderMessage(message: AgentMessage) {
    const payload = message.type === "user"
      ? stockPayloadFromMetadata(message.metadata)
      : null
    if (payload) {
      return (
        <StockReplayCard
          key={message.id}
          content={message.content}
          payload={payload}
          runStatus={stockRunStatus as StockRunStatus | undefined}
        />
      )
    }
    return <MessageBubble key={message.id} message={message} text={text} />
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] min-h-[680px] overflow-hidden rounded-lg border bg-background">
      <SessionRail
        sessions={sessions}
        activeSessionId={activeSessionId}
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
              <h1 className="truncate text-base font-semibold">{text.pageTitle}</h1>
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
              <WelcomeScreen onExample={fillComposerFromQuickPrompt} text={text} />
            ) : (
              messages.map(renderMessage)
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
            {showStockConfig && (
              <StockConfigCard
                running={running}
                locked={stockConfigSubmitted}
                runStatus={stockRunStatus}
                onCancel={() => {
                  setShowStockConfig(false)
                  setStockConfigSubmitted(false)
                }}
                onSave={fillComposerFromStockSummary}
                onSubmit={({ summary, payload }) => {
                  void runStockAnalysis(summary, payload)
                }}
              />
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
                    <button
                      type="button"
                      disabled={running}
                      onClick={() => {
                        setShowStockConfig(true)
                        setStockConfigSubmitted(false)
                        setComposerMode("chat")
                        setShowMenu(false)
                        requestAnimationFrame(scrollToBottom)
                      }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <TrendingUp className="size-4" />{text.singleStock}
                    </button>
                    <div className="my-1 border-t" />
                    {text.quickPrompts.map((item) => (
                      <button key={item.label} type="button" onClick={() => fillComposerFromQuickPrompt(item.prompt)} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
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
