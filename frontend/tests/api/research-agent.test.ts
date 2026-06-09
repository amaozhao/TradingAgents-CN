import { afterEach, describe, expect, it, vi } from "vitest"

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

class MockEventSource {
  static instances: MockEventSource[] = []

  listeners = new Map<string, Array<(event: MessageEvent) => void>>()
  onopen: (() => void) | null = null
  onerror: ((event: Event) => void) | null = null
  url: string

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    const listeners = this.listeners.get(type) || []
    listeners.push(listener)
    this.listeners.set(type, listeners)
  }

  emit(type: string, data: Record<string, unknown>, lastEventId = "1") {
    for (const listener of this.listeners.get(type) || []) {
      listener({ data: JSON.stringify(data), lastEventId } as MessageEvent)
    }
  }

  close = vi.fn()
}

describe("researchAgentApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    MockEventSource.instances = []
  })

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

  it("maps Vibe backend answer truncation and swarm SSE events into page events", () => {
    vi.stubGlobal("EventSource", MockEventSource)
    const onEvent = vi.fn()

    const stop = researchAgentApi.subscribeEvents("session-1", { onEvent })
    const source = MockEventSource.instances[0]

    source.emit("answer_truncated", { content: "partial answer" }, "2")
    source.emit("swarm.started", { run_id: "swarm-1", preset: "investment_committee" }, "3")
    source.emit("swarm.event", { run_id: "swarm-1", event: { type: "task_started", task_id: "task-a" } }, "4")
    source.emit("swarm.event", { run_id: "swarm-1", event: { type: "run_completed" } }, "5")
    stop()

    expect(onEvent).toHaveBeenCalledWith({
      event: "assistant_delta",
      data: { content: "partial answer" },
      eventId: 2
    })
    expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({
      event: "tool_started",
      data: expect.objectContaining({ tool_name: "run_swarm", preview: expect.stringContaining("investment_committee") }),
      eventId: 3
    }))
    expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({
      event: "tool_progress",
      data: expect.objectContaining({ tool_name: "run_swarm", preview: expect.stringContaining("task_started") }),
      eventId: 4
    }))
    expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({
      event: "tool_completed",
      data: expect.objectContaining({ tool_name: "run_swarm", preview: expect.stringContaining("run_completed") }),
      eventId: 5
    }))
    expect(source.close).toHaveBeenCalled()
  })
})
