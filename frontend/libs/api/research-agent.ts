import request from "@/libs/api/request"

type ApiEnvelope<T> = {
  success: boolean
  data: T
  message: string
}

export interface ResearchSession {
  session_id: string
  title?: string
  status?: string
  created_at?: string
  updated_at?: string
  last_attempt_id?: string | null
  config?: Record<string, unknown>
}

export interface ResearchMessage {
  message_id: string
  session_id?: string
  role: string
  content: string
  created_at?: string
  linked_attempt_id?: string | null
  metadata?: Record<string, unknown>
}

export interface SendResearchMessageResponse {
  status?: string
  message_id?: string
  attempt_id?: string
  job_id?: string
  session_id?: string
}

export interface ResearchAttempt {
  attempt_id: string
  session_id?: string
  user_id?: string
  status?: string
  error?: string | null
  result?: Record<string, unknown> | null
  created_at?: string
  started_at?: string | null
  completed_at?: string | null
}

export interface ResearchAgentEvent {
  event_id?: number | string
  event_type: string
  payload: Record<string, unknown>
}

export interface ResearchGoalEvidence {
  evidence_id?: string
  kind?: string
  summary?: string
  artifact_id?: string | null
  message_id?: string | null
  metadata?: Record<string, unknown>
  created_at?: string
}

export interface ResearchGoal {
  goal_id: string
  session_id?: string
  title?: string
  description?: string
  criteria?: string[]
  status?: string
  status_reason?: string
  evidence?: ResearchGoalEvidence[]
  created_at?: string
  updated_at?: string
}

export interface ParsedResearchStreamEvent {
  event: string
  data: Record<string, unknown>
  eventId?: string
}

export interface LiveBrokerStatus {
  auth: {
    broker: string
    oauth_token_present: boolean
    is_live_broker: boolean
  }
  mandate?: {
    broker: string
    account_ref: string
    expires_at: string
    expired: boolean
    limits?: Record<string, unknown>
  } | null
  runner?: {
    broker: string
    alive: boolean
    last_tick?: number | null
    last_tick_age_seconds?: number | null
  } | null
  halted: boolean
}

export interface LiveStatus {
  global_halted: boolean
  brokers: LiveBrokerStatus[]
}

export interface ResearchSwarmPreset {
  preset: string
  title?: string
  description?: string
  workers?: string[]
}

export interface ResearchSwarmRun {
  run_id: string
  session_id?: string | null
  parent_run_id?: string | null
  preset: string
  title?: string
  variables?: Record<string, unknown>
  workers?: Array<Record<string, unknown>>
  status: string
  created_at?: string
  updated_at?: string
  completed_at?: string | null
  error?: string | null
}

export interface ResearchSwarmEvent {
  event_id?: number | string
  run_id: string
  session_id?: string | null
  event_type: string
  payload: Record<string, unknown>
  created_at?: string
}

