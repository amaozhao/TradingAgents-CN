import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { StockDetailPage } from "@/features/stocks/stock-detail-page"
import { clearAllCache } from "@/libs/api/cache"
import { stockSyncApi } from "@/libs/api/stock-sync"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() })
}))

vi.mock("@/libs/api/favorites", () => ({
  favoritesApi: {
    check: vi.fn(async () => ({ success: true, data: { is_favorite: false }, message: "ok" })),
    add: vi.fn(),
    remove: vi.fn()
  }
}))

vi.mock("@/libs/api/stocks", () => ({
  stocksApi: {
    getQuote: vi.fn(async () => ({
      success: true,
      data: { code: "600519", name: "贵州茅台", market: "CN", price: 1272.86, change_percent: 0.38, updated_at: "2026-06-06T10:00:00Z" },
      message: "ok"
    })),
    getFundamentals: vi.fn(async () => ({
      success: true,
      data: { name: "贵州茅台", market: "CN", industry: "白酒", sector: "消费" },
      message: "ok"
    })),
    getKline: vi.fn(async () => ({ success: true, data: { items: [] }, message: "ok" })),
    getNews: vi.fn(async () => ({ success: true, data: { items: [] }, message: "ok" }))
  }
}))

vi.mock("@/libs/api/stock-sync", () => ({
  stockSyncApi: {
    syncSingle: vi.fn()
  }
}))

vi.mock("@/libs/api/cache", () => ({
  clearAllCache: vi.fn()
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

describe("StockDetailPage", () => {
  it("syncs the current stock with selected sync options", async () => {
    const user = userEvent.setup()
    vi.mocked(stockSyncApi.syncSingle).mockResolvedValue({
      success: true,
      data: {
        symbol: "600519",
        realtime_sync: { success: true, message: "ok" },
        historical_sync: null,
        financial_sync: null,
        basic_sync: null,
        overall_success: true
      },
      message: "ok"
    })

    renderWithQueryClient(<StockDetailPage code="600519" />)

    await user.click(await screen.findByRole("button", { name: "同步数据" }))
    const dialog = screen.getByRole("dialog", { name: "同步股票数据" })
    await user.click(within(dialog).getByRole("button", { name: "开始同步" }))

    await waitFor(() =>
      expect(stockSyncApi.syncSingle).toHaveBeenCalledWith({
        symbol: "600519",
        sync_realtime: true,
        sync_historical: false,
        sync_financial: false,
        sync_basic: false,
        data_source: "tushare",
        days: 365
      })
    )
  })

  it("clears cache and refreshes stock detail data", async () => {
    const user = userEvent.setup()
    vi.mocked(clearAllCache).mockResolvedValue({ success: true, data: {}, message: "ok" })

    renderWithQueryClient(<StockDetailPage code="600519" />)

    await user.click(await screen.findByRole("button", { name: "清除缓存" }))
    await user.click(screen.getByRole("button", { name: "确认清除" }))

    await waitFor(() => expect(clearAllCache).toHaveBeenCalledTimes(1))
  })
})
