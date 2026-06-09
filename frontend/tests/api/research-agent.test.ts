import { afterEach, describe, expect, it, vi } from "vitest"

import request from "@/libs/api/request"
import { researchAgentApi } from "@/libs/api/research-agent"

vi.mock("@/libs/api/request", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
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

  it("loads persisted research-agent execution events from the backend events endpoint", async () => {
    vi.mocked(request.get).mockResolvedValueOnce({
      success: true,
      data: [
        { event_id: 1, event_type: "tool_started", payload: { tool_name: "read_url" } }
      ],
      message: "ok"
    })

    const response = await researchAgentApi.listEvents("session-1", 7)

    expect(request.get).toHaveBeenCalledWith("/api/research-agent/sessions/session-1/events", {
      params: { after_event_id: 7 },
      skipErrorHandler: true
    })
    expect(response.data).toEqual([
      { event_id: 1, event_type: "tool_started", payload: { tool_name: "read_url" } }
    ])
  })

  it("uses current-project research goal endpoints", async () => {
    vi.mocked(request.get).mockResolvedValueOnce({ success: true, data: null, message: "ok" })
    vi.mocked(request.post).mockResolvedValueOnce({
      success: true,
      data: { goal_id: "goal-1", title: "验证储能板块投资机会", status: "active" },
      message: "ok"
    })

    await researchAgentApi.getGoal("session-1")
    await researchAgentApi.createGoal("session-1", {
      title: "验证储能板块投资机会",
      description: "验证储能板块投资机会",
      criteria: ["输出风险点"]
    })

    expect(request.get).toHaveBeenCalledWith("/api/research-agent/sessions/session-1/goal")
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/sessions/session-1/goal", {
      title: "验证储能板块投资机会",
      description: "验证储能板块投资机会",
      criteria: ["输出风险点"]
    })
  })

  it("uses current-project swarm runtime endpoints", async () => {
    vi.mocked(request.get).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(request.post).mockResolvedValue({
      success: true,
      data: { run_id: "run-1", preset: "research_team", status: "running" },
      message: "ok"
    })

    await researchAgentApi.listSwarmPresets()
    await researchAgentApi.createSwarmRun({
      preset: "research_team",
      variables: { topic: "储能" },
      session_id: "session-1"
    })
    await researchAgentApi.listSwarmRunEvents("run-1", 3)
    await researchAgentApi.cancelSwarmRun("run-1")
    await researchAgentApi.retrySwarmRun("run-1")

    expect(request.get).toHaveBeenCalledWith("/api/research-agent/swarm/presets")
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/swarm/runs", {
      preset: "research_team",
      variables: { topic: "储能" },
      session_id: "session-1"
    })
    expect(request.get).toHaveBeenCalledWith("/api/research-agent/swarm/runs/run-1/events", {
      params: { after_event_id: 3 }
    })
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/swarm/runs/run-1/cancel")
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/swarm/runs/run-1/retry")
  })

  it("uses current-project live safety endpoints", async () => {
    vi.mocked(request.get).mockResolvedValue({ success: true, data: { global_halted: false, brokers: [] }, message: "ok" })
    vi.mocked(request.post).mockResolvedValue({ success: true, data: {}, message: "ok" })

    await researchAgentApi.getLiveStatus()
    await researchAgentApi.haltLive({ reason: "halt", session_id: "session-1" })
    await researchAgentApi.resumeLive({ reason: "resume", session_id: "session-1" })
    await researchAgentApi.authorizeLive({ broker: "paper", session_id: "session-1" })
    await researchAgentApi.startLiveRunner({ broker: "paper", session_id: "session-1" })
    await researchAgentApi.stopLiveRunner({ broker: "paper", session_id: "session-1" })
    await researchAgentApi.commitMandate({ proposal: { broker: "paper" }, session_id: "session-1" })

    expect(request.get).toHaveBeenCalledWith("/api/research-agent/live/status")
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/live/halt", { reason: "halt", session_id: "session-1" })
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/live/resume", { reason: "resume", session_id: "session-1" })
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/live/authorize", { broker: "paper", session_id: "session-1" })
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/live/runner/start", { broker: "paper", session_id: "session-1" })
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/live/runner/stop", { broker: "paper", session_id: "session-1" })
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/mandate/commit", { proposal: { broker: "paper" }, session_id: "session-1" })
  })

  it("uses current-project upload and artifact endpoints", async () => {
    vi.mocked(request.post).mockClear()
    vi.mocked(request.get).mockClear()
    vi.mocked(request.post).mockResolvedValue({ success: true, data: { status: "uploaded", file_id: "artifact-1", artifact_id: "artifact-1", filename: "memo.txt" }, message: "ok" })
    vi.mocked(request.get).mockResolvedValue({ success: true, data: [], message: "ok" })
    const file = new File(["memo"], "memo.txt", { type: "text/plain" })

    await researchAgentApi.uploadFile(file, "session-1")
    await researchAgentApi.getArtifact("artifact-1")
    await researchAgentApi.listArtifacts("session-1", "upload")

    expect(request.post).toHaveBeenCalledWith("/api/research-agent/upload", expect.any(FormData), {
      headers: { "Content-Type": "multipart/form-data" }
    })
    const form = vi.mocked(request.post).mock.calls.at(-1)?.[1] as FormData
    expect(form.get("session_id")).toBe("session-1")
    expect(request.get).toHaveBeenCalledWith("/api/research-agent/artifacts/artifact-1")
    expect(request.get).toHaveBeenCalledWith("/api/research-agent/sessions/session-1/artifacts", {
      params: { artifact_type: "upload" }
    })
  })

  it("uses current-project run and shadow artifact endpoints", async () => {
    vi.mocked(request.get).mockClear()
    vi.mocked(request.get).mockResolvedValue({ success: true, data: {}, message: "ok" })

    await researchAgentApi.listRuns()
    await researchAgentApi.getRun("run-1")
    await researchAgentApi.getRunCode("run-1")
    await researchAgentApi.getRunPine("run-1")
    await researchAgentApi.getShadowReport("shadow-1")

    expect(request.get).toHaveBeenCalledWith("/api/research-agent/runs")
    expect(request.get).toHaveBeenCalledWith("/api/research-agent/runs/run-1")
    expect(request.get).toHaveBeenCalledWith("/api/research-agent/runs/run-1/code")
    expect(request.get).toHaveBeenCalledWith("/api/research-agent/runs/run-1/pine")
    expect(request.get).toHaveBeenCalledWith("/api/research-agent/shadow-reports/shadow-1")
  })

  it("uses current-project skill catalog endpoint", async () => {
    vi.mocked(request.get).mockClear()
    vi.mocked(request.get).mockResolvedValue({ success: true, data: [], message: "ok" })

    await researchAgentApi.listSkills()

    expect(request.get).toHaveBeenCalledWith("/api/research-agent/skills")
  })

  it("uses current-project capabilities and settings endpoints", async () => {
    vi.mocked(request.get).mockClear()
    vi.mocked(request.put).mockClear()
    vi.mocked(request.post).mockClear()
    vi.mocked(request.get).mockResolvedValue({ success: true, data: {}, message: "ok" })
    vi.mocked(request.put).mockResolvedValue({ success: true, data: {}, message: "ok" })
    vi.mocked(request.post).mockResolvedValue({ success: true, data: {}, message: "ok" })

    await researchAgentApi.getCapabilities()
    await researchAgentApi.getLlmSettings()
    await researchAgentApi.updateLlmSettings({ model: "openai/test" })
    await researchAgentApi.getDataSourceSettings()
    await researchAgentApi.updateDataSourceSettings({ tushare: true })
    await researchAgentApi.rejectSystemShutdown()
    await researchAgentApi.rejectRunShutdown("run-1")

    expect(request.get).toHaveBeenCalledWith("/api/research-agent/api")
    expect(request.get).toHaveBeenCalledWith("/api/research-agent/settings/llm")
    expect(request.put).toHaveBeenCalledWith("/api/research-agent/settings/llm", { values: { model: "openai/test" } })
    expect(request.get).toHaveBeenCalledWith("/api/research-agent/settings/data-sources")
    expect(request.put).toHaveBeenCalledWith("/api/research-agent/settings/data-sources", { values: { tushare: true } })
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/system/shutdown")
    expect(request.post).toHaveBeenCalledWith("/api/research-agent/runs/run-1/shutdown")
  })

  it("maps research-agent answer truncation and swarm SSE events into page events", () => {
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
      eventId: "2"
    })
    expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({
      event: "tool_started",
      data: expect.objectContaining({ tool_name: "run_swarm", preview: expect.stringContaining("investment_committee") }),
      eventId: "3"
    }))
    expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({
      event: "tool_progress",
      data: expect.objectContaining({ tool_name: "run_swarm", preview: expect.stringContaining("task_started") }),
      eventId: "4"
    }))
    expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({
      event: "tool_completed",
      data: expect.objectContaining({ tool_name: "run_swarm", preview: expect.stringContaining("run_completed") }),
      eventId: "5"
    }))
    expect(source.close).toHaveBeenCalled()
  })
})
