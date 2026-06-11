import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { SingleAnalysisPage } from "@/features/analysis/single-analysis-page"
import { analysisApi } from "@/libs/api/analysis"

let search = ""
const push = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push
  }),
  useSearchParams: () => new URLSearchParams(search)
}))

vi.mock("@/libs/api/analysis", () => ({
  analysisApi: {
    startSingleAnalysis: vi.fn()
  }
}))

vi.mock("@/libs/api/config", () => ({
  configApi: {
    getLLMConfigs: vi.fn(async () => [])
  }
}))

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("SingleAnalysisPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    search = ""
    vi.mocked(analysisApi.startSingleAnalysis).mockResolvedValue({
      success: true,
      data: { task_id: "legacy-task-600519" },
      message: "ok"
    })
  })

  it("uses the app date picker instead of the browser native date input", () => {
    renderWithQueryClient(<SingleAnalysisPage />)

    const dateControl = screen.getByLabelText("分析日期")

    expect(dateControl.tagName).toBe("BUTTON")
    expect(dateControl).not.toHaveAttribute("type", "date")
  })

  it("prefills the stock symbol from the URL query", () => {
    search = "symbol=600519"

    renderWithQueryClient(<SingleAnalysisPage />)

    expect(screen.getByLabelText("股票代码")).toHaveValue("600519")
  })

  it("shows Vue-compatible analysis controls", () => {
    renderWithQueryClient(<SingleAnalysisPage />)

    expect(screen.getByText("分析深度")).toBeInTheDocument()
    expect(screen.getByText("分析师团队")).toBeInTheDocument()
    expect(screen.getByText("高级配置")).toBeInTheDocument()
    expect(screen.getByText("快速分析模型")).toBeInTheDocument()
    expect(screen.getByText("深度决策模型")).toBeInTheDocument()
    expect(screen.getByText("情绪分析")).toBeInTheDocument()
    expect(screen.getByText("风险评估")).toBeInTheDocument()
  })

  it("keeps submitting through the legacy single analysis endpoint shape", async () => {
    const user = userEvent.setup()
    renderWithQueryClient(<SingleAnalysisPage />)

    await user.type(screen.getByLabelText("股票代码"), "600519")
    await user.click(screen.getByRole("button", { name: /开始智能分析/ }))

    await waitFor(() => expect(analysisApi.startSingleAnalysis).toHaveBeenCalled())
    expect(analysisApi.startSingleAnalysis).toHaveBeenCalledWith({
      symbol: "600519",
      stock_code: "600519",
      parameters: expect.objectContaining({
        market_type: "A股",
        research_depth: "标准",
        selected_analysts: ["market", "fundamentals"],
        include_sentiment: true,
        include_risk: true,
        language: "zh-CN",
        quick_analysis_model: "qwen-turbo",
        deep_analysis_model: "qwen-max"
      })
    })
    const submitted = vi.mocked(analysisApi.startSingleAnalysis).mock.calls[0][0]
    expect(submitted).not.toHaveProperty("metadata")
    expect(submitted).not.toHaveProperty("tool_name")
    expect(push).toHaveBeenCalledWith("/tasks")
  })
})
