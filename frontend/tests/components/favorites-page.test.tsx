import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { FavoritesPage } from "@/features/favorites/favorites-page"
import { stockSyncApi } from "@/libs/api/stock-sync"

vi.mock("@/libs/api/favorites", () => ({
  favoritesApi: {
    list: vi.fn(async () => ({
      success: true,
      data: [
        { symbol: "000001", stock_name: "平安银行", market: "A股", tags: ["银行"], added_at: "2026-06-01T00:00:00Z" },
        { symbol: "AAPL", stock_name: "Apple", market: "美股", tags: ["科技"], added_at: "2026-06-01T00:00:00Z" }
      ],
      message: "ok"
    })),
    tags: vi.fn(async () => ({ success: true, data: ["银行", "科技"], message: "ok" })),
    add: vi.fn(),
    remove: vi.fn(),
    syncRealtime: vi.fn()
  }
}))

vi.mock("@/libs/api/stock-sync", () => ({
  stockSyncApi: {
    syncBatch: vi.fn()
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

describe("FavoritesPage", () => {
  it("batch syncs selected A-share favorites", async () => {
    const user = userEvent.setup()
    vi.mocked(stockSyncApi.syncBatch).mockResolvedValue({
      success: true,
      data: {
        total: 1,
        symbols: ["000001"],
        historical_sync: { success_count: 1, error_count: 0, total_records: 10, message: "ok" },
        financial_sync: null,
        basic_sync: null
      },
      message: "ok"
    })

    renderWithQueryClient(<FavoritesPage />)

    await screen.findByText(/000001/)
    await user.click(screen.getByLabelText("选择 000001"))
    await user.click(screen.getByRole("button", { name: "批量同步数据 (1)" }))
    await user.click(screen.getByRole("button", { name: "开始同步" }))

    await waitFor(() => expect(stockSyncApi.syncBatch).toHaveBeenCalledTimes(1))
    expect(stockSyncApi.syncBatch).toHaveBeenCalledWith({
      symbols: ["000001"],
      sync_historical: true,
      sync_financial: false,
      sync_basic: false,
      data_source: "tushare",
      days: 365
    })
  })
})
