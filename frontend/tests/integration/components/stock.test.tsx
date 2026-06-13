import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { initialStockWorkflowTools, toolsFromEvents } from "@/features/agent/event"
import { defaultStockModels, enabledModels } from "@/features/research/models"
import {
  createStockDraft,
  buildStockPayload,
  localDateKey,
  stockDraftSummary
} from "@/features/research/payload"
import { ResearchAgentPage } from "@/features/research-agent/research-agent-page"
import { normalizeStockSymbol, stockSymbolError } from "@/features/research/symbol"
import { configApi, type LLMConfig } from "@/libs/api/config"
import { researchAgentApi } from "@/libs/api/research-agent"
import { useAppStore } from "@/stores/app-store"

let latestSubscription:
  | Parameters<typeof researchAgentApi.subscribeEvents>[1]
  | undefined

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
    resumeLive: vi.fn(),
    authorizeLive: vi.fn(),
    startLiveRunner: vi.fn(),
    stopLiveRunner: vi.fn(),
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

vi.mock("@/libs/api/config", () => ({
  configApi: {
    getLLMConfigs: vi.fn()
  }
}))

async function openSession(title: string) {
  const label = await screen.findByText(title)
  const button = label.closest("button")
  expect(button).not.toBeNull()
  await userEvent.setup().click(button as HTMLButtonElement)
}

const models: LLMConfig[] = [
  {
    provider: "dashscope",
    model_name: "qwen-turbo",
    model_display_name: "Qwen Turbo",
    enabled: true,
    max_tokens: 8000,
    temperature: 0.7,
    timeout: 60,
    retry_times: 2,
    created_at: "2026-06-11T00:00:00Z",
    updated_at: "2026-06-11T00:00:00Z"
  },
  {
    provider: "dashscope",
    model_name: "qwen-max",
    model_display_name: "Qwen Max",
    enabled: true,
    max_tokens: 16000,
    temperature: 0.4,
    timeout: 60,
    retry_times: 2,
    created_at: "2026-06-11T00:00:00Z",
    updated_at: "2026-06-11T00:00:00Z"
  },
  {
    provider: "openai",
    model_name: "disabled-model",
    model_display_name: "Disabled",
    enabled: false,
    max_tokens: 4000,
    temperature: 0.2,
    timeout: 60,
    retry_times: 2,
    created_at: "2026-06-11T00:00:00Z",
    updated_at: "2026-06-11T00:00:00Z"
  }
]

