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
  message_id: string
  attempt_id?: string
}

export interface ResearchAgentEvent {
  event_id?: number
  event_type: string
  payload: Record<string, unknown>
}

export interface ParsedResearchStreamEvent {
  event: string
  data: Record<string, unknown>
  eventId?: number
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

export type ResearchAgentStreamHandlers = {
  onEvent: (event: ParsedResearchStreamEvent) => void
  onError?: (error: Event) => void
  onOpen?: () => void
}

function getStoredToken() {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem("auth-token")
}

function envelope<T>(data: T, message = "ok"): ApiEnvelope<T> {
  return { success: true, data, message }
}

function parseEventData(raw: string): Record<string, unknown> {
  try {
    return raw ? JSON.parse(raw) as Record<string, unknown> : {}
  } catch {
    return { content: raw }
  }
}

function mapVibeEvent(eventName: string, data: Record<string, unknown>, eventId?: number): ParsedResearchStreamEvent[] {
  if (eventName === "text_delta") {
    return [{ event: "assistant_delta", data: { ...data, content: data.delta || data.text || "" }, eventId }]
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
    return [
      { event: "message_completed", data: { ...data, content: data.summary || "" }, eventId },
      { event: "task_completed", data, eventId }
    ]
  }
  if (eventName === "attempt.failed") {
    return [{ event: "task_failed", data: { ...data, content: data.error || "Agent execution failed" }, eventId }]
  }
  if (eventName === "tool_heartbeat" || eventName === "tool_progress") {
    return [{
      event: "tool_started",
      data: { ...data, tool_name: data.tool || data.tool_name },
      eventId
    }]
  }
  if (eventName === "heartbeat") {
    return [{ event: "heartbeat", data, eventId }]
  }
  return [{ event: eventName, data, eventId }]
}

export const researchAgentApi = {
  createSession: async (payload: { title?: string }) =>
    envelope(await request.post<ResearchSession>("/api/vibe/sessions", payload)),
  listSessions: async () => envelope(await request.get<ResearchSession[]>("/api/vibe/sessions")),
  updateSession: async (sessionId: string, payload: { title: string }) => {
    await request.patch<{ status: string }>(`/api/vibe/sessions/${sessionId}`, payload)
    const session = await request.get<ResearchSession>(`/api/vibe/sessions/${sessionId}`)
    return envelope(session)
  },
  deleteSession: async (sessionId: string) =>
    envelope(await request.delete<{ status: string; session_id?: string }>(`/api/vibe/sessions/${sessionId}`)),
  cancelSession: async (sessionId: string) =>
    envelope(await request.post<{ status: string }>(`/api/vibe/sessions/${sessionId}/cancel`)),
  uploadFile: async (file: File) => {
    const form = new FormData()
    form.append("file", file)
    const response = await fetch("/api/vibe/upload", { method: "POST", body: form })
    if (!response.ok) throw new Error(await response.text())
    return envelope(await response.json() as { status: string; file_path: string; filename: string })
  },
  getLiveStatus: async () => envelope(await request.get<LiveStatus>("/api/vibe/live/status")),
  haltLive: async (payload: { reason: string; broker?: string | null; session_id?: string | null }) =>
    envelope(await request.post<{ halted: boolean; broker?: string | null; reason: string }>("/api/vibe/live/halt", payload)),
  listMessages: async (sessionId: string) =>
    envelope(await request.get<ResearchMessage[]>(`/api/vibe/sessions/${sessionId}/messages`)),
  appendMessage: async (sessionId: string, payload: { role?: string; content: string; metadata?: Record<string, unknown> }) =>
    envelope(await request.post<SendResearchMessageResponse>(`/api/vibe/sessions/${sessionId}/messages`, { content: payload.content })),
  listEvents: async (sessionId: string, afterEventId = 0) =>
    envelope(await request.get<ResearchAgentEvent[]>(`/api/vibe-history/sessions/${sessionId}/events`, {
      params: { after_event_id: afterEventId },
      skipErrorHandler: true
    })),
  streamEvents: async (sessionId: string, afterEventId = 0) => {
    void sessionId
    void afterEventId
    return [] as ParsedResearchStreamEvent[]
  },
  subscribeEvents: (
    sessionId: string,
    handlers: ResearchAgentStreamHandlers,
    afterEventId = 0
  ) => {
    const token = getStoredToken()
    const params = new URLSearchParams()
    params.set("replay", "active")
    if (afterEventId > 0) params.set("last_index", String(afterEventId))
    if (token) params.set("api_key", token)
    const query = params.toString()
    const source = new EventSource(
      `/api/vibe/sessions/${sessionId}/events${query ? `?${query}` : ""}`
    )
    const eventTypes = [
      "text_delta",
      "thinking_done",
      "tool_call",
      "tool_result",
      "tool_heartbeat",
      "tool_progress",
      "compact",
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
      "heartbeat"
    ]

    const parse = (eventName: string, message: MessageEvent) => {
      const data = parseEventData(message.data)
      const eventId = message.lastEventId ? Number(message.lastEventId) : undefined
      for (const mapped of mapVibeEvent(eventName, data, eventId)) handlers.onEvent(mapped)
    }

    source.onopen = () => handlers.onOpen?.()
    source.onerror = (event) => handlers.onError?.(event)
    for (const eventType of eventTypes) {
      source.addEventListener(eventType, (event) => parse(eventType, event as MessageEvent))
    }

    return () => source.close()
  }
}
