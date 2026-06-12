import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ReportsPage } from "@/features/reports/reports-page"
import { deleteReport, fetchReports } from "@/features/reports/report-api"

vi.mock("@/features/reports/report-api", () => ({
  fetchReports: vi.fn(),
  deleteReport: vi.fn()
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ReportsPage />
    </QueryClientProvider>
  )
}

describe("ReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, "confirm").mockReturnValue(true)
    vi.mocked(fetchReports).mockResolvedValue({
      reports: [
        {
          id: "report-1",
          title: "贵州茅台(600519) 分析报告",
          stock_code: "600519",
          stock_name: "贵州茅台",
          type: "single",
          status: "completed",
          created_at: "2026-06-12T10:00:00+08:00"
        }
      ],
      total: 1
    })
    vi.mocked(deleteReport).mockResolvedValue({})
  })

  it("deletes a report from the list actions", async () => {
    renderPage()

    expect(await screen.findByText("贵州茅台(600519) 分析报告")).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole("button", { name: /删除/ }))

    expect(window.confirm).toHaveBeenCalledWith("确认删除报告“贵州茅台(600519) 分析报告”？")
    expect(vi.mocked(deleteReport).mock.calls[0]?.[0]).toBe("report-1")
    await waitFor(() => expect(fetchReports).toHaveBeenCalledTimes(2))
  })
})