export interface ResearchArtifact {
  artifact_id: string
  session_id: string
  artifact_type: string
  payload: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface ResearchSkill {
  name: string
  title?: string
  status: string
  source_runtime_dependency?: boolean
  mutation_allowed?: boolean
  summary?: string
  prompt_context?: string
}

export type ResearchAgentStreamHandlers = {
  onEvent: (event: ParsedResearchStreamEvent) => void
  onError?: (error: Event) => void
  onOpen?: () => void
}

const BASE = "/api/research-agent"

function getStoredToken() {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem("auth-token")
}

function parseEventData(raw: string): Record<string, unknown> {
  try {
    return raw ? JSON.parse(raw) as Record<string, unknown> : {}
  } catch {
    return { content: raw }
  }
}

function formatSwarmStatus(data: Record<string, unknown>) {
  const event = data.event && typeof data.event === "object"
    ? data.event as Record<string, unknown>
    : {}
  const eventType = String(event.type || "")
  const preset = String(data.preset || "")
  const runId = String(data.run_id || "")
  const agentId = String(event.agent_id || "")
  const taskId = String(event.task_id || "")
  const status = String(data.status || eventType || "")
  const parts: string[] = []
  if (preset) parts.push(`preset=${preset}`)
  if (runId) parts.push(`run=${runId}`)
  if (eventType) parts.push(`event=${eventType}`)
  if (agentId) parts.push(`agent=${agentId}`)
  if (taskId) parts.push(`task=${taskId}`)
  if (status && !eventType) parts.push(`status=${status}`)
  return parts.length ? parts.join(" · ") : "Swarm event received"
}

function mapSwarmEvent(
  data: Record<string, unknown>,
  eventId?: string
): ParsedResearchStreamEvent {
  const event = data.event && typeof data.event === "object"
    ? data.event as Record<string, unknown>
    : {}
  const eventType = String(event.type || "")
  const eventName = eventType === "run_completed"
    ? "tool_completed"
    : eventType === "run_error" || eventType === "run_cancelled"
      ? "tool_failed"
      : "tool_progress"
  return {
    event: eventName,
    data: {
      ...data,
      tool_name: "run_swarm",
      tool: "run_swarm",
      preview: formatSwarmStatus(data),
      content: formatSwarmStatus(data),
      result: data.event || data
    },
    eventId
  }
}

function mapResearchAgentEvent(eventName: string, data: Record<string, unknown>, eventId?: string): ParsedResearchStreamEvent[] {
  if (eventName === "text_delta") {
    return [{ event: "assistant_delta", data: { ...data, content: data.delta || data.text || "" }, eventId }]
  }
  if (eventName === "answer_truncated") {
    return [{ event: "assistant_delta", data: { ...data, content: data.content || data.text || "" }, eventId }]
  }
  if (eventName === "tool_call") {
    return [{
      event: "tool_started",
      data: {
        ...data,
        tool_name: data.tool || data.tool_name,
        arguments: data.arguments || {}
      },
      eventId
    }]
  }
  if (eventName === "tool_result") {
    const ok = String(data.status || "ok") === "ok"
    return [{
      event: ok ? "tool_completed" : "tool_failed",
      data: {
        ...data,
        tool_name: data.tool || data.tool_name,
        result: data.preview || data.result || data.error || "",
        content: data.preview || data.result || data.error || ""
      },
      eventId
    }]
  }
  if (eventName === "attempt.completed") {
    const result = data.result && typeof data.result === "object"
      ? data.result as Record<string, unknown>
      : {}
    const content = data.summary || data.content || result.summary || result.content || ""
    return [
      { event: "message_completed", data: { ...data, content }, eventId },
      { event: "task_completed", data, eventId }
    ]
  }
  if (eventName === "attempt.failed") {
    return [{ event: "task_failed", data: { ...data, content: data.error || "Agent execution failed" }, eventId }]
  }
  if (eventName === "tool_heartbeat" || eventName === "tool_progress") {
    return [{
      event: "tool_progress",
      data: { ...data, tool_name: data.tool || data.tool_name },
      eventId
    }]
  }
  if (eventName === "swarm.started") {
    return [{
      event: "tool_started",
      data: {
        ...data,
        tool_name: "run_swarm",
        tool: "run_swarm",
        arguments: {
          preset: data.preset,
          run_id: data.run_id,
          variables: data.variables
        },
        preview: formatSwarmStatus(data),
        content: formatSwarmStatus(data)
      },
      eventId
    }]
  }
  if (eventName === "swarm.event") {
    return [mapSwarmEvent(data, eventId)]
  }
  if (eventName === "heartbeat") {
    return [{ event: "heartbeat", data, eventId }]
  }
  return [{ event: eventName, data, eventId }]
}

export const researchAgentApi = {
  createSession: async (payload: { title?: string }) =>
    request.post<ApiEnvelope<ResearchSession>>(`${BASE}/sessions`, payload),
  listSessions: async () => request.get<ApiEnvelope<ResearchSession[]>>(`${BASE}/sessions`),
  updateSession: async (sessionId: string, payload: { title: string }) =>
    request.patch<ApiEnvelope<ResearchSession>>(`${BASE}/sessions/${sessionId}`, payload),
  deleteSession: async (sessionId: string) =>
    request.delete<ApiEnvelope<{ status: string; session_id?: string }>>(`${BASE}/sessions/${sessionId}`),
  cancelSession: async (sessionId: string) =>
    request.post<ApiEnvelope<{ status: string }>>(`${BASE}/sessions/${sessionId}/cancel`),
  uploadFile: async (file: File, sessionId?: string | null) => {
    const form = new FormData()
    form.append("file", file)
    if (sessionId) form.append("session_id", sessionId)
    return request.post<ApiEnvelope<{ status: string; file_path?: string; file_id?: string; artifact_id?: string; filename: string; size?: number }>>(`${BASE}/upload`, form, {
      headers: { "Content-Type": "multipart/form-data" }
    })
  },
  getArtifact: async (artifactId: string) =>
    request.get<ApiEnvelope<ResearchArtifact>>(`${BASE}/artifacts/${artifactId}`),
  listArtifacts: async (sessionId: string, artifactType?: string) =>
    request.get<ApiEnvelope<ResearchArtifact[]>>(`${BASE}/sessions/${sessionId}/artifacts`, {
      params: artifactType ? { artifact_type: artifactType } : undefined
    }),
  listRuns: async () =>
    request.get<ApiEnvelope<ResearchArtifact[]>>(`${BASE}/runs`),
  getRun: async (runId: string) =>
    request.get<ApiEnvelope<ResearchArtifact>>(`${BASE}/runs/${runId}`),
  getRunCode: async (runId: string) =>
    request.get<ApiEnvelope<ResearchArtifact>>(`${BASE}/runs/${runId}/code`),
  getRunPine: async (runId: string) =>
    request.get<ApiEnvelope<ResearchArtifact>>(`${BASE}/runs/${runId}/pine`),
  getShadowReport: async (shadowId: string) =>
    request.get<ApiEnvelope<ResearchArtifact>>(`${BASE}/shadow-reports/${shadowId}`),
  listSkills: async () =>
    request.get<ApiEnvelope<ResearchSkill[]>>(`${BASE}/skills`),
  getCapabilities: async () =>
    request.get<ApiEnvelope<Record<string, unknown>>>(`${BASE}/api`),
  getLlmSettings: async () =>
    request.get<ApiEnvelope<Record<string, unknown>>>(`${BASE}/settings/llm`),
  updateLlmSettings: async (values: Record<string, unknown>) =>
    request.put<ApiEnvelope<Record<string, unknown>>>(`${BASE}/settings/llm`, { values }),
  getDataSourceSettings: async () =>
    request.get<ApiEnvelope<Record<string, unknown>>>(`${BASE}/settings/data-sources`),
  updateDataSourceSettings: async (values: Record<string, unknown>) =>
    request.put<ApiEnvelope<Record<string, unknown>>>(`${BASE}/settings/data-sources`, { values }),
  rejectSystemShutdown: async () =>
    request.post<ApiEnvelope<Record<string, unknown>>>(`${BASE}/system/shutdown`),
  rejectRunShutdown: async (runId: string) =>
    request.post<ApiEnvelope<Record<string, unknown>>>(`${BASE}/runs/${runId}/shutdown`),
  getLiveStatus: async () => request.get<ApiEnvelope<LiveStatus>>(`${BASE}/live/status`),
  haltLive: async (payload: { reason: string; broker?: string | null; session_id?: string | null }) =>
    request.post<ApiEnvelope<{ halted: boolean; broker?: string | null; reason: string }>>(`${BASE}/live/halt`, payload),
  resumeLive: async (payload: { reason: string; broker?: string | null; session_id?: string | null }) =>
    request.post<ApiEnvelope<{ resumed: boolean; broker?: string | null; reason: string }>>(`${BASE}/live/resume`, payload),
  authorizeLive: async (payload: { broker?: string; session_id?: string | null }) =>
    request.post<ApiEnvelope<{ broker: string; oauth_token_present: boolean }>>(`${BASE}/live/authorize`, payload),
  startLiveRunner: async (payload: { broker?: string; session_id?: string | null }) =>
    request.post<ApiEnvelope<{ broker: string; alive: boolean }>>(`${BASE}/live/runner/start`, payload),
  stopLiveRunner: async (payload: { broker?: string; session_id?: string | null }) =>
    request.post<ApiEnvelope<{ broker: string; alive: boolean }>>(`${BASE}/live/runner/stop`, payload),
  commitMandate: async (payload: { proposal: Record<string, unknown>; session_id?: string | null }) =>
    request.post<ApiEnvelope<Record<string, unknown>>>(`${BASE}/mandate/commit`, payload),
  listSwarmPresets: async () =>
    request.get<ApiEnvelope<ResearchSwarmPreset[]>>(`${BASE}/swarm/presets`),
  createSwarmRun: async (payload: { preset: string; variables?: Record<string, unknown>; session_id?: string | null }) =>
    request.post<ApiEnvelope<ResearchSwarmRun>>(`${BASE}/swarm/runs`, payload),
  listSwarmRuns: async () =>
    request.get<ApiEnvelope<ResearchSwarmRun[]>>(`${BASE}/swarm/runs`),
  getSwarmRun: async (runId: string) =>
    request.get<ApiEnvelope<ResearchSwarmRun>>(`${BASE}/swarm/runs/${runId}`),
  listSwarmRunEvents: async (runId: string, afterEventId: string | number = 0) =>
    request.get<ApiEnvelope<ResearchSwarmEvent[]>>(`${BASE}/swarm/runs/${runId}/events`, {
      params: { after_event_id: Number(afterEventId) || 0 }
    }),
  cancelSwarmRun: async (runId: string) =>
    request.post<ApiEnvelope<ResearchSwarmRun>>(`${BASE}/swarm/runs/${runId}/cancel`),
  retrySwarmRun: async (runId: string) =>
    request.post<ApiEnvelope<ResearchSwarmRun>>(`${BASE}/swarm/runs/${runId}/retry`),
  listMessages: async (sessionId: string) =>
    request.get<ApiEnvelope<ResearchMessage[]>>(`${BASE}/sessions/${sessionId}/messages`),
  listAttempts: async (sessionId: string) =>
    request.get<ApiEnvelope<ResearchAttempt[]>>(`${BASE}/sessions/${sessionId}/attempts`, {
      skipErrorHandler: true
    }),
  appendMessage: async (sessionId: string, payload: { role?: string; content: string; metadata?: Record<string, unknown> }) =>
    request.post<ApiEnvelope<SendResearchMessageResponse>>(`${BASE}/sessions/${sessionId}/messages`, {
      role: payload.role || "user",
      content: payload.content,
      metadata: payload.metadata || {}
    }),
  createGoal: async (sessionId: string, payload: { title: string; description?: string; criteria?: string[] }) =>
    request.post<ApiEnvelope<ResearchGoal>>(`${BASE}/sessions/${sessionId}/goal`, payload),
  getGoal: async (sessionId: string) =>
    request.get<ApiEnvelope<ResearchGoal | null>>(`${BASE}/sessions/${sessionId}/goal`),
  updateGoal: async (sessionId: string, payload: { title?: string; description?: string; criteria?: string[] }) =>
    request.patch<ApiEnvelope<ResearchGoal>>(`${BASE}/sessions/${sessionId}/goal`, payload),
  addGoalEvidence: async (sessionId: string, payload: { kind?: string; summary: string; artifact_id?: string | null; message_id?: string | null; metadata?: Record<string, unknown> }) =>
    request.post<ApiEnvelope<ResearchGoal>>(`${BASE}/sessions/${sessionId}/goal/evidence`, payload),
  updateGoalStatus: async (sessionId: string, payload: { status: string; reason?: string; expected_goal_id?: string }) =>
    request.patch<ApiEnvelope<ResearchGoal>>(`${BASE}/sessions/${sessionId}/goal/status`, payload),
  listEvents: async (sessionId: string, afterEventId: string | number = 0) =>
    request.get<ApiEnvelope<ResearchAgentEvent[]>>(`${BASE}/sessions/${sessionId}/events`, {
      params: { after_event_id: Number(afterEventId) || 0 },
      skipErrorHandler: true
    }),
  streamEvents: async (sessionId: string, afterEventId: string | number = 0) => {
    void sessionId
    void afterEventId
    return [] as ParsedResearchStreamEvent[]
  },
  subscribeEvents: (
    sessionId: string,
    handlers: ResearchAgentStreamHandlers,
    afterEventId: string | number = ""
  ) => {
    const token = getStoredToken()
    const params = new URLSearchParams()
    if (afterEventId) params.set("after_event_id", String(Number(afterEventId) || 0))
    if (token) params.set("token", token)
    const query = params.toString()
    const source = new EventSource(
      `${BASE}/sessions/${sessionId}/events/stream${query ? `?${query}` : ""}`
    )
    const eventTypes = [
      "text_delta",
      "answer_truncated",
      "assistant_delta",
      "message_completed",
      "task_completed",
      "task_failed",
      "tool_call",
      "tool_started",
      "tool_progress",
      "tool_heartbeat",
      "tool_result",
      "tool_completed",
      "tool_failed",
      "stock_analysis.stage",
      "job_queued",
      "job_running",
      "job_completed",
      "job_failed",
      "job_cancelled",
      "attempt.created",
      "attempt.started",
      "attempt.completed",
      "attempt.failed",
      "goal.created",
      "goal.evidence",
      "goal.updated",
      "swarm.started",
      "swarm.event",
      "mandate.proposed",
      "mandate.committed",
      "live.action",
      "live.halted",
      "live.resumed",
      "compact",
      "heartbeat"
    ]

    const parse = (eventName: string, message: MessageEvent) => {
      const data = parseEventData(message.data)
      const eventId = message.lastEventId || undefined
      for (const mapped of mapResearchAgentEvent(eventName, data, eventId)) handlers.onEvent(mapped)
    }

    source.onopen = () => handlers.onOpen?.()
    source.onerror = (event) => handlers.onError?.(event)
    for (const eventType of eventTypes) {
      source.addEventListener(eventType, (event) => parse(eventType, event as MessageEvent))
    }

    return () => source.close()
  }
}
