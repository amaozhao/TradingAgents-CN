export type AgentMessageType = "user" | "answer" | "error" | "tool_call" | "tool_result" | "system"

export type AgentMessage = {
  id: string
  type: AgentMessageType
  content: string
  timestamp: number
  tool?: string
  status?: "running" | "ok" | "warning" | "error" | "skipped"
  elapsedMs?: number
  metadata?: Record<string, unknown>
}

export type ToolState = {
  id: string
  name: string
  title?: string
  status: "running" | "ok" | "warning" | "error" | "skipped"
  preview?: string
  artifactId?: string
  taskId?: string
  reportUrl?: string
  elapsedMs?: number
}
