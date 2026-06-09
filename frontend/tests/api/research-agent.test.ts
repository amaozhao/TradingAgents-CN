import { describe, expect, it, vi } from "vitest"

import request from "@/libs/api/request"
import { researchAgentApi } from "@/libs/api/research-agent"

vi.mock("@/libs/api/request", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn()
  }
}))

describe("researchAgentApi", () => {
  it("loads persisted Vibe execution events from the backend history endpoint", async () => {
    vi.mocked(request.get).mockResolvedValueOnce([
      { event_id: 1, event_type: "tool_started", payload: { tool_name: "read_url" } }
    ])

    const response = await researchAgentApi.listEvents("session-1", 7)

    expect(request.get).toHaveBeenCalledWith("/api/vibe-history/sessions/session-1/events", {
      params: { after_event_id: 7 },
      skipErrorHandler: true
    })
    expect(response.data).toEqual([
      { event_id: 1, event_type: "tool_started", payload: { tool_name: "read_url" } }
    ])
  })
})
