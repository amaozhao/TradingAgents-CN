import { ApiClient } from "@/libs/api/request"

export interface ResearchSession {
  session_id: string
  title?: string
  updated_at?: string
}

export interface ResearchMessage {
  message_id: string
  role: string
  content: string
  metadata?: Record<string, unknown>
}

export interface ResearchAgentEvent {
  event_id?: number
  event_type: string
  payload: Record<string, unknown>
}

export interface ParsedResearchStreamEvent {
  event: string
  data: Record<string, unknown>
}

function getStoredToken() {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem("auth-token")
}

function parseSseEvents(body: string): ParsedResearchStreamEvent[] {
  return body
    .split(/\n\n+/)
    .map((chunk) => {
      const lines = chunk.split(/\n/).filter(Boolean)
      const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim()
      const data = lines
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("\n")

      if (!event || !data) return null

      try {
        return { event, data: JSON.parse(data) as Record<string, unknown> }
      } catch {
        return { event, data: { content: data } }
      }
    })
    .filter((event): event is ParsedResearchStreamEvent => Boolean(event))
}

export const researchAgentApi = {
  createSession: (payload: { title?: string }) =>
    ApiClient.post<ResearchSession>("/api/research-agent/sessions", payload),
  listSessions: () => ApiClient.get<ResearchSession[]>("/api/research-agent/sessions"),
  listMessages: (sessionId: string) =>
    ApiClient.get<ResearchMessage[]>(`/api/research-agent/sessions/${sessionId}/messages`),
  appendMessage: (sessionId: string, payload: { role: string; content: string; metadata?: Record<string, unknown> }) =>
    ApiClient.post<ResearchMessage>(`/api/research-agent/sessions/${sessionId}/messages`, payload),
  listEvents: (sessionId: string, afterEventId = 0) =>
    ApiClient.get<ResearchAgentEvent[]>(`/api/research-agent/sessions/${sessionId}/events`, { after_event_id: afterEventId }),
  streamEvents: async (sessionId: string, afterEventId = 0) => {
    const token = getStoredToken()
    const query = afterEventId > 0 ? `?after_event_id=${afterEventId}` : ""
    const response = await fetch(`/api/research-agent/sessions/${sessionId}/events${query}`, {
      headers: {
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      }
    })
    const contentType = response.headers.get("content-type") || ""
    const body = await response.text()

    if (contentType.includes("text/event-stream")) {
      return parseSseEvents(body)
    }

    const parsed = JSON.parse(body) as { data?: ResearchAgentEvent[] }
    return (parsed.data || []).map((event) => ({
      event: event.event_type,
      data: event.payload || {}
    }))
  }
}
