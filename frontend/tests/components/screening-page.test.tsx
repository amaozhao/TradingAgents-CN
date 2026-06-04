import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ScreeningPage } from "@/features/screening/screening-page"

vi.mock("@/libs/api/screening", () => ({
  screeningApi: {
    getIndustries: vi.fn(async () => ({
      industries: [{ value: "银行", label: "银行", count: 10 }],
      total: 1,
      source: "akshare"
    })),
    run: vi.fn()
  }
}))

vi.mock("@/libs/api/sync", () => ({
  getCurrentDataSource: vi.fn(async () => ({
    success: true,
    data: { name: "akshare", priority: 2, description: "开源金融数据库" },
    message: "ok"
  }))
}))

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("ScreeningPage", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {})
  })

  it("accepts raw industries responses from the FastAPI screening endpoint", async () => {
    renderWithQueryClient(<ScreeningPage />)

    await waitFor(() => {
      expect(screen.getByText(/当前数据源：akshare/)).toBeInTheDocument()
    })
    expect(console.error).not.toHaveBeenCalledWith(expect.stringContaining("Query data cannot be undefined"))
  })
})
