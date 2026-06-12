import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ScreeningPage } from "@/features/screening/screening-page"
import { screeningApi } from "@/libs/api/screening"

const push = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push })
}))

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

vi.mock("@/libs/api/favorites", () => ({
  favoritesApi: {
    list: vi.fn(async () => []),
    add: vi.fn(),
    remove: vi.fn()
  }
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
    push.mockClear()
    vi.spyOn(console, "error").mockImplementation(() => {})
  })

  it("accepts raw industries responses from the FastAPI screening endpoint", async () => {
    renderWithQueryClient(<ScreeningPage />)

    await waitFor(() => {
      expect(screen.getByText(/当前数据源：akshare/)).toBeInTheDocument()
    })
    expect(console.error).not.toHaveBeenCalledWith(expect.stringContaining("Query data cannot be undefined"))
  })

  it("sends selected screening results to batch analysis", async () => {
    const user = userEvent.setup()
    vi.mocked(screeningApi.run).mockResolvedValue({
      success: true,
      data: {
        items: [
          { code: "000001", close: 12.2, pct_chg: 1.2, amount: 100000000, ma20: 12, rsi14: 55 },
          { code: "600519", close: 1500, pct_chg: -0.5, amount: 200000000, ma20: 1490, rsi14: 48 }
        ],
        total: 2
      },
      message: "ok"
    })

    renderWithQueryClient(<ScreeningPage />)

    await user.click(screen.getAllByRole("button", { name: /开始筛选/ })[0])
    await screen.findByRole("link", { name: "000001" })

    await user.click(screen.getByLabelText("选择 000001"))
    await user.click(screen.getAllByRole("button", { name: "批量分析 (1)" })[0])

    expect(push).toHaveBeenCalledWith("/agent?mode=batch&stocks=000001")
  })

  it("keeps Vue-compatible screening filters visible", async () => {
    renderWithQueryClient(<ScreeningPage />)

    expect(screen.getByText("市场类型")).toBeInTheDocument()
    expect(screen.getByText("市值范围")).toBeInTheDocument()
    expect(screen.getByText("市盈率 (PE)")).toBeInTheDocument()
    expect(screen.getByText("市净率 (PB)")).toBeInTheDocument()
    expect(screen.getByText("ROE (%)")).toBeInTheDocument()
    expect(screen.getByText("涨跌幅 (%)")).toBeInTheDocument()
    expect(screen.getByText("成交量")).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/当前数据源：akshare/)).toBeInTheDocument())
  })
})
