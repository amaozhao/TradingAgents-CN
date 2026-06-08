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

export const researchAgentApi = {
  createSession: (payload: { title?: string }) =>
    ApiClient.post<ResearchSession>("/api/research-agent/sessions", payload),
  listSessions: () => ApiClient.get<ResearchSession[]>("/api/research-agent/sessions"),
  listMessages: (sessionId: string) =>
    ApiClient.get<ResearchMessage[]>(`/api/research-agent/sessions/${sessionId}/messages`),
  appendMessage: (sessionId: string, payload: { role: string; content: string; metadata?: Record<string, unknown> }) =>
    ApiClient.post<ResearchMessage>(`/api/research-agent/sessions/${sessionId}/messages`, payload),
  listEvents: (sessionId: string, afterEventId = 0) =>
    ApiClient.get<Record<string, unknown>[]>(`/api/research-agent/sessions/${sessionId}/events`, { after_event_id: afterEventId })
}
