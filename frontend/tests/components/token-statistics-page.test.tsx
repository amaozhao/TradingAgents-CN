import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { TokenStatisticsPage } from "@/features/reports/token-statistics-page"

vi.mock("@/libs/api/usage", () => ({
  getUsageStatistics: vi.fn(async () => ({
    success: true,
    data: {
      total_requests: 1,
      total_input_tokens: 100,
      total_output_tokens: 50,
      total_cost: 0.12,
      cost_by_currency: { CNY: 0.12 },
      by_provider: {},
      by_model: {},
      by_date: {}
    },
    message: "ok"
  })),
  getUsageRecords: vi.fn(async () => ({
    success: true,
    data: {
      records: [
        {
          id: "usage-1",
          timestamp: "2026-06-06T10:00:00Z",
          provider: "minimax",
          model_name: "MiniMax-M1",
          input_tokens: 100,
          output_tokens: 50,
          cost: 0.12,
          session_id: "session-1",
          analysis_type: "single"
        }
      ],
      total: 1
    },
    message: "ok"
  }))
}))

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="chart" />
}))

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("TokenStatisticsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("exports current token statistics and records as json", async () => {
    const user = userEvent.setup()
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test")
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {})
    const click = vi.fn()
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      const element = document.createElementNS("http://www.w3.org/1999/xhtml", tagName) as HTMLAnchorElement
      if (tagName === "a") element.click = click
      return element
    })

    renderWithQueryClient(<TokenStatisticsPage />)

    await screen.findByText("MiniMax-M1")
    await user.click(screen.getByRole("button", { name: "导出统计" }))

    await waitFor(() => expect(createObjectURL).toHaveBeenCalled())
    expect(click).toHaveBeenCalled()

    createObjectURL.mockRestore()
    revokeObjectURL.mockRestore()
  })
})
