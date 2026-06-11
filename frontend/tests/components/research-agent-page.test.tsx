import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ResearchAgentPage } from "@/features/research-agent/research-agent-page"
import { researchAgentApi } from "@/libs/api/research-agent"
import { useAppStore } from "@/stores/app-store"

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
    createGoal: vi.fn(),
    getGoal: vi.fn(),
    updateGoal: vi.fn(),
    addGoalEvidence: vi.fn(),
    updateGoalStatus: vi.fn(),
    listAttempts: vi.fn(),
    appendMessage: vi.fn(),
    streamEvents: vi.fn(),
    subscribeEvents: vi.fn()
  }
}))

describe("ResearchAgentPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAppStore.setState({ language: "zh-CN" })
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
    vi.mocked(researchAgentApi.listAttempts).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.getGoal).mockResolvedValue({ success: true, data: null, message: "ok" })
    vi.mocked(researchAgentApi.createGoal).mockResolvedValue({
      success: true,
      data: {
        goal_id: "goal-1",
        session_id: "session-1",
        title: "验证储能板块投资机会",
        description: "验证储能板块投资机会",
        criteria: ["保持研究用途，不执行交易下单"],
        status: "active",
        evidence: []
      },
      message: "ok"
    })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        { event_id: 1, event_type: "tool_started", payload: { tool_name: "alpha_bench" } },
        { event_id: 2, event_type: "tool_completed", payload: { tool_name: "alpha_bench", result: { ok: true } } },
        { event_id: 3, event_type: "tool_started", payload: { tool_name: "run_swarm", preview: "preset=investment_committee" } },
        { event_id: 4, event_type: "tool_completed", payload: { tool_name: "run_swarm", preview: "event=run_completed" } },
        { event_id: 5, event_type: "message_completed", payload: { content: "分析完成" } },
        { event_id: 6, event_type: "task_completed", payload: {} }
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

  it("renders the current-project Agent capability surface", async () => {
    render(<ResearchAgentPage />)

    expect(screen.getAllByRole("heading", { name: "智能体" }).length).toBeGreaterThan(0)
    expect(screen.getByText("多市场回测")).toBeInTheDocument()
    expect(screen.getByText("跨市场组合")).toBeInTheDocument()
    expect(screen.getByText("文档与网页研究")).toBeInTheDocument()
    expect(screen.getAllByText("交易连接器").length).toBeGreaterThan(0)
    expect(screen.getByText("分析连接器组合")).toBeInTheDocument()
    expect(screen.getByText("报价与趋势")).toBeInTheDocument()
    expect(screen.getByText("交易日志")).toBeInTheDocument()
    expect(screen.getByText("分析券商导出记录")).toBeInTheDocument()
    expect(screen.getByText("我少赚了多少？")).toBeInTheDocument()
    expect(screen.getByText("生成 Shadow 报告")).toBeInTheDocument()
    expect(screen.getByText("当前项目补充")).toBeInTheDocument()
    expect(screen.getByText("Alpha Zoo 覆盖检查")).toBeInTheDocument()
    expect(screen.getAllByText("Shadow Account").length).toBeGreaterThan(0)
    expect(screen.getByText("执行步骤")).toBeInTheDocument()
    expect(screen.getByText("智能体运行时")).toBeInTheDocument()
    expect(screen.getByText("会话")).toBeInTheDocument()
    expect(screen.queryByText("Sessions")).not.toBeInTheDocument()
    expect(screen.getAllByText("交易连接器").length).toBeGreaterThan(0)
    expect(screen.getByText("交易连接器运行")).toBeInTheDocument()
    expect(await screen.findByText("储能验证")).toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: /新会话/ }).length).toBeGreaterThan(0)
    expect(screen.getByRole("button", { name: "更多选项" })).toBeInTheDocument()
  })

  it("uses the configured language for static Agent page copy", async () => {
    useAppStore.setState({ language: "en-US" })

    render(<ResearchAgentPage />)

    expect(screen.getByText("Multi-market backtest")).toBeInTheDocument()
    expect(screen.getByText("Analyze connector portfolio")).toBeInTheDocument()
    expect(screen.getByText("Quote and trend")).toBeInTheDocument()
    expect(screen.getByText("Trade journal")).toBeInTheDocument()
    expect(screen.getByText("How much am I leaving on the table?")).toBeInTheDocument()
    expect(screen.getByText("Generate shadow report")).toBeInTheDocument()
    expect(screen.getByText("Current-project additions")).toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: /New session/ }).length).toBeGreaterThan(0)
    expect(screen.getByPlaceholderText("Example: run a backtest, check connector status, or analyze the A-share energy storage sector")).toBeInTheDocument()
    expect(screen.queryByPlaceholderText("例如：运行回测、检查连接器状态，或分析 A 股储能板块")).not.toBeInTheDocument()
    expect(await screen.findByText("储能验证")).toBeInTheDocument()
  })

  it("sends localized Chinese prompts from examples", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({ success: true, data: [], message: "ok" })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(await screen.findByRole("button", { name: /跨市场组合/ }))

    await waitFor(() => expect(researchAgentApi.appendMessage).toHaveBeenCalled())
    expect(vi.mocked(researchAgentApi.appendMessage).mock.calls.at(-1)?.[1].content).toContain("请用 backtest 工具回测一个风险平价组合")
    expect(vi.mocked(researchAgentApi.appendMessage).mock.calls.at(-1)?.[1].content).not.toContain("Backtest a risk-parity portfolio")
  })

  it("fills the composer from quick actions without sending", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({ success: true, data: [], message: "ok" })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(await screen.findByRole("button", { name: "更多选项" }))
    await user.click(screen.getByRole("button", { name: "分析连接器组合" }))

    const composer = screen.getByPlaceholderText("例如：运行回测、检查连接器状态，或分析 A 股储能板块") as HTMLTextAreaElement
    await waitFor(() => expect(composer.value).toContain("请使用当前选中的 trading connector profile"))
    expect(researchAgentApi.appendMessage).not.toHaveBeenCalled()
  })

  it("keeps English prompts when the Agent page language is English", async () => {
    useAppStore.setState({ language: "en-US" })
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({ success: true, data: [], message: "ok" })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(await screen.findByRole("button", { name: /Cross-market portfolio/ }))

    await waitFor(() => expect(researchAgentApi.appendMessage).toHaveBeenCalled())
    expect(vi.mocked(researchAgentApi.appendMessage).mock.calls.at(-1)?.[1].content).toContain("Backtest a risk-parity portfolio")
    expect(vi.mocked(researchAgentApi.appendMessage).mock.calls.at(-1)?.[1].content).not.toContain("请用 backtest 工具")
  })

  it("renders the persisted research goal ledger for the active session", async () => {
    vi.mocked(researchAgentApi.getGoal).mockResolvedValue({
      success: true,
      data: {
        goal_id: "goal-session-1",
        session_id: "session-1",
        title: "验证储能板块投资机会",
        description: "结合 Alpha、回测和基本面证据验证储能板块机会。",
        criteria: ["覆盖候选股票", "输出风险点"],
        status: "active",
        evidence: [
          { evidence_id: "e-1", kind: "tool", summary: "Alpha coverage 已覆盖 300750 与 阳光电源。" }
        ]
      },
      message: "ok"
    })

    render(<ResearchAgentPage />)

    expect(await screen.findByText("当前研究目标")).toBeInTheDocument()
    expect(await screen.findByText("验证储能板块投资机会")).toBeInTheDocument()
    expect(screen.getByText("active")).toBeInTheDocument()
    expect(screen.getByText("覆盖候选股票")).toBeInTheDocument()
    expect(screen.getByText("Alpha coverage 已覆盖 300750 与 阳光电源。")).toBeInTheDocument()
  })

  it("creates a backend research goal before sending goal-mode prompts", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({ success: true, data: [], message: "ok" })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(screen.getByRole("button", { name: "更多选项" }))
    await user.click(screen.getByRole("button", { name: "研究目标" }))
    await user.type(screen.getByPlaceholderText("描述要绑定到当前会话的研究目标"), "验证储能板块投资机会")
    await user.click(screen.getByRole("button", { name: "发送" }))

    await waitFor(() => expect(researchAgentApi.createGoal).toHaveBeenCalledWith("session-new", expect.objectContaining({
      title: "验证储能板块投资机会",
      description: "验证储能板块投资机会"
    })))
    await waitFor(() => expect(researchAgentApi.appendMessage).toHaveBeenCalledWith("session-new", expect.objectContaining({
      metadata: expect.objectContaining({
        mode: "goal",
        goal_id: "goal-1"
      })
    })))
    expect((await screen.findAllByText("验证储能板块投资机会")).length).toBeGreaterThan(0)
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
        { event_id: 3, event_type: "tool_started", payload: { tool_name: "run_swarm", preview: "preset=investment_committee" } },
        { event_id: 4, event_type: "tool_completed", payload: { tool_name: "run_swarm", preview: "event=run_completed" } },
        { event_id: 5, event_type: "message_completed", payload: { content: "分析完成" } },
        { event_id: 6, event_type: "task_completed", payload: {} }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.subscribeEvents).mockImplementation((_sessionId, handlers) => {
      queueMicrotask(() => {
        handlers.onEvent({ event: "assistant_delta", data: { content: "开始分析" }, eventId: "1" })
        handlers.onEvent({ event: "tool_started", data: { tool_name: "alpha_bench" }, eventId: "2" })
        handlers.onEvent({ event: "tool_started", data: { tool_name: "run_swarm", preview: "preset=investment_committee" }, eventId: "3" })
        handlers.onEvent({ event: "tool_progress", data: { tool_name: "run_swarm", preview: "event=task_started · task=task-a" }, eventId: "4" })
        handlers.onEvent({ event: "tool_completed", data: { tool_name: "alpha_bench", result: { ok: true } }, eventId: "5" })
        handlers.onEvent({ event: "message_completed", data: { content: "分析完成" }, eventId: "6" })
        handlers.onEvent({ event: "task_completed", data: {}, eventId: "7" })
      })
      return vi.fn()
    })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.type(screen.getByPlaceholderText("例如：运行回测、检查连接器状态，或分析 A 股储能板块"), "分析贵州茅台")
    await user.click(screen.getByRole("button", { name: "发送" }))

    await waitFor(() => expect(researchAgentApi.subscribeEvents).toHaveBeenCalled())
    expect(await screen.findByText("分析完成")).toBeInTheDocument()
    expect(screen.getAllByText("Alpha 覆盖检查").length).toBeGreaterThan(0)
    await waitFor(() => expect(screen.getAllByText("智能体团队").length).toBeGreaterThan(0))
    expect(screen.queryByText("[object Object]")).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument())
  })

  it("restores the final answer from store when a new-session stream only receives task completion", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.listAttempts).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({
      success: true,
      data: [
        { message_id: "new-user", role: "user", content: "读取会议纪要", linked_attempt_id: "attempt-1", metadata: {} },
        { message_id: "tool-call", role: "assistant", content: "", linked_attempt_id: "attempt-1", metadata: { tool_calls: [] } },
        { message_id: "final-answer", role: "assistant", content: "会议纪要总结完成", linked_attempt_id: "attempt-1", metadata: {} }
      ],
      message: "ok"
    })
    let streamHandlers: Parameters<typeof researchAgentApi.subscribeEvents>[1] | undefined
    vi.mocked(researchAgentApi.subscribeEvents).mockImplementation((_sessionId, handlers) => {
      streamHandlers = handlers
      return vi.fn()
    })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.type(screen.getByPlaceholderText("例如：运行回测、检查连接器状态，或分析 A 股储能板块"), "读取会议纪要")
    await user.click(screen.getByRole("button", { name: "发送" }))
    await waitFor(() => expect(researchAgentApi.appendMessage).toHaveBeenCalledWith("session-new", expect.objectContaining({
      content: "读取会议纪要"
    })))

    streamHandlers?.onEvent({
      event: "task_completed",
      data: { attempt_id: "attempt-1", status: "completed" },
      eventId: "8"
    })

    expect(await screen.findByText("会议纪要总结完成")).toBeInTheDocument()
    expect(screen.queryByText("tool-call")).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument())
  })

  it("keeps execution steps collapsed by default and expands full tool output on click", async () => {
    const longTraceback = [
      "Traceback (most recent call last):",
      "  File \"/tmp/run.py\", line 42, in <module>",
      "    raise RuntimeError('完整错误内容应该在展开后可见')",
      "RuntimeError: 完整错误内容应该在展开后可见"
    ].join("\n")
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        { event_id: 1, event_type: "tool_started", payload: { tool_name: "bash" } },
        {
          event_id: 2,
          event_type: "tool_failed",
          payload: {
            tool_name: "bash",
            result: { status: "error", exit_code: 1, stderr: longTraceback }
          }
        }
      ],
      message: "ok"
    })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    const step = await screen.findByRole("button", { name: /命令执行/ })
    expect(screen.queryByText(/完整错误内容应该在展开后可见/)).not.toBeInTheDocument()

    await user.click(step)

    expect(await screen.findByText(/完整错误内容应该在展开后可见/)).toBeInTheDocument()
    expect(screen.getByText(/Traceback \(most recent call last\):/)).toBeInTheDocument()
  })

  it("shows degraded web search as data-limited instead of completed", async () => {
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        { event_id: 1, event_type: "tool_started", payload: { tool_name: "web_search" } },
        {
          event_id: 2,
          event_type: "tool_completed",
          payload: {
            tool_name: "web_search",
            result: {
              tool: "web_search",
              status: "degraded",
              error_type: "ConnectTimeout",
              error: "外部网络连接超时，未能建立连接"
            }
          }
        }
      ],
      message: "ok"
    })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    const step = await screen.findByRole("button", { name: /网页搜索/ })
    expect(screen.getByText("数据受限")).toBeInTheDocument()

    await user.click(step)

    expect(await screen.findByText(/数据受限：外部网络连接超时/)).toBeInTheDocument()
  })

  it("shows concrete market data limitations from nested history reason", async () => {
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        { event_id: 1, event_type: "tool_started", payload: { tool_name: "market_data_lookup" } },
        {
          event_id: 2,
          event_type: "tool_completed",
          payload: {
            tool_name: "market_data_lookup",
            result: {
              tool: "market_data_lookup",
              symbol: "600519",
              status: "degraded",
              history: {
                status: "degraded",
                reason: "A 股行情数据未取得可用价格序列：AKShare、BaoStock 没有返回足够数据。"
              }
            }
          }
        }
      ],
      message: "ok"
    })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    const step = await screen.findByRole("button", { name: /market_data_lookup/ })
    expect(screen.getByText("数据受限")).toBeInTheDocument()

    await user.click(step)

    expect(await screen.findByText(/数据受限：A 股行情数据未取得可用价格序列/)).toBeInTheDocument()
  })

  it("humanizes persisted timeout failures", async () => {
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        {
          event_id: 1,
          event_type: "attempt.failed",
          payload: { error: "ConnectTimeout" }
        }
      ],
      message: "ok"
    })

    render(<ResearchAgentPage />)

    expect(await screen.findByText(/外部模型或网络服务请求超时：ConnectTimeout/)).toBeInTheDocument()
  })

  it("sends the composer with Enter and keeps Shift+Enter for new lines", async () => {
    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    const composer = screen.getByPlaceholderText("例如：运行回测、检查连接器状态，或分析 A 股储能板块")
    await user.click(composer)
    await user.type(composer, "第一行")
    await user.keyboard("{Shift>}{Enter}{/Shift}")

    expect(composer).toHaveValue("第一行\n")
    expect(researchAgentApi.appendMessage).not.toHaveBeenCalled()

    await user.type(composer, "第二行")
    await user.keyboard("{Enter}")

    await waitFor(() => expect(researchAgentApi.appendMessage).toHaveBeenCalled())
    expect(vi.mocked(researchAgentApi.appendMessage).mock.calls.at(-1)?.[1].content).toBe("第一行\n第二行")
  })

  it("auto-grows the composer until the maximum height before scrolling", async () => {
    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    const composer = screen.getByPlaceholderText("例如：运行回测、检查连接器状态，或分析 A 股储能板块") as HTMLTextAreaElement
    Object.defineProperty(composer, "scrollHeight", { configurable: true, value: 96 })

    await user.type(composer, "第一行{Shift>}{Enter}{/Shift}第二行{Shift>}{Enter}{/Shift}第三行")

    await waitFor(() => expect(composer.style.height).toBe("96px"))
    expect(composer.style.overflowY).toBe("hidden")

    Object.defineProperty(composer, "scrollHeight", { configurable: true, value: 220 })
    await user.type(composer, "{Shift>}{Enter}{/Shift}第四行")

    await waitFor(() => expect(composer.style.height).toBe("128px"))
    expect(composer.style.overflowY).toBe("auto")
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

  it("reloads execution steps when switching between persisted research-agent sessions", async () => {
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

  it("allows switching to a completed session while another session is running", async () => {
    vi.mocked(researchAgentApi.listMessages).mockImplementation(async (sessionId) => ({
      success: true,
      data: sessionId === "session-2"
        ? [{ message_id: "session-2-user", role: "user", content: "已完成的白酒研究", metadata: {} }]
        : [],
      message: "ok"
    }))
    vi.mocked(researchAgentApi.listEvents).mockImplementation(async (sessionId) => ({
      success: true,
      data: sessionId === "session-2"
        ? [{ event_id: 1, event_type: "tool_completed", payload: { tool_name: "alpha_bench", preview: "Coverage ok" } }]
        : [],
      message: "ok"
    }))
    vi.mocked(researchAgentApi.subscribeEvents).mockReturnValue(vi.fn())

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await screen.findByText("储能验证")
    await user.type(screen.getByPlaceholderText("例如：运行回测、检查连接器状态，或分析 A 股储能板块"), "运行一个长任务")
    await user.click(screen.getByRole("button", { name: "发送" }))
    await waitFor(() => expect(screen.getByText("智能体正在工作...")).toBeInTheDocument())

    await user.click(screen.getByText("白酒研究"))

    expect(await screen.findByText("已完成的白酒研究")).toBeInTheDocument()
    expect(await screen.findByText("Alpha 覆盖检查")).toBeInTheDocument()
    expect(screen.queryByText("智能体正在工作...")).not.toBeInTheDocument()
  })

  it("restores the running indicator when opening a persisted running session", async () => {
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({
      success: true,
      data: [{ message_id: "running-user", role: "user", content: "继续分析储能", metadata: {} }],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [{ event_id: 9, event_type: "tool_started", payload: { tool_name: "alpha_bench" } }],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listAttempts).mockResolvedValue({
      success: true,
      data: [{
        attempt_id: "attempt-running",
        session_id: "session-1",
        status: "running",
        created_at: "2026-06-09T12:00:00Z",
        started_at: "2026-06-09T12:00:01Z",
        completed_at: null,
        result: null
      }],
      message: "ok"
    })

    render(<ResearchAgentPage />)

    expect(await screen.findByText("继续分析储能")).toBeInTheDocument()
    expect(await screen.findByText("智能体正在工作...")).toBeInTheDocument()
    expect(vi.mocked(researchAgentApi.subscribeEvents)).toHaveBeenCalledWith(
      "session-1",
      expect.any(Object),
      "9"
    )
  })

  it("renders a restored running session's completed assistant reply", async () => {
    let streamHandlers: Parameters<typeof researchAgentApi.subscribeEvents>[1] | undefined
    let messageCallCount = 0
    vi.mocked(researchAgentApi.listMessages).mockImplementation(async () => {
      messageCallCount += 1
      const baseMessages = [{ message_id: "running-user", role: "user", content: "继续分析储能", metadata: {} }]
      return {
        success: true,
        data: messageCallCount >= 3
          ? [
              ...baseMessages,
              {
                message_id: "assistant-done",
                role: "assistant",
                content: "## 分析完成\n\n储能板块研究已完成。",
                linked_attempt_id: "attempt-running",
                metadata: { status: "completed" }
              }
            ]
          : baseMessages,
        message: "ok"
      }
    })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [{ event_id: 9, event_type: "tool_started", payload: { tool_name: "alpha_bench" } }],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listAttempts).mockResolvedValue({
      success: true,
      data: [{
        attempt_id: "attempt-running",
        session_id: "session-1",
        status: "running",
        created_at: "2026-06-09T12:00:00Z",
        started_at: "2026-06-09T12:00:01Z",
        completed_at: null,
        result: null
      }],
      message: "ok"
    })
    vi.mocked(researchAgentApi.subscribeEvents).mockImplementation((_sessionId, handlers) => {
      streamHandlers = handlers
      return vi.fn()
    })

    render(<ResearchAgentPage />)

    expect(await screen.findByText("智能体正在工作...")).toBeInTheDocument()
    streamHandlers?.onEvent({
      event: "attempt.completed",
      data: { attempt_id: "attempt-running", status: "completed" },
      eventId: "10"
    })

    expect(await screen.findByRole("heading", { name: "分析完成" })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument())
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

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    expect(await screen.findByText("加载能力模块")).toBeInTheDocument()
    expect(screen.queryByText(/已加载技能 moodtx/)).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /加载能力模块/ }))
    expect(screen.getByText(/已加载技能 moodtx/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /网页读取/ }))
    expect(screen.getByText(/工具失败：remote reader request failed/)).toBeInTheDocument()

    expect(screen.getByText("命令执行")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /命令执行/ }))
    expect(screen.getByText(/命令失败（exit 1）/)).toBeInTheDocument()
    expect(screen.queryByText(/\{"status":/)).not.toBeInTheDocument()
  })

  it("shows execution steps only for the latest completed attempt in a session", async () => {
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({
      success: true,
      data: [
        { message_id: "user-1", role: "user", content: "第一次问题", linked_attempt_id: "attempt-old", metadata: {} },
        { message_id: "answer-1", role: "assistant", content: "第一次回答", linked_attempt_id: "attempt-old", metadata: {} },
        { message_id: "user-2", role: "user", content: "第二次问题", linked_attempt_id: "attempt-new", metadata: {} },
        { message_id: "answer-2", role: "assistant", content: "第二次回答", linked_attempt_id: "attempt-new", metadata: {} }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listAttempts).mockResolvedValue({
      success: true,
      data: [
        {
          attempt_id: "attempt-old",
          session_id: "session-1",
          status: "completed",
          created_at: "2026-06-09T12:00:00Z",
          started_at: "2026-06-09T12:00:01Z",
          completed_at: "2026-06-09T12:01:00Z",
          result: { content: "第一次回答" }
        },
        {
          attempt_id: "attempt-new",
          session_id: "session-1",
          status: "completed",
          created_at: "2026-06-09T12:02:00Z",
          started_at: "2026-06-09T12:02:01Z",
          completed_at: "2026-06-09T12:03:00Z",
          result: { content: "第二次回答" }
        }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        { event_id: 1, event_type: "tool_completed", payload: { tool_name: "web_search", attempt_id: "attempt-old", preview: "旧搜索结果" } },
        { event_id: 2, event_type: "tool_completed", payload: { tool_name: "read_url", attempt_id: "attempt-new", preview: "新网页读取" } },
        { event_id: 3, event_type: "message_completed", payload: { attempt_id: "attempt-new", content: "第二次回答" } }
      ],
      message: "ok"
    })

    render(<ResearchAgentPage />)

    expect(await screen.findByText("第二次回答")).toBeInTheDocument()
    expect(screen.getByText("网页读取")).toBeInTheDocument()
    expect(screen.queryByText("网页搜索")).not.toBeInTheDocument()
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

    await user.type(screen.getByPlaceholderText("例如：运行回测、检查连接器状态，或分析 A 股储能板块"), "Read https://example.com")
    await user.click(screen.getByRole("button", { name: "发送" }))

    await waitFor(() => expect(researchAgentApi.listMessages).toHaveBeenCalledWith("session-new"))
    expect(await screen.findByRole("heading", { name: "Summary" })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument())
  })
})
