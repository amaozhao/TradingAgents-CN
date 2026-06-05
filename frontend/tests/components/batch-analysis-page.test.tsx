import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { BatchAnalysisPage } from "@/features/analysis/batch-analysis-page"
import { analysisApi } from "@/libs/api/analysis"

const push = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams("")
}))

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn()
  }
}))

vi.mock("@/libs/api/analysis", () => ({
  analysisApi: {
    startBatchAnalysis: vi.fn()
  }
}))

vi.mock("@/libs/api/config", () => ({
  configApi: {
    getDefaultModels: vi.fn().mockResolvedValue({
      quick_analysis_model: "qwen-plus",
      deep_analysis_model: "qwen-max"
    })
  }
}))

describe("BatchAnalysisPage", () => {
  it("submits the full Vue-compatible batch analysis payload", async () => {
    const user = userEvent.setup()
    vi.mocked(analysisApi.startBatchAnalysis).mockResolvedValue({
      success: true,
      data: { batch_id: "batch-1", total_tasks: 2, task_ids: ["task-1", "task-2"], status: "pending" },
      message: "ok"
    })

    render(<BatchAnalysisPage />)

    await user.clear(screen.getByLabelText("批次标题"))
    await user.type(screen.getByLabelText("批次标题"), "银行板块分析")
    await user.type(screen.getByLabelText("批次描述"), "对银行股做批量复盘")
    await user.type(screen.getByLabelText("股票代码列表"), "000001\n000001\nAAPL\nBAD!")

    expect(await screen.findByText("000001")).toBeInTheDocument()
    expect(screen.getByText("AAPL")).toBeInTheDocument()
    expect(screen.getByText("BAD!")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /开始批量分析/ }))

    await waitFor(() => expect(analysisApi.startBatchAnalysis).toHaveBeenCalledTimes(1))
    expect(analysisApi.startBatchAnalysis).toHaveBeenCalledWith({
      title: "银行板块分析",
      description: "对银行股做批量复盘",
      symbols: ["000001", "AAPL"],
      stock_codes: ["000001", "AAPL"],
      parameters: {
        market_type: undefined,
        research_depth: "3",
        selected_analysts: ["market", "fundamentals"],
        include_sentiment: true,
        include_risk: true,
        language: "zh-CN",
        quick_analysis_model: "qwen-plus",
        deep_analysis_model: "qwen-max"
      }
    })
    expect(push).toHaveBeenCalledWith("/tasks?batch_id=batch-1")
  })
})
