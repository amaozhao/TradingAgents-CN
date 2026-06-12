import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PaperTradingPage } from "@/features/paper/paper-trading-page"
import { paperApi } from "@/libs/api/paper"

let search = ""
const push = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(search)
}))

vi.mock("@/libs/api/paper", () => ({
  paperApi: {
    getAccount: vi.fn(),
    getPositions: vi.fn(),
    getOrders: vi.fn(),
    placeOrder: vi.fn(),
    resetAccount: vi.fn()
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

describe("PaperTradingPage", () => {
  beforeEach(() => {
    search = ""
    push.mockClear()
    vi.mocked(paperApi.getAccount).mockResolvedValue({
      success: true,
      message: "ok",
      data: {
        account: {
          cash: { CNY: 100000, HKD: 50000, USD: 20000 },
          positions_value: { CNY: 12000, HKD: 0, USD: 1500 },
          equity: { CNY: 112000, HKD: 50000, USD: 21500 },
          realized_pnl: { CNY: 1200, HKD: 0, USD: -100 },
          updated_at: "2026-06-05T00:00:00Z"
        },
        positions: []
      }
    })
    vi.mocked(paperApi.getPositions).mockResolvedValue({
      success: true,
      message: "ok",
      data: {
        items: [
          { code: "000001", name: "平安银行", market: "CN", currency: "CNY", quantity: 100, available_qty: 100, avg_cost: 10, last_price: 12 },
          { code: "AAPL", name: "Apple", market: "US", currency: "USD", quantity: 5, available_qty: 5, avg_cost: 100, last_price: 110 }
        ]
      }
    })
    vi.mocked(paperApi.getOrders).mockResolvedValue({
      success: true,
      message: "ok",
      data: {
        items: [
          { code: "000001", name: "平安银行", market: "CN", side: "buy", quantity: 100, price: 12, amount: 1200, status: "filled", created_at: "2026-06-05T00:00:00Z", analysis_id: "analysis-1" },
          { code: "AAPL", name: "Apple", market: "US", side: "sell", quantity: 1, price: 110, amount: 110, status: "filled", created_at: "2026-06-05T00:00:00Z" }
        ]
      }
    })
    vi.mocked(paperApi.placeOrder).mockResolvedValue({
      success: true,
      data: {
        order: { code: "000001", side: "sell", quantity: 100, price: 12, amount: 1200, status: "filled", created_at: "2026-06-05T00:00:00Z" }
      },
      message: "ok"
    })
  })

  it("shows market tabs, filters positions and exposes position actions", async () => {
    const user = userEvent.setup()
    renderWithQueryClient(<PaperTradingPage />)

    expect(await screen.findByRole("tab", { name: "A股" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "港股" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "美股" })).toBeInTheDocument()
    expect(await screen.findAllByText(/平安银行/)).toHaveLength(2)
    expect(screen.queryByText(/Apple/)).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "分析 000001" }))
    expect(push).toHaveBeenCalledWith("/agent?mode=stock&symbol=000001&market=A%E8%82%A1")

    await user.click(screen.getByRole("button", { name: "卖出 000001" }))
    await user.click(screen.getByRole("button", { name: "确认卖出" }))

    await waitFor(() => expect(paperApi.placeOrder).toHaveBeenCalledWith({ side: "sell", code: "000001", quantity: 100 }))
  })

  it("prefills the order dialog from URL query parameters", async () => {
    search = "code=AAPL&side=sell&quantity=3&analysis_id=analysis-9"
    const user = userEvent.setup()

    renderWithQueryClient(<PaperTradingPage />)

    expect(await screen.findByRole("dialog", { name: "下市场单" })).toBeInTheDocument()
    expect(screen.getByLabelText("代码")).toHaveValue("AAPL")
    expect(screen.getByLabelText("数量")).toHaveValue(3)
    expect(screen.getByText(/来自分析报告：analysis-9/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "提交" }))

    await waitFor(() => expect(paperApi.placeOrder).toHaveBeenCalledWith({ code: "AAPL", side: "sell", quantity: 3, analysis_id: "analysis-9" }))
  })
})