describe("stock analysis shared frontend logic", () => {
  it("normalizes A-share, Hong Kong, and US symbols consistently", () => {
    expect(normalizeStockSymbol("SH600519", "A股")).toEqual({ symbol: "600519", market: "A股" })
    expect(normalizeStockSymbol("0700.HK", "A股")).toEqual({ symbol: "0700", market: "港股" })
    expect(normalizeStockSymbol("aapl.us", "A股")).toEqual({ symbol: "AAPL", market: "美股" })
  })

  it("returns market-specific symbol validation errors", () => {
    expect(stockSymbolError("AAPL", "A股")).toContain("A股代码")
    expect(stockSymbolError("600519", "A股")).toBe("")
    expect(stockSymbolError("0700", "港股")).toBe("")
    expect(stockSymbolError("AAPL", "美股")).toBe("")
  })

  it("builds the direct invocation payload from a submitted draft", () => {
    const draft = {
      ...createStockDraft("2026-06-11"),
      symbol: "600519",
      quick: "qwen-turbo",
      deep: "qwen-max",
      prompt: "  重点解释估值和风险  ",
      analysts: ["market", "fundamentals"]
    }
    const normalized = normalizeStockSymbol(draft.symbol, draft.market)

    expect(buildStockPayload(draft, normalized)).toEqual({
      mode: "single",
      symbol: "600519",
      market_type: "A股",
      analysis_date: "2026-06-11",
      research_depth: "标准",
      selected_analysts: ["market", "fundamentals"],
      include_sentiment: true,
      include_risk: true,
      language: "zh-CN",
      quick_analysis_model: "qwen-turbo",
      deep_analysis_model: "qwen-max",
      custom_prompt: "重点解释估值和风险",
      wait_for_completion: true,
      wait_timeout_seconds: 900
    })
    expect(stockDraftSummary(draft, normalized)).toContain("600519 / A股 / 标准")
  })

  it("keeps queued single-stock tool events in the running state", () => {
    const [tool] = toolsFromEvents([
      {
        event: "tool_completed",
        eventId: "event-1",
        data: {
          tool_name: "stock_analysis",
          result: {
            tool: "stock_analysis",
            status: "queued",
            task_id: "task-600519"
          }
        }
      }
    ])

    expect(tool?.name).toBe("stock_analysis")
    expect(tool?.status).toBe("running")
    expect(tool?.taskId).toBe("task-600519")
  })

  it("builds only the active initial stock workflow step before SSE events arrive", () => {
    const tools = initialStockWorkflowTools({
      mode: "single",
      symbol: "000938",
      market_type: "A股",
      selected_analysts: ["market", "fundamentals", "news"],
      include_sentiment: true,
      include_risk: true
    })

    expect(tools).toHaveLength(1)
    expect(tools[0]).toMatchObject({
      id: "stock_analysis:validate_input",
      title: "参数校验",
      status: "running"
    })
  })

  it("uses the browser local date for default analysis dates", () => {
    expect(localDateKey(new Date(2026, 5, 11, 0, 30))).toBe("2026-06-11")
  })

  it("selects only enabled models and derives quick/deep defaults", () => {
    const enabled = enabledModels(models)

    expect(enabled.map((model) => model.model_name)).toEqual(["qwen-turbo", "qwen-max"])
    expect(defaultStockModels(enabled)).toEqual({ quick: "qwen-turbo", deep: "qwen-max" })
    expect(defaultStockModels(enabled.slice(0, 1))).toEqual({ quick: "qwen-turbo", deep: "qwen-turbo" })
  })

  it("keeps quick/deep model defaults on the same provider when providers differ", () => {
    const enabled = enabledModels([
      {
        provider: "minimax",
        model_name: "MiniMax-M3",
        model_display_name: "MiniMax-M3",
        enabled: true,
        max_tokens: 8000,
        temperature: 0.7,
        timeout: 60,
        retry_times: 2
      },
      {
        provider: "zhipu",
        model_name: "glm-4",
        model_display_name: "glm-4",
        enabled: true,
        max_tokens: 8000,
        temperature: 0.7,
        timeout: 60,
        retry_times: 2
      }
    ])

    expect(defaultStockModels(enabled)).toEqual({ quick: "MiniMax-M3", deep: "MiniMax-M3" })
  })
})

