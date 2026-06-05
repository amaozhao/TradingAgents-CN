import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { SingleAnalysisPage } from "@/features/analysis/single-analysis-page"

let search = ""

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn()
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
    search = ""
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
})
