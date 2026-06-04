import { expect, test } from "@playwright/test"
import { installNotificationMocks } from "./helpers"

test.beforeEach(async ({ page }) => {
  await installNotificationMocks(page)
  await page.addInitScript(() => {
    window.localStorage.setItem("auth-token", "access.payload.sig")
    window.localStorage.setItem("refresh-token", "refresh.payload.sig")
    window.localStorage.setItem("user-info", JSON.stringify({ username: "admin" }))
    window.localStorage.setItem("config-wizard-completed", "true")
  })
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: mockPayload(url.pathname), message: "ok" })
    })
  })
})

test("opens stock detail dynamic route and screening page", async ({ page }) => {
  await page.goto("/stocks/000001")
  await expect(page.getByRole("heading", { name: "平安银行" })).toBeVisible()
  await expect(page.getByText("价格K线")).toBeVisible()

  await page.goto("/screening")
  await expect(page.getByRole("heading", { name: "股票筛选" })).toBeVisible()
  await page.getByRole("button", { name: "开始筛选" }).click()
  await expect(page.getByText("筛选结果", { exact: true })).toBeVisible()

  await page.goto("/favorites")
  await expect(page.getByRole("heading", { name: "我的自选股" })).toBeVisible()

  await page.goto("/paper")
  await expect(page.getByRole("heading", { name: "模拟交易" })).toBeVisible()
})

function mockPayload(path: string) {
  if (path.endsWith("/quote")) {
    return { symbol: "000001", name: "平安银行", market: "A股", price: 12.34, change_percent: 1.23, amount: 123456789, turnover_rate: 1.1, prev_close: 12.1, amplitude: 2.2, trade_date: "2026-06-04", updated_at: "2026-06-04T10:00:00Z" }
  }
  if (path.endsWith("/fundamentals")) {
    return { symbol: "000001", name: "平安银行", industry: "银行", sector: "金融", total_mv: 120000000000, pe_ttm: 6.5, pb_mrq: 0.8, roe: 11.2 }
  }
  if (path.endsWith("/kline")) {
    return { symbol: "000001", period: "day", limit: 120, adj: "none", items: [{ time: "2026-06-03", open: 12, close: 12.2, low: 11.9, high: 12.4 }, { time: "2026-06-04", open: 12.2, close: 12.34, low: 12.1, high: 12.5 }] }
  }
  if (path.endsWith("/news")) {
    return { symbol: "000001", days: 30, limit: 20, include_announcements: true, items: [{ title: "平安银行公告", source: "交易所", time: "2026-06-04", url: "#", type: "announcement" }] }
  }
  switch (path) {
    case "/api/favorites/check/000001":
      return { symbol: "000001", is_favorite: false }
    case "/api/sync/multi-source/sources/current":
      return { name: "tushare", priority: 1, description: "Tushare" }
    case "/api/screening/industries":
      return { industries: [{ value: "银行", label: "银行", count: 10 }], total: 1 }
    case "/api/screening/run":
      return { total: 1, items: [{ code: "000001", close: 12.34, pct_chg: 1.23, amount: 123456789, ma20: 12.1, rsi14: 55 }] }
    case "/api/favorites/":
      return [{ symbol: "000001", stock_code: "000001", stock_name: "平安银行", market: "A股", tags: ["关注"], current_price: 12.34, change_percent: 1.23, added_at: "2026-06-04T10:00:00Z" }]
    case "/api/favorites/tags":
      return ["关注"]
    case "/api/paper/account":
      return { account: { cash: { CNY: 100000, HKD: 50000, USD: 10000 }, realized_pnl: { CNY: 0, HKD: 0, USD: 0 }, positions_value: { CNY: 1234, HKD: 0, USD: 0 }, equity: { CNY: 101234, HKD: 50000, USD: 10000 }, updated_at: "2026-06-04T10:00:00Z" }, positions: [] }
    case "/api/paper/positions":
      return { items: [] }
    case "/api/paper/orders":
      return { items: [] }
    default:
      return {}
  }
}