describe("ResearchAgentPage stock analysis", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    latestSubscription = undefined
    useAppStore.setState({ language: "zh-CN" })
    vi.spyOn(window, "confirm").mockReturnValue(true)
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.createSession).mockResolvedValue({
      success: true,
      data: { session_id: "session-new", title: "Agent session" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.updateSession).mockResolvedValue({
      success: true,
      data: { session_id: "session-stock", title: "贵州茅台", updated_at: "2026-06-11T10:00:00Z" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.deleteSession).mockResolvedValue({
      success: true,
      data: { status: "deleted", session_id: "session-stock" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.getLiveStatus).mockResolvedValue({
      success: true,
      data: { global_halted: false, brokers: [] },
      message: "ok"
    })
    vi.mocked(researchAgentApi.haltLive).mockResolvedValue({
      success: true,
      data: { halted: true, broker: null, reason: "test" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.resumeLive).mockResolvedValue({
      success: true,
      data: { resumed: true, broker: null, reason: "test" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.authorizeLive).mockResolvedValue({
      success: true,
      data: { broker: "paper", oauth_token_present: true },
      message: "ok"
    })
    vi.mocked(researchAgentApi.startLiveRunner).mockResolvedValue({
      success: true,
      data: { broker: "paper", alive: true },
      message: "ok"
    })
    vi.mocked(researchAgentApi.stopLiveRunner).mockResolvedValue({
      success: true,
      data: { broker: "paper", alive: false },
      message: "ok"
    })
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.listAttempts).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.getGoal).mockResolvedValue({ success: true, data: null, message: "ok" })
    vi.mocked(researchAgentApi.createGoal).mockResolvedValue({
      success: true,
      data: {
        goal_id: "goal-1",
        session_id: "session-stock",
        title: "验证贵州茅台",
        description: "验证贵州茅台",
        criteria: [],
        status: "active",
        evidence: []
      },
      message: "ok"
    })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({ success: true, data: [], message: "ok" })
    vi.mocked(researchAgentApi.appendMessage).mockResolvedValue({
      success: true,
      data: { message_id: "message-1", attempt_id: "attempt-1" },
      message: "ok"
    })
    vi.mocked(researchAgentApi.streamEvents).mockResolvedValue([])
    vi.mocked(researchAgentApi.subscribeEvents).mockImplementation((_sessionId, handlers) => {
      latestSubscription = handlers
      return vi.fn()
    })
    vi.mocked(configApi.getLLMConfigs).mockResolvedValue([
      {
        provider: "dashscope",
        model_name: "qwen-turbo",
        model_display_name: "通义千问 Turbo",
        max_tokens: 2000,
        temperature: 0.7,
        timeout: 60,
        retry_times: 2,
        enabled: true
      },
      {
        provider: "dashscope",
        model_name: "qwen-max",
        model_display_name: "通义千问 Max",
        max_tokens: 8000,
        temperature: 0.7,
        timeout: 60,
        retry_times: 2,
        enabled: true
      }
    ])
  })

  it("submits single-stock configuration through structured metadata", async () => {
    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(await screen.findByRole("button", { name: "更多选项" }))
    await user.click(screen.getByRole("button", { name: /个股分析/ }))
    await screen.findByText("通义千问 Turbo (qwen-turbo)")
    await user.type(screen.getByPlaceholderText("600519 / 0700.HK / AAPL"), "600519")
    await user.type(screen.getByPlaceholderText("例如：重点解释估值和风险"), "重点解释估值")
    await user.click(screen.getByRole("button", { name: /开始分析/ }))

    await waitFor(() => expect(researchAgentApi.appendMessage).toHaveBeenCalled())
    const payload = vi.mocked(researchAgentApi.appendMessage).mock.calls.at(-1)?.[1]
    expect(payload?.content).toContain("个股分析")
    expect(payload?.metadata).toMatchObject({
      mode: "stock_analysis_workflow",
      tool_name: "stock_analysis",
      tool_arguments: {
        mode: "single",
        symbol: "600519",
        market_type: "A股",
        analysis_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        research_depth: "标准",
        selected_analysts: ["market", "fundamentals"],
        include_sentiment: true,
        include_risk: true,
        language: "zh-CN",
        quick_analysis_model: "qwen-turbo",
        deep_analysis_model: "qwen-max",
        custom_prompt: "重点解释估值",
        wait_for_completion: true,
        wait_timeout_seconds: 900
      }
    })
    expect(screen.getByText("已提交，执行步骤和报告链接会在右侧更新。")).toBeInTheDocument()
  })

  it("opens the single-stock card without sending and reuses the existing draft", async () => {
    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(await screen.findByRole("button", { name: "更多选项" }))
    await user.click(screen.getByRole("button", { name: /个股分析/ }))
    expect(await screen.findByLabelText("个股分析配置")).toBeInTheDocument()
    expect(researchAgentApi.appendMessage).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "更多选项" }))
    await user.click(screen.getByRole("button", { name: /个股分析/ }))

    expect(screen.getAllByLabelText("个股分析配置")).toHaveLength(1)
    expect(researchAgentApi.appendMessage).not.toHaveBeenCalled()
  })

  it("saves single-stock summary to the composer without calling the tool", async () => {
    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(await screen.findByRole("button", { name: "更多选项" }))
    await user.click(screen.getByRole("button", { name: /个股分析/ }))
    await screen.findByText("通义千问 Turbo (qwen-turbo)")
    await user.type(screen.getByPlaceholderText("600519 / 0700.HK / AAPL"), "600519")
    await user.click(screen.getByRole("button", { name: /保存到输入框/ }))

    const composer = screen.getByPlaceholderText("例如：运行回测、检查连接器状态，或分析 A 股储能板块") as HTMLTextAreaElement
    expect(composer.value).toContain("请进行个股分析：600519 / A股 / 标准")
    expect(researchAgentApi.appendMessage).not.toHaveBeenCalled()
  })

  it("disables A-share social analyst selection in the card", async () => {
    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(await screen.findByRole("button", { name: "更多选项" }))
    await user.click(screen.getByRole("button", { name: /个股分析/ }))

    expect(await screen.findByText("A 股默认禁用社媒分析。")).toBeInTheDocument()
    expect(screen.getByRole("checkbox", { name: "社媒" })).toBeDisabled()
  })

  it("keeps the stock entry unavailable while an Agent attempt is running", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({
      success: true,
      data: [{ session_id: "session-stock", title: "贵州茅台", updated_at: "2026-06-11T10:00:00Z" }],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listAttempts).mockResolvedValue({
      success: true,
      data: [
        {
          attempt_id: "attempt-running",
          session_id: "session-stock",
          status: "running",
          created_at: "2026-06-11T10:00:00Z",
          started_at: "2026-06-11T10:00:01Z"
        }
      ],
      message: "ok"
    })

    render(<ResearchAgentPage />)
    await openSession("贵州茅台")

    expect(await screen.findByText("运行中")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "更多选项" })).toBeDisabled()
  })

  it("shows stock task and report links from stage events after submission", async () => {
    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(await screen.findByRole("button", { name: "更多选项" }))
    await user.click(screen.getByRole("button", { name: /个股分析/ }))
    await screen.findByText("通义千问 Turbo (qwen-turbo)")
    await user.type(screen.getByPlaceholderText("600519 / 0700.HK / AAPL"), "600519")
    await user.click(screen.getByRole("button", { name: /开始分析/ }))
    await waitFor(() => expect(latestSubscription).toBeDefined())

    latestSubscription?.onEvent({
      event: "stock_analysis.stage",
      data: {
        tool_name: "stock_analysis",
        attempt_id: "attempt-1",
        task_id: "task-600519",
        report_url: "/reports/view/task-600519",
        stage: "analysis_task",
        title: "个股分析任务",
        status: "running",
        progress: 35,
        message: "个股分析任务已提交。"
      }
    })

    expect(await screen.findByText("任务：task-600519")).toBeInTheDocument()
    expect(screen.getByText("个股分析任务")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /查看任务/ })).toHaveAttribute(
      "href",
      "/tasks?task_id=task-600519"
    )
    expect(screen.getByRole("link", { name: /查看报告/ })).toHaveAttribute(
      "href",
      "/reports/view/task-600519"
    )
  })

  it("replays persisted single-stock metadata as a status card", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({
      success: true,
      data: [{ session_id: "session-stock", title: "贵州茅台", updated_at: "2026-06-11T10:00:00Z" }],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({
      success: true,
      data: [
        {
          message_id: "message-stock",
          role: "user",
          content: "个股分析：600519 / A股 / 标准",
          created_at: "2026-06-11T10:00:01Z",
          metadata: {
            source: "research-agent-page",
            mode: "stock_analysis_workflow",
            tool_name: "stock_analysis",
            tool_arguments: {
              mode: "single",
              symbol: "600519",
              market_type: "A股",
              analysis_date: "2026-06-11",
              research_depth: "标准",
              selected_analysts: ["market", "fundamentals"],
              include_sentiment: true,
              include_risk: true,
              language: "zh-CN",
              quick_analysis_model: "qwen-turbo",
              deep_analysis_model: "qwen-max",
              custom_prompt: "重点解释估值",
              wait_for_completion: true,
              wait_timeout_seconds: 900
            }
          }
        }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        {
          event_id: 1,
          event_type: "stock_analysis.stage",
          payload: {
            tool_name: "stock_analysis",
            attempt_id: "attempt-stock",
            task_id: "task-600519",
            report_url: "/reports/view/task-600519",
            stage: "agent_summary",
            title: "Agent 总结",
            status: "completed",
            progress: 100,
            message: "个股分析已完成。"
          }
        }
      ],
      message: "ok"
    })

    render(<ResearchAgentPage />)
    await openSession("贵州茅台")

    expect(await screen.findByLabelText("个股分析历史配置")).toBeInTheDocument()
    expect(screen.getByText("600519 / A股 / 标准 / market+fundamentals / 情绪+风险 / qwen-turbo -> qwen-max")).toBeInTheDocument()
    expect(screen.getByText("重点解释估值")).toBeInTheDocument()
    expect(screen.getByText("任务：task-600519")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /查看报告/ })).toHaveAttribute(
      "href",
      "/reports/view/task-600519"
    )
  })

  it("replays failed single-stock stages without completed-report wording", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({
      success: true,
      data: [{ session_id: "session-stock", title: "贵州茅台", updated_at: "2026-06-11T10:00:00Z" }],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({
      success: true,
      data: [
        {
          message_id: "message-stock",
          role: "user",
          content: "个股分析：600519 / A股 / 标准",
          metadata: {
            source: "research-agent-page",
            mode: "stock_analysis_workflow",
            tool_name: "stock_analysis",
            tool_arguments: {
              mode: "single",
              symbol: "600519",
              market_type: "A股",
              analysis_date: "2026-06-11",
              research_depth: "标准",
              selected_analysts: ["market", "fundamentals"],
              include_sentiment: true,
              include_risk: true,
              language: "zh-CN",
              quick_analysis_model: "qwen-turbo",
              deep_analysis_model: "qwen-max",
              custom_prompt: "",
              wait_for_completion: true,
              wait_timeout_seconds: 900
            }
          }
        },
        {
          message_id: "message-assistant",
          role: "assistant",
          content: "行情数据源无可用历史数据。 任务 ID：task-600519",
          linked_attempt_id: "attempt-stock"
        }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        {
          event_id: 1,
          event_type: "stock_analysis.stage",
          payload: {
            tool_name: "stock_analysis",
            attempt_id: "attempt-stock",
            task_id: "task-600519",
            stage: "analysis_task",
            title: "个股分析任务",
            status: "failed",
            progress: 35,
            message: "行情数据源无可用历史数据。"
          }
        },
        {
          event_id: 2,
          event_type: "stock_analysis.failed",
          payload: { attempt_id: "attempt-stock", task_id: "task-600519", status: "failed" }
        }
      ],
      message: "ok"
    })

    render(<ResearchAgentPage />)
    await openSession("贵州茅台")

    expect(await screen.findByLabelText("个股分析历史配置")).toBeInTheDocument()
    expect(screen.getByText("当前状态：失败")).toBeInTheDocument()
    expect(screen.getAllByText(/行情数据源无可用历史数据/).length).toBeGreaterThan(0)
    expect(screen.getByText("个股分析任务")).toBeInTheDocument()
    expect(screen.queryByText(/个股分析报告已生成/)).not.toBeInTheDocument()
    expect(screen.queryByText("当前状态：已完成")).not.toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /查看报告/ })).not.toBeInTheDocument()
  })

  it("replays timed-out single-stock stages as still running", async () => {
    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({
      success: true,
      data: [{ session_id: "session-stock", title: "贵州茅台", updated_at: "2026-06-11T10:00:00Z" }],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listMessages).mockResolvedValue({
      success: true,
      data: [
        {
          message_id: "message-stock",
          role: "user",
          content: "个股分析：600519 / A股 / 标准",
          metadata: {
            source: "research-agent-page",
            mode: "stock_analysis_workflow",
            tool_name: "stock_analysis",
            tool_arguments: {
              mode: "single",
              symbol: "600519",
              market_type: "A股",
              analysis_date: "2026-06-11",
              research_depth: "标准",
              selected_analysts: ["market", "fundamentals"],
              include_sentiment: true,
              include_risk: true,
              language: "zh-CN",
              quick_analysis_model: "qwen-turbo",
              deep_analysis_model: "qwen-max",
              custom_prompt: "",
              wait_for_completion: true,
              wait_timeout_seconds: 30
            }
          }
        },
        {
          message_id: "message-assistant",
          role: "assistant",
          content: "个股分析任务仍在执行，已返回任务链接。 任务 ID：task-600519",
          linked_attempt_id: "attempt-stock"
        }
      ],
      message: "ok"
    })
    vi.mocked(researchAgentApi.listEvents).mockResolvedValue({
      success: true,
      data: [
        {
          event_id: 1,
          event_type: "stock_analysis.stage",
          payload: {
            tool_name: "stock_analysis",
            attempt_id: "attempt-stock",
            task_id: "task-600519",
            report_url: "/reports/view/task-600519",
            stage: "wait_bounded",
            title: "等待窗口",
            status: "running",
            progress: 40,
            message: "个股分析任务仍在执行，已返回任务链接。"
          }
        },
        {
          event_id: 2,
          event_type: "stock_analysis.timed_out",
          payload: { attempt_id: "attempt-stock", task_id: "task-600519", status: "processing" }
        }
      ],
      message: "ok"
    })

    render(<ResearchAgentPage />)
    await openSession("贵州茅台")

    expect(await screen.findByLabelText("个股分析历史配置")).toBeInTheDocument()
    expect(screen.getByText("当前状态：运行中")).toBeInTheDocument()
    expect(screen.getAllByText(/个股分析任务仍在执行/).length).toBeGreaterThan(0)
    expect(screen.getByText("等待窗口")).toBeInTheDocument()
    expect(screen.queryByText("当前状态：已完成")).not.toBeInTheDocument()
    expect(screen.queryByText(/个股分析报告已生成/)).not.toBeInTheDocument()
  })

  it("blocks single-stock submission when no enabled model exists", async () => {
    vi.mocked(configApi.getLLMConfigs).mockResolvedValue([])

    const user = userEvent.setup()
    render(<ResearchAgentPage />)

    await user.click(await screen.findByRole("button", { name: "更多选项" }))
    await user.click(screen.getByRole("button", { name: /个股分析/ }))
    await user.type(screen.getByPlaceholderText("600519 / 0700.HK / AAPL"), "600519")
    await screen.findByText("没有启用模型，请先在设置中配置模型。")

    expect(screen.getByRole("button", { name: /开始分析/ })).toBeDisabled()
    expect(researchAgentApi.appendMessage).not.toHaveBeenCalled()
  })

  it("renders readable execution step summaries instead of raw tool JSON", async () => {
    const batchResult = {
      mode: "batch",
      tool: "batch_stock_analysis",
      links: { batch: "/tasks?batch_id=batch-1" },
      status: "completed",
      message: "批量分析已完成。",
      summary: "批量分析状态：2/2 成功，0 失败，0 取消。",
      accepted: true,
      batch_id: "batch-1",
      children: [
        {
          status: "completed",
          symbol: "000002",
          task_id: "task-000002",
          progress: 100,
          report_url: "/reports/view/report-000002"
        },
        {
          status: "completed",
          symbol: "000338",
          task_id: "task-000338",
          progress: 100,
          report_url: "/reports/view/report-000338"
        }
      ],
      progress: 100,
      task_ids: ["task-000002", "task-000338"],
      total_tasks: 2,
      failed_tasks: 0,
      cancelled_tasks: 0,
      completed_tasks: 2
    }

    vi.mocked(researchAgentApi.listSessions).mockResolvedValue({
      success: true,
      data: [{ session_id: "session-stock", title: "贵州茅台", updated_at: "2026-06-11T10:00:00Z" }],
      message: "ok"
    })
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
        },
        {
          event_id: 4,
          event_type: "tool_completed",
          payload: {
            tool_name: "single_stock_analysis",
            result: {
              tool: "single_stock_analysis",
              status: "queued",
              task_id: "task-600519",
              symbol: "600519",
              research_depth: "标准"
            }
          }
        },
        {
          event_id: 5,
          event_type: "tool_completed",
          payload: {
            tool_name: "stock_analysis_status",
            result: {
              tool: "stock_analysis_status",
              status: "running",
              task_id: "task-600519",
              progress: 45,
              current_step: "基本面分析师"
            }
          }
        },
        {
          event_id: 6,
          event_type: "tool_completed",
          payload: {
            tool_name: "stock_analysis_report",
            result: {
              tool: "stock_analysis_report",
              status: "completed",
              task_id: "task-600519",
              summary: "贵州茅台基本面稳健。"
            }
          }
        },
        {
          event_id: 7,
          event_type: "tool_completed",
          payload: {
            tool_name: "batch_stock_analysis",
            result: batchResult
          }
        },
        {
          event_id: 8,
          event_type: "message_completed",
          payload: {
            content: JSON.stringify(batchResult)
          }
        }
      ],
      message: "ok"
    })

    const user = userEvent.setup()
    render(<ResearchAgentPage />)
    await openSession("贵州茅台")

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

    await user.click(screen.getByRole("button", { name: /个股分析运行中/ }))
    expect(screen.getByText(/600519（标准） 任务 task-600519已提交到分析队列/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /个股分析进度/ }))
    expect(screen.getByText(/任务 task-600519进度 45%：基本面分析师/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /个股分析报告/ }))
    expect(screen.getByText(/个股分析报告已生成：贵州茅台基本面稳健/)).toBeInTheDocument()
    expect(screen.queryByText(/"task_id": "task-600519"/)).not.toBeInTheDocument()

    expect(screen.getAllByText(/批量分析已完成/).length).toBeGreaterThan(0)
    await user.click(screen.getByRole("button", { name: /批量分析/ }))
    expect(screen.getAllByText(/批量分析状态：2\/2 成功，0 失败，0 取消/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/"children"/)).not.toBeInTheDocument()
    expect(screen.queryByText(/"task_ids"/)).not.toBeInTheDocument()
  })
})
