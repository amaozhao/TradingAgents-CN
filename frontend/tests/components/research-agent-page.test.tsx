import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ResearchAgentPage } from "@/features/research-agent/research-agent-page"
import { researchAgentApi } from "@/libs/api/research-agent"

vi.mock("@/libs/api/research-agent", () => ({
  researchAgentApi: {
    listSessions: vi.fn(),
    createSession: vi.fn(),
    updateSession: vi.fn(),
    deleteSession: vi.fn(),
    cancelSession: vi.fn(),
    uploadFile: vi.fn(),
    getLiveStatus: vi.fn(),
    haltLive: vi.fn(),
    listMessages: vi.fn(),
    listEvents: vi.fn(),
    appendMessage: vi.fn(),
    streamEvents: vi.fn(),
    subscribeEvents: vi.fn()
  }
}))

describe("ResearchAgentPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, "confirm").mockReturnValue(true)
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({
      success: true,
      data: [
        { session_id: "session-1", title: "储能验证", updated_at: "2026-06-08T11:34:01Z" },
        { session_id: "session-2", title: "白酒研究", updated_at: "2026-06-08T11:33:01Z" }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.createSession).mockResolvedValue({
      success: true,
      data: { session_id: "session-new", title: "Agent session" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.updateSession).mockResolvedValue({
      success: true,
      data: { session_id: "session-1", title: "储能复盘", updated_at: "2026-06-08T11:34:01Z" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.deleteSession).mockResolvedValue({
      success: true,
      data: { status: "deleted", session_id: "session-1" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.getLiveStatus).mockResolvedValue({
      success: true,
      data: {
        global_halted: false,
        brokers: [
          {
            auth: { broker: "ibkr", oauth_token_present: false, is_live_broker: true },
            mandate: null,
            runner: { broker: "ibkr", alive: false, last_tick: null, last_tick_age_seconds: null },
            halted: false
          }
        ]
      },
      message: "ok"
    })
    vi.mocked(researchAgentApi.haltLive).mockResolvedValue({
      success: true,
      data: { halted: true, broker: null, reason: "test" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        { event_id: 1, event_type: "tool_started", payload: { tool_name: "alpha_bench" } },
        { event_id: 2, event_type: "tool_completed", payload: { tool_name: "alpha_bench", result: { ok: true } } },
        { event_id: 3, event_type: "message_completed", payload: { content: "分析完成" } },
        { event_id: 4, event_type: "task_completed", payload: {} }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.appendMessage).mockResolvedValue({
      success: true,
      data: { message_id: "message-1", attempt_id: "attempt-1" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.streamEvents).mockResolvedValue([])
    vi.mocked(researchAgentApi.subscribeEvents).mockReturnValue(vi.fn())
  })

  it("renders the migrated Vibe Agent capability surface", async () => {
    render(<ResearchAgentPage />)

    expect(screen.getByText("Vibe Agent")).toBeInTheDocument()
    expect(screen.getByText("研究与回测")).toBeInTheDocument()
    expect(screen.getByText("跨市场组合回测")).toBeInTheDocument()
    expect(screen.getByText("文档与网页")).toBeInTheDocument()
    expect(screen.getByText("运行时与连接器")).toBeInTheDocument()
    expect(screen.getAllByText("Shadow Account").length).toBeGreaterThan(0)
    expect(screen.getByText("执行步骤")).toBeInTheDocument()
    expect(screen.getByText("Vibe Agent Runtime")).toBeInTheDocument()
    expect(screen.getByText("交易连接器")).toBeInTheDocument()
    expect(screen.getByText("交易连接器运行")).toBeInTheDocument()
    expect(await screen.findByText("储能验证")).toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: /新会话/ }).length).toBeGreaterThan(0)
    expect(screen.getByRole("button", { name: "更多选项" })).toBeInTheDocument()
  })

  it("renames and deletes research sessions through the backend API", async () => {
    const user = userEvent.setup()

    render(<ResearchAgentPage />)
    expect(await screen.findByText("储能验证")).toBeInTheDocument()

    await user.click(screen.getAllByLabelText("重命名会话")[0])
    const input = screen.getByDisplayValue("储能验证")
    await user.clear(input)
    await user.type(input, "储能复盘")
    await user.click(screen.getByLabelText("保存重命名"))

    await waitFor(() => expect(researchAgentApi.updateSession).toHaveBeenCalledWith("session-1", { title: "储能复盘" }))
    expect(await screen.findByText("储能复盘")).toBeInTheDocument()

    await user.click(screen.getAllByLabelText("删除会话")[0])

    await waitFor(() => expect(researchAgentApi.deleteSession).toHaveBeenCalledWith("session-1"))
  })

  it("updates the timeline from live research-agent stream events with readable tool steps", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({
      success: true,
      data: [
        { message_id: "persisted-user", role: "user", content: "分析贵州茅台", metadata: {} },
        { message_id: "persisted-answer", role: "assistant", content: "分析完成", metadata: {} }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        { event_id: 1, event_type: "tool_started", payload: { tool_name: "alpha_bench" } },
        { event_id: 2, event_type: "tool_completed", payload: { tool_name: "alpha_bench", result: { ok: true } } },
        { event_id: 3, event_type: "message_completed", payload: { content: "分析完成" } },
        { event_id: 4, event_type: "task_completed", payload: {} }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.subscribeEvents).mockImplementation((_sessionId, handlers) => {
      queueMicrotask(() => {
        handlers.onEvent({ event: "assistant_delta", data: { content: "开始分析" }, eventId: 1 })
        handlers.onEvent({ event: "tool_started", data: { tool_name: "alpha_bench" }, eventId: 2 })
        handlers.onEvent({ event: "tool_completed", data: { tool_name: "alpha_bench", result: { ok: true } }, eventId: 3 })
        handlers.onEvent({ event: "message_completed", data: { content: "分析完成" }, eventId: 4 })
        handlers.onEvent({ event: "task_completed", data: {}, eventId: 5 })
      })
      return vi.fn()
    })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.type(screen.getByPlaceholderText("例如：Run a backtest, check connector status, or analyze A 股储能板块"), "分析贵州茅台")
    await user.click(screen.getByRole("button", { name: "发送" }))

    await waitFor(() => expect(researchAgentApi.subscribeEvents).toHaveBeenCalled())
    expect(await screen.findByText("分析完成")).toBeInTheDocument()
    expect(screen.getAllByText("Alpha 覆盖检查").length).toBeGreaterThan(0)
    expect(screen.queryByText("[object Object]")).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument())
  })

  it("renders assistant markdown answers instead of plain text", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({
      success: true,
      data: [{ session_id: "markdown-session", title: "connector report", updated_at: "2026-06-09T12:35:01Z" }],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({
      success: true,
      data: [
        {
          message_id: "assistant-md",
          role: "assistant",
          content: "## Trading Connector Profiles\n\n| Profile | Broker |\n|---|---|\n| `ibkr-paper-local` | IBKR |",
          metadata: {}
        }
      ],
      message: "ok"
    })

    render(<ResearchAgentPage />)

    expect(await screen.findByRole("heading", { name: "Trading Connector Profiles" })).toBeInTheDocument()
    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.getByText("ibkr-paper-local")).toBeInTheDocument()
  })

  it("reloads execution steps when switching between persisted Vibe sessions", async () => {
    vi.mocked(researchAgentApi.listEvents).mockImplementation(async (sessionId) => ({
      success: true,
      data: sessionId === "session-1"
        ? [
            { event_id: 1, event_type: "tool_started", payload: { tool_name: "read_url" } },
            { event_id: 2, event_type: "tool_completed", payload: { tool_name: "read_url", preview: "No finance content" } }
          ]
        : [
            { event_id: 1, event_type: "tool_started", payload: { tool_name: "alpha_bench" } },
            { event_id: 2, event_type: "tool_completed", payload: { tool_name: "alpha_bench", preview: "Coverage ok" } }
          ],
      message: "ok"
    }))

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    expect(await screen.findByText("网页读取")).toBeInTheDocument()
    expect(screen.queryByText("Alpha 覆盖检查")).not.toBeInTheDocument()

    await user.click(await screen.findByText("白酒研究"))

    expect(await screen.findByText("Alpha 覆盖检查")).toBeInTheDocument()
    expect(screen.queryByText("网页读取")).not.toBeInTheDocument()
  })

  it("shows a loading state while switching sessions and ignores stale responses", async () => {
    let resolveSession1Messages: ((value: Awaited<ReturnType<typeof researchAgentApi.listMessages>>) => void) | undefined
    vi.mocked(researchAgentApi.listMessages).mockImplementation((sessionId) => {
      if (sessionId === "session-1") {
        return new Promise((resolve) => {
          resolveSession1Messages = resolve
        })
      }
      return Promise.resolve({
        success: true,
        data: [{ message_id: "session-2-user", role: "user", content: "白酒研究内容", metadata: {} }],
        message: "ok"
      })
    })
    vi.mocked(researchAgentApi.listEvents).mockImplementation(async (sessionId) => ({
      success: true,
      data: sessionId === "session-2"
        ? [{ event_id: 1, event_type: "tool_completed", payload: { tool_name: "alpha_bench", preview: "Coverage ok" } }]
        : [{ event_id: 1, event_type: "tool_completed", payload: { tool_name: "read_url", preview: "Stale content" } }],
      message: "ok"
    }))

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    expect(await screen.findByText("正在载入会话")).toBeInTheDocument()
    await user.click(await screen.findByText("白酒研究"))

    expect(await screen.findByText("白酒研究内容")).toBeInTheDocument()
    expect(await screen.findByText("Alpha 覆盖检查")).toBeInTheDocument()

    resolveSession1Messages?.({
      success: true,
      data: [{ message_id: "session-1-user", role: "user", content: "过期的储能内容", metadata: {} }],
      message: "ok"
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByText("过期的储能内容")).not.toBeInTheDocument()
    expect(screen.getByText("白酒研究内容")).toBeInTheDocument()
  })

  it("renders readable execution step summaries instead of raw tool JSON", async () => {
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        {
          event_id: 1,
          event_type: "tool_completed",
          payload: {
            tool_name: "load_skill",
            result: JSON.stringify({
              status: "ok",
              content: "<skill name=\"moodtx\">\\n## Overview\\n\\nMoodtx talks the native protocol over TCP."
            })
          }
        },
        {
          event_id: 2,
          event_type: "tool_failed",
          payload: {
            tool_name: "read_url",
            preview: "{\"status\": \"error\", \"error\": \"remote reader request failed: HTTPSConnectionPool"
          }
        },
        {
          event_id: 3,
          event_type: "tool_failed",
          payload: {
            tool_name: "bash",
            elapsed_ms: 1200,
            result: JSON.stringify({
              status: "error",
              exit_code: 1,
              stdout: "=== 阳光电源资金流 ===",
              stderr: "Traceback: request timeout"
            })
          }
        }
      ],
      message: "ok"
    })

    render(<ResearchAgentPage />)

    expect(await screen.findByText("加载能力模块")).toBeInTheDocument()
    expect(screen.getByText(/已加载技能 moodtx/)).toBeInTheDocument()
    expect(screen.getByText(/工具失败：remote reader request failed/)).toBeInTheDocument()
    expect(screen.getByText("命令执行")).toBeInTheDocument()
    expect(screen.getByText(/命令失败（exit 1）/)).toBeInTheDocument()
    expect(screen.queryByText(/\{"status":/)).not.toBeInTheDocument()
  })

  it("recovers completed assistant messages from storage when SSE completion is missed", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.createSession).mockResolvedValue({
      success: true,
      data: { session_id: "session-new", title: "Read https://example.com" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.appendMessage).mockResolvedValue({
      success: true,
      data: { message_id: "message-user", attempt_id: "attempt-fallback" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.subscribeEvents).mockReturnValue(vi.fn())
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({
      success: true,
      data: [
        { message_id: "message-user", role: "user", content: "Read https://example.com", metadata: {} },
        {
          message_id: "message-assistant",
          role: "assistant",
          content: "## Summary\n\nNo finance content.",
          linked_attempt_id: "attempt-fallback",
          metadata: { status: "completed" }
        }
      ],
      message: "ok"
    })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.type(screen.getByPlaceholderText("例如：Run a backtest, check connector status, or analyze A 股储能板块"), "Read https://example.com")
    await user.click(screen.getByRole("button", { name: "发送" }))

    await waitFor(() => expect(researchAgentApi.listMessages).toHaveBeenCalledWith("session-new"))
    expect(await screen.findByRole("heading", { name: "Summary" })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument())
  })
})
